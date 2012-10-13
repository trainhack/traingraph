import psycopg2
import random
from xml.sax import saxutils

conn = psycopg2.connect("dbname=traingraph user=postgres")
cur = conn.cursor()

COLOURS = ['ff0000', '00ff00', '0000ff', 'ffff00', 'ff00ff', '00ffff']

print '''<kml xmlns="http://www.opengis.net/kml/2.2">
	<Document>
		<name>traingraph</name>
		<Style id="dot-icon">
			<IconStyle>
				<scale>0.25</scale>
				<Icon>
					<href>http://sleeper.demozoo.org/images/dot.png</href>
				</Icon>
			</IconStyle>
		</Style>
'''

# extract railway lines
cur.execute('''
	-- SELECT ST_ASKML(ST_MAKELINE(node1.geom, node2.geom))
	SELECT ST_ASKML(linestring)
	FROM rail_segments
	INNER JOIN nodes AS node1 ON (node1_id = node1.id)
	INNER JOIN nodes AS node2 ON (node2_id = node2.id)
''')
for (kml,) in cur:
	print '<Placemark>%s<Style><LineStyle><width>2</width><color>ff%s</color></LineStyle></Style></Placemark>' % (kml, random.choice(COLOURS))

# extract stations with wgs84 lng/lat
cur.execute('''
	SELECT name, ST_ASKML(geom)
	FROM stations
''')
for (name, kml) in cur:
	print '<Placemark>'
	if name:
		print '<name>%s</name>' % saxutils.escape(name)
	print '<styleUrl>#dot-icon</styleUrl>'
	print kml
	print '</Placemark>'

print '</Document>'
print '</kml>'
