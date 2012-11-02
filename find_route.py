# find_route.py: Traverse the 'paths' table using Dijkstra's Algorithm to find the shortest
# distance between two points on or near the railway network.

# A 'path' is a non-branching section of track joining two nodes, identified as node1_id and node2_id.
# To minimise the number of permutations involved in database access, we stipulate that
# node1_id < node2_id.
# For each path, we know its actual geographical route (expressed in the database as a PostGIS linestring)
# and its length in metres.

from sys import argv, exit
import psycopg2
import re

if len(argv) == 4:
	(dbname, origin_station, destination_station) = argv[1:4]
else:
	print "Usage: find_route.py <dbname> <origin-station> <destination-station>"
	exit()

conn = psycopg2.connect("dbname=%s user=postgres" % dbname)
cur = conn.cursor()


# Find a geom object corresponding to the passed station string, which may be a (long, lat) pair
# or a station name. Return None if not found
def find_station_geom(station):
	# try to interpret origin as a (long, lat) pair
	match = re.match(r'([\+\-\d\.]+)\s*\,\s*([\+\-\d\.]+)$', station)
	if match:
		origin = match.groups()
		# convert origin point to a geometry object
		cur.execute("""
			SELECT ST_SetSRID(ST_Point(%s, %s), 4326)
		""", (float(origin[0]), float(origin[1])))
		(geom, ) = cur.fetchone()
		return geom
	else:
		# look up as a station name
		cur.execute("""
			SELECT geom
			FROM stations
			WHERE name = %s
		""", (station,))
		result = cur.fetchone()
		if result:
			(geom, ) = result
			return geom

origin_geom = find_station_geom(origin_station)
if not origin_geom:
	print "Could not find station %s" % origin_station
	exit()

destination_geom = find_station_geom(destination_station)
if not destination_geom:
	print "Could not find station %s" % destination_station
	exit()


# Any paths which pass within this number of metres of the origin/destination point
# are considered to be valid start/end positions for the route
STATION_RADIUS = 80


# Set up data structures used during the algorithm's run

# Mapping from node ID to the shortest distance so far found between the origin point and that node
distance_to_node = {}

# Mapping from node ID to a (path_id, last_node_id, start_frac, end_frac) tuple, where:
# path_id = ID of the path immediately leading up to that node on the shortest route found so far
# last_node_id = ID of the node at the far end of that path
# start_frac = how far along the linestring (expressed as a fraction from 0..1) last_node is
# end_frac = how far along the linestring (expressed as a fraction from 0..1) the present node is.
# NB start_frac and end_frac will always be 0 or 1 (indicating the full extent of the path)
#  except for paths at the origin and destination, which start/end at the specific point
# closest to the original requested origin/destination point
path_to_node = {}

# Contains IDs of all nodes for which we know we've established the shortest possible route
visited_nodes = set()

# Contains IDs of all nodes which we've encountered by following paths, but have not yet
# exhausted the possibilities for finding shorter routes
seen_nodes = set()


# Helper function:
# log a new minimum distance to a specified node (and the IDs of the previous path and node leading
# up to it) iff it represents an improvement over the previous logged distance
def log_distance(node_id, last_node_id, distance, path_id, start_frac, end_frac):
	if (node_id not in distance_to_node) or distance_to_node[node_id] > distance:
		distance_to_node[node_id] = distance
		path_to_node[node_id] = (path_id, last_node_id, start_frac, end_frac)
		seen_nodes.add(node_id)


print "Finding paths within %d metres of the origin station..." % STATION_RADIUS
# Find the details of paths which pass within STATION_RADIUS metres of the origin point.
# ST_Line_Locate_Point gives us a value between 0 and 1 indicating how far along the linestring
# the closest point to the origin point is.
cur.execute("""
	SELECT id, length, node1_id, node2_id, ST_Line_Locate_Point(linestring, %s) AS distance_along
	FROM paths
	WHERE ST_Distance_Sphere(linestring, %s) < %s
""", (origin_geom, origin_geom, STATION_RADIUS))

# The nodes on either end of these paths form the initial set of 'seen' nodes.
# By scaling our distance_along value (a fraction from 0 to 1) by the total length of the path,
# we can determine the absolute distance from the origin point (or rather, the nearest point on the
# path to the origin point) to these end nodes.
for (path_id, length, node1_id, node2_id, distance_along) in cur:
	log_distance(node1_id, None, length * distance_along, path_id, distance_along, 0)
	log_distance(node2_id, None, length * (1 - distance_along), path_id, distance_along, 1)


# Now repeat the process at the destination end. When we perform database queries to find
# onward paths to follow from a particular node, we'll also check the node on our list of candidate
# destination nodes.
print "Finding paths within %d metres of the destination station..." % STATION_RADIUS
cur.execute("""
	SELECT id, length, node1_id, node2_id, ST_Line_Locate_Point(linestring, %s) AS distance_along
	FROM paths
	WHERE ST_Distance_Sphere(linestring, %s) < %s
""", (destination_geom, destination_geom, STATION_RADIUS))


# The destination_nodes dict will contain the node IDs of the nodes at either end of the paths
# which pass within STATION_RADIUS metres of the destination point.
# These are mapped to a tuple of (distance, path_id, start_frac, end_frac), where:
# distance = absolute distance from that node to the destination point
#    (or rather, the nearest point on the path to the destination point)
# start_frac = how far along the linestring (as a fraction from 0..1) the end node is
#    (i.e. 0 if the end node is node1, 1 if it's node2)
# end_frac = how far along the linestring (as a fraction from 0..1) the destination point is
destination_nodes = {}

