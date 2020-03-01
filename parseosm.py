"""Analyzes an OpenStreetMap file for Lyon, France"""

from __future__ import print_function
import csv
import xml.etree.ElementTree as ET
import sqlite3

# ----------------------------------------------------------------
# first section: parsing the XML file into CSVs

def split_into_key_and_type(key):
    """The required schema requires breaking out the part before a colon as a "type" to be stored in
a separate field. If there is no colon, we substitute "regular."""
    idx = key.find(":")
    if idx < 0:
        return key, "regular"
    return key[idx+1:], key[:idx]

def prt_sorted_dict_top(unsrt, top_num):
    """Prints a dictionary sorted by value"""
    tups = unsrt.items()
    srtd = sorted(tups, key=lambda value: value[1], reverse=True)
    count = 0
    for key, value in srtd:
        print(key, ":", value)
        if top_num > 0:
            count = count + 1
            if count >= top_num:
                return

def generate_csvs():
    """Parses the OpenStreetMap XML and generates CSV files required by the project. We also tally
up some totals while parsing the XML."""
    # we tally up various things as we parse
    count = 0
    tag_set = {}
    tag_sub_tags = {}
    tag_attrs = {}
    osmtag_keys = {}
    unique_users = {}
    # we use a stack to tell which tags are nested within which other tags
    stack = []
    stkptr = 0

    # open the CSV files for writing
    nodes_file = open("nodes.csv", mode="w", newline="")
    nodes_tags_file = open("nodes_tags.csv", mode="w", newline="")
    ways_file = open("ways.csv", mode="w", newline="")
    ways_tags_file = open("ways_tags.csv", mode="w", newline="")
    ways_nodes_file = open("ways_nodes.csv", mode="w", newline="")

    nodes_writer = csv.writer(nodes_file, dialect='unix')
    nodes_tags_writer = csv.writer(nodes_tags_file, dialect='unix')
    ways_writer = csv.writer(ways_file, dialect='unix')
    ways_tags_writer = csv.writer(ways_tags_file, dialect='unix')
    ways_nodes_writer = csv.writer(ways_nodes_file, dialect='unix')

    nodes_writer.writerow(["id", "lat", "lon", "user", "uid", "version", "changeset", "timestamp"])
    ways_writer.writerow(["id", "user", "uid", "version", "changeset", "timestamp"])
    nodes_tags_writer.writerow(["id", "key", "value", "type"])
    ways_tags_writer.writerow(["id", "key", "value", "type"])
    ways_nodes_writer.writerow(["id", "node_id", "position"])
    way_position = 0

    #
    # all the corrections to addr:street that we are going to do
    corrections = {
        "Boulevard du 11 novembre 1918": "Boulevard du 11 Novembre 1918",
        "Rue moliere": "Rue Molière",
        "Chemin jean petit": "Chemin Jean Petit",
        "Cours DOCTEUR LONG": "Cours Docteur Long",
        "Cours du Docteur Long": "Cours Docteur Long",
        "Rue du Docteur Fleury-Pierre Papillon": "Rue du Docteur Pierre-Fleury Papillon",
        "Galerie Soufflot": "Quai Jules Courmont",
        "Caluire-et-Cuire": "Quai Clemenceau",
        "Route de vienne": "Route de Vienne",
        "rue de la charité": "Rue de la Charité",
        "rue du 8 Mai 1945": "Rue du 8 Mai 1945",
        "GRANDE RUE": "Grande Rue",
        "rue des Charmettes": "Rue des Charmettes",
        "allée des Savoies": "Allée des Savoies",
        "Roger Salengro": "Rue Roger Salengro",
        "Passage du beal": "Passage du Beal",
        "/25 Grande Rue": "Grande Rue",
        "37": "Grande Rue de Vaise",
        "A 7": "A7",
        "Ctre Cial Carrefour Ecully": "Centre Commercial Carrefour Ecully",
        "Grand Cloître": "Place du Grand Cloître",
        "Pl. Depéret": "Place Depéret",
        "Rond-Point Maréchal de Lattre de Tassigny":
            "Rue du Rond-Point Maréchal de Lattre de Tassigny",
        "Rue": "Rue Lortet",
        "Victor Hugo": "Rue Victor Hugo",
        "avenue Roger Salengro": "Avenue Roger Salengro",
        "boulevard Joliot Curie": "Boulevard Joliot Curie",
        "Chemin de Chalin": "chemin de Chalin",
        "chemin de chantegrillet": "Chemin de chantegrillet",
        "des remparts d'Ainay": "Rue des Remparts d'Ainay",
        "humanités": "Rue des Humanités",
        "place des Trois Renards": "Place des Trois Renards",
        "quai Perrache": "Quai Perrache",
        "rue Béchevelin": "Rue Béchevelin",
        "rue Carnot": "Rue Carnot",
        "rue Chavanne": "Rue Chavanne",
        "rue Duhamel": "Rue Duhamel",
        "rue François Peissel": "Rue François Peissel",
        "rue Laurent Paul": "Rue Laurent Paul",
        "rue Roger Salengro": "Rue Roger Salengro",
        "rue commandant Charcot": "Rue Commandant Charcot",
        "rue de Sèze": "Rue de Sèze",
        "rue de sans soucis": "Rue de Sans Soucis",
        "rue de tourvielle": "Rue de Tourvielle",
        "rue des freres bertrand": "Rue des Frères Bertrand",
        "rue du 4 août 1789": "Rue du 4 Août 1789",
        "rue vaubecour": "Rue Vaubecour",
    }

    #
    # here we go -- here's the parser + corrector
    filename = "lyon.osm"
    for event, elem in ET.iterparse(filename, events=('start', 'end')):
        count = count + 1
        if count == 1:
            root = elem
        if event == "start":
            tag = elem.tag
            attributes = elem.attrib
            if stkptr < len(stack):
                stack[stkptr] = [tag, attributes]
                stkptr = stkptr + 1
            else:
                stack.append([tag, attributes])
                stkptr = len(stack)
            #
            # tally up some things as we parse
            # what tags are in the XML file?
            if tag in tag_set:
                tag_set[tag] = tag_set[tag] + 1
            else:
                tag_set[tag] = 1
                # initialize other maps
                tag_sub_tags[tag] = {}
                tag_attrs[tag] = {}
            # what tags are within other tags?
            if stkptr > 1:
                prev = stack[stkptr - 2][0]
                tag_sub_tags[prev][tag] = True
            # what attributes does each tag have?
            for atname in attributes:
                tag_attrs[tag][atname] = True
            # if the tag is a "tag" tag, what are all the "keys" ("k" attributes) in use?
            if tag == "tag":
                key = attributes["k"]
                if key in osmtag_keys:
                    osmtag_keys[key] = osmtag_keys[key] + 1
                else:
                    osmtag_keys[key] = 1
            # count unique users
            if "uid" in attributes:
                unique_users[attributes["uid"]] = True
            #
            # generate the CSV files as we parse
            if tag == "node":
                nodes_writer.writerow([attributes["id"], attributes["lat"], attributes["lon"],
                                       attributes["user"], attributes["uid"], attributes["version"],
                                       attributes["changeset"], attributes["timestamp"]])
            elif tag == "tag":
                above_tag = stack[stkptr - 2][0]
                above_attrs = stack[stkptr - 2][1]
                key, k_type = split_into_key_and_type(attributes["k"])
                value = attributes["v"]
                #
                # Here's the magic spot where we apply our corrections
                if attributes["k"] == "addr:street":
                    if value in corrections:
                        print("Correcting", value, "-> to:", corrections[value])
                        value = corrections[value]
                if above_tag == "node":
                    nodes_tags_writer.writerow([above_attrs["id"], key, value, k_type])
                elif above_tag == "way":
                    ways_tags_writer.writerow([above_attrs["id"], key, value, k_type])
                # for relation, we do nothing
            elif tag == "way":
                ways_writer.writerow([attributes["id"], attributes["user"], attributes["uid"],
                                      attributes["version"], attributes["changeset"],
                                      attributes["timestamp"]])
                way_position = 0
            elif tag == "nd":
                way_position = way_position + 1
                above_attrs = stack[stkptr - 2][1]
                ways_nodes_writer.writerow([above_attrs["id"], attributes["ref"], way_position])
            # for all the other tags, we do nothing
        if event == "end":
            tag = elem.tag
            attributes = elem.attrib
            stkptr = stkptr - 1
            if stack[stkptr][0] != tag:
                print("tag end mismatch!!")
        # magic line that keeps memory usage from exploding
        root.clear()
    print("Done with parsing.")
    # close all the output files
    nodes_file.close()
    nodes_tags_file.close()
    ways_file.close()
    ways_tags_file.close()
    ways_nodes_file.close()
    # output our tallies
    print("Total number of tags", count)
    print("Number of occurrences of each tag", tag_set)
    print("Tags and their sub-tags (which tags are contained within each other tag)", tag_sub_tags)
    print("Tag attributes -- list of what attributes each tag has", tag_attrs)
    print("Values used for keys ('k' attributes on 'tag' tags")
    prt_sorted_dict_top(osmtag_keys, -1)
    print("Total number of unique users:", len(unique_users))

