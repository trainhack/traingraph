from sys import argv
import psycopg2

conn = psycopg2.connect("dbname=%s user=postgres" % argv[1])
cur = conn.cursor()

while True:
	# retrieve a junction node which has unfollowed segments, and a segment hanging off it
	cur.execute("""
		SELECT
			junctions.id AS first_node,
			(CASE WHEN junctions.id = node1_id THEN node2_id ELSE node1_id END) AS second_node
		FROM junctions
		INNER JOIN rail_segments ON (
			(junctions.id = node1_id OR junctions.id = node2_id)
			AND path_id IS NULL
		)
		WHERE unfollowed_neighbour_count > 0
		LIMIT 1
	""")

	row = cur.fetchone()
	if row is None:
		break

	(last_node, current_node) = row
	nodes = [last_node, current_node]

	while True:
		# continue walking the graph until we encounter another node with more than one exit
		cur.execute("""
			SELECT
				(CASE WHEN node1_id = %s THEN node2_id ELSE node1_id END) AS next_node
			FROM rail_segments
			WHERE
				(node1_id = %s AND node2_id <> %s)
				OR (node2_id = %s AND node1_id <> %s)
		""", (
			current_node,
			current_node, last_node,
			current_node, last_node,
		))

		rows = cur.fetchall()
		if len(rows) != 1:
			break

		(next_node, ) = rows[0]
		nodes.append(next_node)
		last_node = current_node
		current_node = next_node

	if nodes[0] > nodes[-1]:
		# reverse path so that starting id <= ending id
		nodes.reverse()

	print repr(nodes)

	# path found; insert it into the db and update unfollowed_neighbour_count of path ends
	cur.execute("""
		INSERT INTO paths (node1_id, node2_id) VALUES (%s, %s);

		UPDATE junctions SET unfollowed_neighbour_count = unfollowed_neighbour_count - 1
		WHERE id = %s;
		UPDATE junctions SET unfollowed_neighbour_count = unfollowed_neighbour_count - 1
		WHERE id = %s;
	""", (nodes[0], nodes[-1], nodes[0], nodes[-1]))
	for (i, node) in enumerate(nodes):
		cur.execute("""
			INSERT INTO path_nodes (path_id, node_id, sequence_id) VALUES (
				CURRVAL('seq_path_id'), %s, %s
			)
		""", (node, i))

		if i != 0:
			# annotate rail_segments with the path id to mark them as visited
			cur.execute("""
				UPDATE rail_segments
				SET path_id = CURRVAL('seq_path_id')
				WHERE node1_id = %s AND node2_id = %s
			""", (
				min(nodes[i - 1], nodes[i]),
				max(nodes[i - 1], nodes[i]),
			))

	conn.commit()

cur.close()
conn.close()
