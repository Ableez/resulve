from resulve.queries import (
    BLAST_RADIUS,
    CLUSTERS,
    FTS_SEARCH,
    GRAPH_EDGES,
    GRAPH_NODES,
    NEIGHBOURHOOD,
    SEMANTIC_SEARCH,
    nodes_to_geojson,
)


def _s(x):
    return str(x)


def test_semantic_search_uses_cosine_operator():
    q = _s(SEMANTIC_SEARCH)
    assert "<=>" in q
    assert "model_version" in q
    assert "hnsw" not in q.lower()


def test_fts_uses_plainto_tsquery():
    q = _s(FTS_SEARCH)
    assert "plainto_tsquery" in q
    assert "ts_rank" in q


def test_neighbourhood_uses_st_dwithin():
    q = _s(NEIGHBOURHOOD)
    assert "ST_DWithin" in q
    assert "ST_Distance" in q


def test_blast_radius_is_recursive():
    q = _s(BLAST_RADIUS)
    assert "WITH RECURSIVE" in q
    assert "depth < :max_depth" in q


def test_clusters_uses_dbscan():
    q = _s(CLUSTERS)
    assert "ST_ClusterDBSCAN" in q
    assert ":eps" in q and ":minpoints" in q


def test_graph_queries_extract_coords():
    assert "ST_X" in _s(GRAPH_NODES)
    assert "ST_Y" in _s(GRAPH_NODES)
    assert "ST_X" in _s(GRAPH_EDGES)


def test_nodes_to_geojson_shapes():
    import uuid
    nid = uuid.uuid4()
    nodes = [{"id": nid, "name": "util", "module_path": "pkg/util", "loc": 12, "x": 1.5, "y": -2.0}]
    edges = [{"source_module_id": nid, "target_module_id": nid, "edge_type": "import", "weight": 1.0, "sx": 0.0, "sy": 0.0, "tx": 1.0, "ty": 1.0}]
    gj = nodes_to_geojson(nodes, edges)
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) == 2
    pt = gj["features"][0]
    assert pt["geometry"]["type"] == "Point"
    assert pt["geometry"]["coordinates"] == [1.5, -2.0]
    line = gj["features"][1]
    assert line["geometry"]["type"] == "LineString"
    assert line["properties"]["kind"] == "edge"
