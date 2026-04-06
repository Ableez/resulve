from sqlalchemy import text


SEMANTIC_SEARCH = text("""
    SELECT c.id, c.file_id, c.chunk_type, c.name, c.start_line, c.end_line, c.raw_source,
           1 - (e.embedding <=> CAST(:vec AS vector)) AS score
    FROM chunk_embeddings e
    JOIN code_chunks c ON c.id = e.chunk_id
    JOIN repo_files f ON f.id = c.file_id
    WHERE e.model_version = :model
      AND (CAST(:repo_id AS uuid) IS NULL OR f.repo_id = CAST(:repo_id AS uuid))
    ORDER BY e.embedding <=> CAST(:vec AS vector)
    LIMIT :limit
""")


FTS_SEARCH = text("""
    SELECT c.id, c.file_id, c.chunk_type, c.name, c.start_line, c.end_line, c.raw_source,
           ts_rank(c.fts_vector, plainto_tsquery('english', :q)) AS score
    FROM code_chunks c
    JOIN repo_files f ON f.id = c.file_id
    WHERE c.fts_vector @@ plainto_tsquery('english', :q)
      AND (CAST(:repo_id AS uuid) IS NULL OR f.repo_id = CAST(:repo_id AS uuid))
    ORDER BY score DESC
    LIMIT :limit
""")


NEIGHBOURHOOD = text("""
    SELECT m2.id, m2.name, m2.module_path,
           ST_X(m2.spatial_coord) AS x, ST_Y(m2.spatial_coord) AS y,
           ST_Distance(m1.spatial_coord, m2.spatial_coord) AS layout_distance
    FROM modules m1
    JOIN modules m2
      ON m1.repo_id = m2.repo_id
     AND m1.id != m2.id
    WHERE m1.module_path = :path
      AND m1.repo_id = :repo_id
      AND ST_DWithin(m1.spatial_coord, m2.spatial_coord, :radius)
    ORDER BY layout_distance ASC
    LIMIT :limit
""")


BLAST_RADIUS = text("""
    WITH RECURSIVE blast AS (
        SELECT target_module_id AS module_id, 1 AS depth
        FROM module_edges
        WHERE source_module_id = (
            SELECT id FROM modules WHERE module_path = :path AND repo_id = :repo_id
        )
        UNION ALL
        SELECT me.target_module_id, b.depth + 1
        FROM module_edges me
        JOIN blast b ON me.source_module_id = b.module_id
        WHERE b.depth < :max_depth
    )
    SELECT DISTINCT m.id, m.name, m.module_path, b.depth,
        ST_Distance(origin.spatial_coord, m.spatial_coord) AS layout_dist
    FROM blast b
    JOIN modules m ON b.module_id = m.id
    CROSS JOIN (
        SELECT spatial_coord FROM modules WHERE module_path = :path AND repo_id = :repo_id
    ) origin
    ORDER BY b.depth, layout_dist
""")


CLUSTERS = text("""
    SELECT m.id, m.name, m.module_path,
           ST_X(m.spatial_coord) AS x, ST_Y(m.spatial_coord) AS y,
           ST_ClusterDBSCAN(m.spatial_coord, eps := :eps, minpoints := :minpoints) OVER () AS cluster_id
    FROM modules m
    WHERE m.repo_id = :repo_id
""")


GRAPH_NODES = text("""
    SELECT id, name, module_path, loc, ST_X(spatial_coord) AS x, ST_Y(spatial_coord) AS y
    FROM modules
    WHERE repo_id = :repo_id
""")


GRAPH_EDGES = text("""
    SELECT me.source_module_id, me.target_module_id, me.edge_type, me.weight,
           ST_X(ms.spatial_coord) AS sx, ST_Y(ms.spatial_coord) AS sy,
           ST_X(mt.spatial_coord) AS tx, ST_Y(mt.spatial_coord) AS ty
    FROM module_edges me
    JOIN modules ms ON ms.id = me.source_module_id
    JOIN modules mt ON mt.id = me.target_module_id
    WHERE ms.repo_id = :repo_id
""")


def nodes_to_geojson(nodes, edges):
    features = []
    for n in nodes:
        features.append({
            "type": "Feature",
            "id": str(n["id"]),
            "geometry": {"type": "Point", "coordinates": [float(n["x"]), float(n["y"])]},
            "properties": {
                "name": n["name"],
                "module_path": n["module_path"],
                "loc": int(n["loc"]),
                "kind": "module",
            },
        })
    for e in edges:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [float(e["sx"]), float(e["sy"])],
                    [float(e["tx"]), float(e["ty"])],
                ],
            },
            "properties": {
                "source": str(e["source_module_id"]),
                "target": str(e["target_module_id"]),
                "edge_type": e["edge_type"],
                "weight": float(e["weight"]),
                "kind": "edge",
            },
        })
    return {"type": "FeatureCollection", "features": features}
