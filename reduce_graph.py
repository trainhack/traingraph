import psycopg2

conn = psycopg2.connect("dbname=traingraph user=postgres")
nodes_qry = conn.cursor()
cur = conn.cursor()

cur.execute("""
SELECT nodes.id
FROM nodes
INNER JOIN rail_segments ON (nodes.id = node1_id OR nodes.id = node2_id)
GROUP BY nodes.id
HAVING count(distinct rail_type) > 1
""")
mixed_mode_results = cur.fetchall()
mixed_mode_nodes = set([res[0] for res in mixed_mode_results])

nodes_qry.execute("""
	SELECT nodes.id
	FROM nodes
	INNER JOIN rail_segments ON (nodes.id = node1_id OR nodes.id = node2_id)
	GROUP BY nodes.id
	HAVING COUNT(node1_id) = 2
""")

for ((node_id,)) in nodes_qry:
	# find the segments adjoining this one
	print node_id
	if node_id in mixed_mode_nodes:
		continue

	cur.execute("""
		SELECT node1_id, node2_id, rail_type, linestring
		FROM rail_segments
		WHERE (node1_id = %s OR node2_id = %s)
	""", (node_id, node_id))
	results = cur.fetchall()
	if len(results) != 2:
		# raise Exception('Number of segments adjoining node %s was not exactly 2' % node_id)
		print "warning: number of segments adjoining node %s was not exactly 2" % node_id
		continue

	[(seg1_node1, seg1_node2, seg1_type, seg1_linestring), (seg2_node1, seg2_node2, seg2_type, seg2_linestring)] = results
	if seg1_type != seg2_type:
		raise Exception('node %s had two neighbouring rail types: %s and %s' % (node_id, seg1_type, seg2_type))

	if seg1_node2 == node_id and seg2_node1 == node_id:
		# new segment is seg1 + seg2
		cur.execute("""
			INSERT INTO rail_segments (node1_id, node2_id, rail_type, linestring)
			VALUES (
				%s, %s, %s,
				ST_LINEMERGE(ST_COLLECT(%s, %s))
			)
		""", (seg1_node1, seg2_node2, seg1_type, seg1_linestring, seg2_linestring))
	elif seg1_node1 == node_id and seg2_node2 == node_id:
		# new segment is seg2 + seg1
		cur.execute("""
			INSERT INTO rail_segments (node1_id, node2_id, rail_type, linestring)
			VALUES (
				%s, %s, %s,
				ST_LINEMERGE(ST_COLLECT(%s, %s))
			)
		""", (seg2_node1, seg1_node2, seg1_type, seg2_linestring, seg1_linestring))
	elif seg1_node2 == node_id and seg2_node2 == node_id:
		# new segment is seg1 + rev(seg2)
		cur.execute("""
			INSERT INTO rail_segments (node1_id, node2_id, rail_type, linestring)
			VALUES (
				%s, %s, %s,
				ST_LINEMERGE(ST_COLLECT(%s, ST_REVERSE(%s)))
			)
		""", (seg1_node1, seg2_node1, seg1_type, seg1_linestring, seg2_linestring))
	elif seg1_node1 == node_id and seg2_node1 == node_id:
		# new segment is rev(seg2) + seg1
		cur.execute("""
			INSERT INTO rail_segments (node1_id, node2_id, rail_type, linestring)
			VALUES (
				%s, %s, %s,
				ST_LINEMERGE(ST_COLLECT(ST_REVERSE(%s), %s))
			)
		""", (seg2_node2, seg1_node2, seg1_type, seg2_linestring, seg1_linestring))
	else:
		raise Exception("don't know how to reduce node %s!" % node_id)

	cur.execute("""
		DELETE FROM rail_segments
		WHERE node1_id = %s AND node2_id = %s and rail_type = %s
	""", (seg1_node1, seg1_node2, seg1_type))
	cur.execute("""
		DELETE FROM rail_segments
		WHERE node1_id = %s AND node2_id = %s and rail_type = %s
	""", (seg2_node1, seg2_node2, seg2_type))
	conn.commit()

nodes_qry.close()
cur.close()
conn.close()
