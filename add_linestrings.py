from sys import argv
import psycopg2

conn = psycopg2.connect("dbname=%s user=postgres" % argv[1])
paths_qry = conn.cursor()
cur = conn.cursor()

paths_qry.execute("""
	SELECT id FROM paths WHERE linestring IS NULL
""")
for (path_id,) in paths_qry:
	print path_id
	cur.execute("""
		UPDATE paths
		SET linestring = (
			SELECT
				st_makeline(st_accum(geom))
			FROM (
				SELECT nodes.geom
				FROM path_nodes
				INNER JOIN nodes ON (path_nodes.node_id = nodes.id)
				WHERE path_nodes.path_id = %s
				ORDER BY path_nodes.sequence_id
			) AS foo
		) WHERE id = %s
	""", (path_id, path_id))
	conn.commit()

print "all paths annotated with linestrings. Adding lengths..."
cur.execute("""
	UPDATE paths
	SET length = ST_Length(ST_GeogFromWKB(linestring))
	WHERE length IS NULL AND linestring IS NOT NULL
""")
conn.commit()
print "done."

paths_qry.close()
cur.close()
conn.close()
