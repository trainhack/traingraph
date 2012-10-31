from sys import argv
import psycopg2

conn = psycopg2.connect("dbname=%s user=postgres" % argv[1])
cur = conn.cursor()

origin = (-1.2703813, 51.7534277)  # Oxford
destination = (-0.1764437, 51.5160254)  # Paddington

distance_to_node = {}
predecessor_for_node = {}
visited_nodes = set()
seen_nodes = set()


# log a new minimum distance to a specified node (and the ID of the previous node leading up to it)
# iff it represents an improvement over the previous logged distance
def log_distance(node_id, last_node_id, distance):
	if (node_id not in distance_to_node) or distance_to_node[node_id] > distance:
		distance_to_node[node_id] = distance
		predecessor_for_node[node_id] = last_node_id
		seen_nodes.add(node_id)

# convert origin point to a geometry object
cur.execute("""SELECT ST_SetSRID(ST_Point(%s, %s), 4326)""", (origin[0], origin[1]))
(geom, ) = cur.fetchone()

print "Finding paths within 80 metres of the origin station..."
cur.execute("""
	SELECT id, length, node1_id, node2_id, ST_Line_Locate_Point(linestring, %s) AS distance_along
	FROM paths
	WHERE ST_Distance_Sphere(linestring, %s) < 80
""", (geom, geom))

# log the distances to the end points of these closest paths, calculated from length and distance_along
for (path_id, length, node1_id, node2_id, distance_along) in cur:
	log_distance(node1_id, None, length * distance_along)
	log_distance(node2_id, None, length * (1 - distance_along))


# convert destination point to a geometry object
cur.execute("""SELECT ST_SetSRID(ST_Point(%s, %s), 4326)""", (destination[0], destination[1]))
(geom, ) = cur.fetchone()

print "Finding paths within 80 metres of the destination station..."
cur.execute("""
	SELECT id, length, node1_id, node2_id, ST_Line_Locate_Point(linestring, %s) AS distance_along
	FROM paths
	WHERE ST_Distance_Sphere(linestring, %s) < 80
""", (geom, geom))

destination_nodes = {}  # stores distances between the destination point and the nodes at the end of the adjoining paths
# log the distances to the end points of these closest paths, calculated from length and distance_along
for (path_id, length, node1_id, node2_id, distance_along) in cur:
	node1_distance = length * distance_along
	if (node1_id not in destination_nodes) or (destination_nodes[node1_id] > node1_distance):
		destination_nodes[node1_id] = node1_distance

	node2_distance = length * (1 - distance_along)
	if (node2_id not in destination_nodes) or (destination_nodes[node2_id] > node2_distance):
		destination_nodes[node2_id] = node2_distance

while True:
	# find the node in seen_nodes with the smallest distance
	current_distance = None
	current_node = None

	for node_id in seen_nodes:
		if current_distance is None or distance_to_node[node_id] < current_distance:
			current_node = node_id
			current_distance = distance_to_node[node_id]

	if current_node is None or current_node == -1:
		break  # no more nodes, or encountered the destination node (special-cased with node ID -1)

	print "following paths from node %s (%s metres from origin)" % (current_node, current_distance)

	seen_nodes.remove(current_node)
	visited_nodes.add(current_node)

	# find all neighbouring nodes
	cur.execute("""
		SELECT (CASE WHEN node1_id = %s THEN node2_id ELSE node1_id END) AS node_id, length
		FROM paths
		WHERE node1_id = %s OR node2_id = %s
	""", (current_node, current_node, current_node))

	for (next_node, length) in cur:
		if next_node in visited_nodes:
			continue
		log_distance(next_node, current_node, current_distance + length)

	# also, see if current_node is present in destination_nodes, which means that there's a direct
	# link from it to the destination point (designated with the special ID number -1)
	if current_node in destination_nodes:
		log_distance(-1, current_node, current_distance + destination_nodes[current_node])

if current_node == -1:
	print "path back from destination:"
	while current_node:
		print current_node
		current_node = predecessor_for_node.get(current_node)
else:
	print "Exhausted search without finding destination point"

cur.close()
conn.close()
