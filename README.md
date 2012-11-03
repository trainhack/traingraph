traingraph
==========

This is a bundle of tools for extracting railway data from an OpenStreetMap data dump, and processing it into a
Postgres / PostGIS database suitable for analysing it as an abstract graph of nodes and edges. For example, this can be
used to find a theoretical shortest route between two points on the railway network, and translate this route back to
an actual geographical path for plotting on a map.

Contents
--------

* graph_reduction.txt - step-by-step instructions for generating the database. A SQL dump of a database generated this
  way for the full European rail network can be found at https://github.com/trainhack/traingraph/downloads as
  traingraph_eu.sql.bz2 .
* build_paths.py, add_linestrings.py - Python scripts used in this process.
* find_route.py - A Python script which uses the database to find a route between two points, which may be specified as
  either a station name or a (longitude, latitude) pair, and outputs a KML representation of the route:

    python find_route.py "2.3665838, 48.8412636" "Lille Europe"

Limitations
-----------

* The graph does not contain nodes for stations - only junctions - because OpenStreetMap data does not provide an
  explicit link between station locations and the sections of track that form them. find_route.py works around this by
  treating all ways within an 80m radius of the station node as part of the station, and 'patching in' the origin /
  destination points as virtual nodes. See the source code for more details.
* The graph is a long way from being an idealised representation - it still includes details like depots and sidings
  which are unlikely to be helpful in route analysis. We also represent double-tracked routes as two distinct edges,
  when it would be far better to condense these into a single path. (It's far from clear how you'd go about doing this
  reduction automatically, though - a simple junction between two double-tracked railways is likely to involve four or
  more sets of points, each of which is represented by its own node in the original OSM data, and you'd have to somehow
  infer that these are to be treated as a single entity when reducing the ways to a single edge.)
* The shortest path is not necessarily the most sensible one to physically send a train down. If the absolute shortest
  path happens to involve going down one prong of a Y-shaped junction and reversing back up the other, the algorithm
  will happily return that one even if it's highly unlikely that a train would really take that route! (But then again,
  many real-world train routes *do* do this...) Handling this properly would involve such fun things as minimum radius
  of curvature calculations.

Contact
-------

Matt Westcott <matt@west.co.tt> - http://matt.west.co.tt/ , @gasmanic