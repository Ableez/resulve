import os
import networkx as nx

from resulve.config import get_settings


def module_path_from_file(file_path):
    p, _ = os.path.splitext(file_path)
    return p.replace(os.sep, "/")


def resolve_import(current_module, imp, known_modules):
    if imp in known_modules:
        return imp
    parts = imp.split(".")
    while parts:
        candidate = "/".join(parts)
        if candidate in known_modules:
            return candidate
        parts.pop()
    base = current_module.rsplit("/", 1)[0]
    for i in range(len(imp.split(".")), 0, -1):
        guess = base + "/" + "/".join(imp.split(".")[:i])
        if guess in known_modules:
            return guess
    return None


def build_dep_graph(files):
    known = set()
    file_imports = {}
    locs = {}
    for f in files:
        mod = module_path_from_file(f["path"])
        known.add(mod)
        imports = []
        loc = 0
        for ch in f["chunks"]:
            imports.extend(ch.get("imports") or [])
            loc += max(0, ch["end_line"] - ch["start_line"] + 1) if ch["chunk_type"] == "file" else 0
        file_imports[mod] = imports
        locs[mod] = loc or 1

    edges = []
    for mod, imports in file_imports.items():
        seen = {}
        for imp in imports:
            target = resolve_import(mod, imp, known)
            if target and target != mod:
                seen[target] = seen.get(target, 0) + 1
        for target, w in seen.items():
            edges.append((mod, target, float(w)))
    return list(known), edges, locs


def compute_layout(nodes, edges):
    s = get_settings()
    g = nx.DiGraph()
    for n in nodes:
        g.add_node(n)
    for src, dst, w in edges:
        g.add_edge(src, dst, weight=w)
    if g.number_of_nodes() == 0:
        return {}
    if g.number_of_nodes() == 1:
        only = next(iter(g.nodes))
        return {only: (0.0, 0.0)}
    pos = nx.spring_layout(
        g,
        k=s.layout_k / max(1.0, g.number_of_nodes() ** 0.5),
        iterations=s.layout_iterations,
        seed=42,
    )
    scale = 100.0
    return {n: (float(p[0]) * scale, float(p[1]) * scale) for n, p in pos.items()}