# ----------------------------------------------------------------
# second section: parsing the CSV files into an SQL DB

def escapestring(stng):
    """Returns an escaped string suitable for SQL commands."""
    return stng.replace("'", "''")


# dict_to_insert and dict_to_update take a Python dictionary and turn it into
# an SQL INSERT or UPDATE.
# Types on the values in the dictionary are assumed to be correct!
# I.e. numbers should be floats and ints, and strings should be strings
# (not numbers represented as strings or vice-versa or anything like that)
# This is useful because we can construct a Python dictionary once, then
# use it to either insert or update.
def dict_to_insert(tblname, insdct):
    """Converts a dictionary of fields to be inserted into an SQL INSERT."""
    fields = ''
    values = ''
    for fieldname in insdct:
        fields = fields + ', ' + fieldname
        if isinstance(insdct[fieldname], int):
            values = values + ', ' + str(insdct[fieldname])
        elif isinstance(insdct[fieldname], float):
            values = values + ', ' + str(insdct[fieldname])
        elif isinstance(insdct[fieldname], str):
            values = values + ", '" + escapestring(insdct[fieldname]) + "'"
        else:
            # this else should never happen
            tcba = type(insdct[fieldname])
            print('error: unrecognized type for:', tcba)
    sql = 'INSERT INTO ' + tblname + '(' + fields[2:] + ') VALUES (' + values[2:] + ');'
    return sql

