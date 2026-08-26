# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Read-only comparison of the lexical and domain layers for one hotel.

`1.1_build_graph.ipynb` runs this walk twice: once on a hotel already in the
restored dump, before the build, and again on the first hotel a participant
extracts, after it. Sharing the query and the print here, rather than
repeating both inline, keeps the "baseline" cell and the "your result" cell
checking the exact same thing.
"""

from graph_builder import connect
from workshop.graph_connection import graph_database

LAYER_QUERY = """
MATCH (d:Document {source_filename: $filename})<-[:FROM_DOCUMENT]-(c:Chunk)
MATCH (c)<-[:FROM_CHUNK]-(h:Hotel)
WITH h, count(DISTINCT c) AS chunks, max(size(c.embedding)) AS embedding_width
RETURN h.name AS name, h.address AS address, h.guest_rating AS rating,
       chunks, embedding_width,
       count { (h)-[:HAS_ROOM]->() } AS rooms,
       count { (h)-[:OFFERS_AMENITY]->() } AS amenities,
       count { (h)-[:HAS_POLICY]->() } AS policies,
       count { (h)-[:PROVIDES_SERVICE]->() } AS services
ORDER BY name
"""


def show_both_layers(filename: str) -> None:
    """Print the lexical and domain layers for the hotels in one document."""
    with connect() as driver:
        with driver.session(database=graph_database()) as session:
            rows = session.run(LAYER_QUERY, filename=filename).data()

    if not rows:
        print(f"{filename} has no hotel in this graph.")
        return

    for row in rows:
        print(f"{row['name']}  ({filename})")
        print(f"  lexical:  {row['chunks']} chunk(s), embedding width "
              f"{row['embedding_width']}")
        print(f"  domain:   {row['rooms']} rooms, {row['amenities']} amenities, "
              f"{row['policies']} policies, {row['services']} services")
        print(f"  on the node: rating {row['rating']}, address {row['address']}")
