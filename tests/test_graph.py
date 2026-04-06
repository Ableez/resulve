from resulve.graph import build_dep_graph, compute_layout, module_path_from_file, resolve_import


def test_module_path_from_file():
    assert module_path_from_file("app/util.py") == "app/util"
    assert module_path_from_file("pkg/sub/mod.py") == "pkg/sub/mod"


def test_resolve_import_direct_hit():
    known = {"pkg/util", "pkg/main"}
    assert resolve_import("pkg/main", "pkg.util", known) == "pkg/util"


def test_build_dep_graph_connects_modules():
    files = [
        {
            "path": "pkg/main.py",
            "chunks": [
                {"chunk_type": "file", "name": "main", "start_line": 1, "end_line": 10, "raw_source": "", "imports": ["pkg.util", "os"]},
            ],
        },
        {
            "path": "pkg/util.py",
            "chunks": [
                {"chunk_type": "file", "name": "util", "start_line": 1, "end_line": 5, "raw_source": "", "imports": []},
            ],
        },
    ]
    nodes, edges, locs = build_dep_graph(files)
    assert set(nodes) == {"pkg/main", "pkg/util"}
    assert ("pkg/main", "pkg/util", 1.0) in edges
    assert locs["pkg/main"] >= 1


def test_compute_layout_returns_all_nodes():
    nodes = ["a", "b", "c"]
    edges = [("a", "b", 1.0), ("b", "c", 1.0)]
    pos = compute_layout(nodes, edges)
    assert set(pos) == set(nodes)
    for n in nodes:
        x, y = pos[n]
        assert isinstance(x, float)
        assert isinstance(y, float)


def test_compute_layout_empty():
    assert compute_layout([], []) == {}


def test_compute_layout_single_node():
    pos = compute_layout(["solo"], [])
    assert pos == {"solo": (0.0, 0.0)}