# csv_to_database pulls a CSV file into a database.
# This function does NOT create the fields!
# It can't do that because it doesn't know the types for each column!
# YOU must create the table with the correct field names and types before calling this function.
# Column names much match field names in the CSV.
def csv_to_database(csv_file, tblname, rename_fields, dbcu):
    """Pulls a CSV file into a database table. The table needs to already be created."""
    fieldnames = []
    rownum = 0
    with open(csv_file, newline='') as csvfile:
        thereader = csv.reader(csvfile, delimiter=',', quotechar='"')
        for rowdat in thereader:
            if rownum == 0:
                for info in rowdat:
                    if info in rename_fields:
                        fieldnames.append(rename_fields[info])
                    else:
                        fieldnames.append(info)
            else:
                insdict = {}
                colnum = 0
                for info in rowdat:
                    insdict[fieldnames[colnum]] = info
                    colnum = colnum + 1
                sql = dict_to_insert(tblname, insdict)
                dbcu.execute(sql)
            rownum = rownum + 1

def set_up_osm_db(create_schema):
    """Set up the DB where we are going to import and analyze the OSM data"""
    # osmconn = sqlite3.connect(":memory:") # lyon data is too big for memory
    osmconn = sqlite3.connect("lyon.db")
    osmconn.row_factory = sqlite3.Row
    osmcu = osmconn.cursor()
    if not create_schema:
        return osmconn, osmcu
    # We don't have a system in place to figure out data types from the CSV file, so we have to
    # explicitly tell SQL what our columns are and what type they are
    osmcu.execute("CREATE TABLE nodes (                 \
                       id INTEGER PRIMARY KEY NOT NULL, \
                       lat REAL,                        \
                       lon REAL,                        \
                       user TEXT,                       \
                       uid INTEGER,                     \
                       version INTEGER,                 \
                       changeset INTEGER,               \
                       timestamp TEXT                   \
                   );")
    osmcu.execute("CREATE TABLE nodes_tags (                 \
                       id INTEGER,                           \
                       key TEXT,                             \
                       value TEXT,                           \
                       type TEXT,                            \
                       FOREIGN KEY (id) REFERENCES nodes(id) \
                   );")
    osmcu.execute("CREATE TABLE ways (                  \
                       id INTEGER PRIMARY KEY NOT NULL, \
                       user TEXT,                       \
                       uid INTEGER,                     \
                       version TEXT,                    \
                       changeset INTEGER,               \
                       timestamp TEXT                   \
                   );")
    osmcu.execute("CREATE TABLE ways_tags (                 \
                       id INTEGER NOT NULL,                 \
                       key TEXT NOT NULL,                   \
                       value TEXT NOT NULL,                 \
                       type TEXT,                           \
                       FOREIGN KEY (id) REFERENCES ways(id) \
                   );")
    osmcu.execute("CREATE TABLE ways_nodes (                      \
                       id INTEGER NOT NULL,                       \
                       node_id INTEGER NOT NULL,                  \
                       position INTEGER NOT NULL,                 \
                       FOREIGN KEY (id) REFERENCES ways(id),      \
                       FOREIGN KEY (node_id) REFERENCES nodes(id) \
                   );")
    osmcu.execute("CREATE INDEX idx_nd_usr ON nodes (uid);")
    osmconn.commit()
    osmcu.execute("CREATE INDEX idx_wy_usr ON ways (uid);")
    osmconn.commit()
    return osmconn, osmcu