for (path_id, length, node1_id, node2_id, distance_along) in cur:
	node1_distance = length * distance_along
	# store a new distance/path against this node ID if we haven't encountered it already,
	# or if the new distance is shorter than the previously encountered one
	if (node1_id not in destination_nodes) or (destination_nodes[node1_id] > node1_distance):
		destination_nodes[node1_id] = (node1_distance, path_id, 0, distance_along)

	node2_distance = length * (1 - distance_along)
	if (node2_id not in destination_nodes) or (destination_nodes[node2_id] > node2_distance):
		destination_nodes[node2_id] = (node2_distance, path_id, 1, distance_along)


while True:
	# Look for the node in seen_nodes with the smallest distance from the origin.
	# Since this is the smallest, we know that we cannot possibly improve on it by following a
	# route through any of the other nodes in seen_nodes - and thus we can declare it a minimal
	# route (and move it to the visited_nodes set).

	current_distance = None  # the shortest distance we've encountered so far in our scan through seen_nodes
	current_node = None  # ID of the node which has this shortest distance

	for node_id in seen_nodes:
		# update current_distance and current_node if it's an improvement over the shortest distance found so far
		if current_distance is None or distance_to_node[node_id] < current_distance:
			current_node = node_id
			current_distance = distance_to_node[node_id]

	if current_node is None or current_node == -1:
		# A current_node of None means that seen_nodes was empty - i.e. we have exhausted the
		# set of possible nodes to check.
		# -1 is a special case node ID representing our destination point, and this indicates that
		# we have found a minimal route to that destination and thus arrived at our answer.
		break  # in either case, we can stop iterating

	print "following paths from node %s (%s metres from origin)" % (current_node, current_distance)

	# Move current_node from seen_nodes to visited_nodes, as we can be sure it's a minimal route
	seen_nodes.remove(current_node)
	visited_nodes.add(current_node)

	# Query the database for all paths leading on from this node, and the IDs of the nodes at the far end
	cur.execute("""
		SELECT
			id,
			(CASE WHEN node1_id = %s THEN node2_id ELSE node1_id END) AS node_id,
			length,
			(CASE WHEN node1_id = %s THEN 0 ELSE 1 END) AS start_frac
		FROM paths
		WHERE node1_id = %s OR node2_id = %s
	""", (current_node, current_node, current_node, current_node))

	for (path_id, next_node, length, start_frac) in cur:
		if next_node in visited_nodes:
			# ignore paths that take us back to a node that we already have a minimal route for
			continue
		# compute the distance from the origin to this new node as
		# current_distance (the distance from origin to current_node) plus the new path length,
		# and log this in our data structures if it represents an improvement over any previous route
		# to that node
		log_distance(next_node, current_node, current_distance + length, path_id, start_frac, 1 - start_frac)

	# also, see if current_node has an entry in destination_nodes; if it does, we can treat that
	# as equivalent to a path taking us to the final destination point (indicated with the dummy
	# node ID -1).
	if current_node in destination_nodes:
		(distance, path_id, start_frac, end_frac) = destination_nodes[current_node]
		log_distance(-1, current_node, current_distance + distance, path_id, start_frac, end_frac)

# We have now left the loop; a current_node of -1 indicates that we have successfully reached
# the destination point (and thus found a minimal route to it).
if current_node == -1:
	# Each node's entry in path_to_node points to the path and previous node leading up to it,
	# so we can follow the chain back until we reach a node in our initial origin set, which
	# has 'None' as its predecessor.

	route_geom = None  # assemble the geometry for the full route as a 'multilinestring' geometry type in this variable
	while current_node is not None:
		(path_id, next_node, start_frac, end_frac) = path_to_node[current_node]
		print "%d to %d via path %d" % (current_node, (next_node or 0), path_id)
		if start_frac == end_frac:
			# avoid adding single points to the accumulated geometry, as this turns it into
			# a geometrycollection rather than a multilinestring
			pass
		if start_frac <= end_frac:
			# retrieve the substring of the linestring between start_frac and end_frac
			cur.execute("""
				SELECT ST_Collect(
					ST_Line_Substring(linestring, %s, %s),
					%s
				)
				FROM paths
				WHERE id = %s
			""", (start_frac, end_frac, route_geom, path_id))
		else:
			# start_frac > end_frac, indicating that we follow the path in reverse;
			# ST_Line_Substring can't handle reversed substrings itself, so we need to switch the
			# endpoints around, then reverse the result
			cur.execute("""
				SELECT ST_Collect(
					ST_Reverse(ST_Line_Substring(linestring, %s, %s)),
					%s
				)
				FROM paths
				WHERE id = %s
			""", (end_frac, start_frac, route_geom, path_id))

		(route_geom, ) = cur.fetchone()
		current_node = next_node

	# condense route_geom into a single linestring and output it as KML
	cur.execute("""
		SELECT ST_AsKML(ST_LineMerge(ST_CollectionExtract(%s, 2)))
	""", (route_geom,))
	(kml, ) = cur.fetchone()
	print kml
else:
	print "Exhausted search without finding destination point"

cur.close()
conn.close()