# This function is like sql_to_dataframe except it just gives us a single number back
# useful if you're just selecting a count of something or the ID number for something.
def sql_to_scalar(dbcu, sql):
    """Return a single value from an SQL query"""
    print(sql)
    for row in dbcu.execute(sql):
        for item in row:
            result = item
    return result

def parse_csvs_into_sql(osmconn, osmcu):
    """This function pulls all our generated CSV files into one SQL db"""
    print("Parsing nodes.csv")
    csv_to_database("nodes.csv", 'nodes', {}, osmcu)
    osmconn.commit()
    print("Parsing nodes_tags.csv")
    csv_to_database("nodes_tags.csv", 'nodes_tags', {}, osmcu)
    osmconn.commit()
    print("Parsing ways.csv")
    csv_to_database("ways.csv", 'ways', {}, osmcu)
    osmconn.commit()
    print("Parsing ways_tags.csv")
    csv_to_database("ways_tags.csv", 'ways_tags', {}, osmcu)
    osmconn.commit()
    print("Parsing ways_nodes.csv")
    csv_to_database("ways_nodes.csv", 'ways_nodes', {}, osmcu)
    osmconn.commit()

def sql_to_list_of_lists(dbcu, sql):
    """Takes an SQL query that returns two colums and turns into Python dict where the first column
is the key and the second column is the value."""
    print(sql)
    result = []
    for row in dbcu.execute(sql):
        rvals = []
        position = 0
        for item in row:
            rvals.append(item)
            position = position + 1
        result.append(rvals)
    return result

def apply_corrections_to_sql_db(osmconn, osmcu):
    """Here we apply any data corrections that we do AFTER the parsing (most corrections are done
while parsing the XML, but we can make corrections here as well.)"""
    sql = "DELETE FROM ways_tags WHERE (id = 44895025) AND (type = 'addr') AND (key = 'street');"
    print(sql)
    osmcu.execute(sql)
    osmconn.commit()

def prt_list_top(lst, top_num):
    """Print the top entries in a list of lists (such as returned by sql_to_list_of_lists)
(separated by colons)."""
    count = 0
    for entry in lst:
        outstr = ""
        for item in entry:
            outstr = outstr + ": " + str(item)
        outstr = outstr[2:]
        count = count + 1
        print(str(count) + ". " + outstr)
        if top_num > 0:
            if count >= top_num:
                return

def prt_list_w_commas(lst):
    """Print the entries in a list of lists (such as returned by sql_to_list_of_lists)
(separated by commas)."""
    for entry in lst:
        outstr = ""
        for item in entry:
            outstr = outstr + ", " + str(item)
        outstr = outstr[2:]
        print(outstr)

def count_tags_for_key(osmcu, tag_type, tag_key, human_name):
    """Here we find the top 10 tag values for a specific tag key and output them for the user."""
    sql = "SELECT value, COUNT(*)                                          \
           FROM nodes_tags                                                 \
           WHERE (type = '" + tag_type + "') AND (key = '" + tag_key + "') \
           GROUP BY value ORDER BY COUNT(*) DESC;"
    stuff = sql_to_list_of_lists(osmcu, sql)
    print("Top 10 " + human_name + " nodes with number of occurrences:")
    prt_list_top(stuff, 10)
    sql = "SELECT value, COUNT(*)                                          \
           FROM ways_tags                                                  \
           WHERE (type = '" + tag_type + "') AND (key = '" + tag_key + "') \
           GROUP BY value ORDER BY COUNT(*) DESC;"
    stuff = sql_to_list_of_lists(osmcu, sql)
    print("Top 10 " + human_name + " ways with number of occurrences:")
    prt_list_top(stuff, 10)

def analyze_osm_sql(osmcu):
    """Here we assume all corrections are done and we're ready to analyze the data!"""
    num_nodes = sql_to_scalar(osmcu, "SELECT COUNT(*) FROM nodes WHERE 1;")
    print("Number of nodes:", num_nodes)

    num_ways = sql_to_scalar(osmcu, "SELECT COUNT(*) FROM ways WHERE 1;")
    print("Number of ways:", num_ways)

    num_nodes_tags = sql_to_scalar(osmcu, "SELECT COUNT(*) FROM nodes_tags WHERE 1;")
    print("Number of node tags:", num_nodes_tags)

    num_ways_tags = sql_to_scalar(osmcu, "SELECT COUNT(*) FROM ways_tags WHERE 1;")
    print("Number of ways tags:", num_ways_tags)

    num_ways_nodes = sql_to_scalar(osmcu, "SELECT COUNT(*) FROM ways_nodes WHERE 1;")
    print("Number of ways nodes:", num_ways_nodes)

    min_lat = sql_to_scalar(osmcu, "SELECT MIN(lat) FROM nodes WHERE 1;")
    print("Minimum latitude:", min_lat)

    max_lat = sql_to_scalar(osmcu, "SELECT MAX(lat) FROM nodes WHERE 1;")
    print("Maximum latitude:", max_lat)

    min_lon = sql_to_scalar(osmcu, "SELECT MIN(lon) FROM nodes WHERE 1;")
    print("Minimum longitude:", min_lon)

    max_lon = sql_to_scalar(osmcu, "SELECT MAX(lon) FROM nodes WHERE 1;")
    print("Maximum longitude:", max_lon)

    # this is the full outer join attempt that did not work
    # num_unique_users = sql_to_scalar(osmcu, "SELECT COUNT(*)                                  \
    #          FROM (SELECT DISTINCT nodes.uid, ways.uid
    #              FROM nodes FULL OUTER JOIN ways ON (nodes.uid = ways.uid) ) sub \
    #          WHERE 1;")
    # print("Number of unique users:", num_unique_users)

    num_unique_users = sql_to_scalar(osmcu, "SELECT COUNT(*) FROM ( \
            SELECT uid FROM nodes                                   \
            UNION                                                   \
            SELECT uid FROM ways                                    \
        ) sub                                                       \
        WHERE 1;")
    print("Number of unique users:", num_unique_users)

    count_tags_for_key(osmcu, "regular", "amenity", "amenities")
    count_tags_for_key(osmcu, "regular", "building", "buildings")
    count_tags_for_key(osmcu, "regular", "highway", "highways")
    count_tags_for_key(osmcu, "regular", "name", "names")
    count_tags_for_key(osmcu, "regular", "wall", "walls")
    count_tags_for_key(osmcu, "regular", "natural", "natural features")
    count_tags_for_key(osmcu, "regular", "surface", "surfaces")

    castle_wall_way_id = sql_to_scalar(osmcu, "SELECT id FROM ways_tags WHERE (type = 'regular') AND (key = 'wall') AND (value = 'castle_wall');")
    sql = "SELECT nodes.lat, nodes.lon FROM ways_nodes, nodes WHERE (ways_nodes.id = " + str(castle_wall_way_id) + ") AND (ways_nodes.node_id = nodes.id) ORDER BY ways_nodes.position;"
    castle_wall_coordinates = sql_to_list_of_lists(osmcu, sql)
    print("Here's the latitude and longitude coordinates for the castle wall:")
    prt_list_w_commas(castle_wall_coordinates)

    sql = "SELECT nodes.lat, nodes.lon FROM ways_nodes, nodes WHERE (ways_nodes.id = 442928017) AND (ways_nodes.node_id = nodes.id) ORDER BY ways_nodes.position;"
    tunnel_coordinates = sql_to_list_of_lists(osmcu, sql)
    print("Here's the latitude and longitude coordinates for the tunnel (hand-picked):")
    prt_list_w_commas(tunnel_coordinates)

# ----------------------------------------------------------------

def main():
    make_database = True # set to False if you have already built the DB and just want to run analysis queries
    osmconn, osmcu = set_up_osm_db(make_database)
    if make_database:
        generate_csvs()
        parse_csvs_into_sql(osmconn, osmcu)
        apply_corrections_to_sql_db(osmconn, osmcu)
    analyze_osm_sql(osmcu)
    osmconn.close()
    print("Done!")

main()
