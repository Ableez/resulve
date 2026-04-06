import ast
import os


LANG_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".md": "markdown",
}


def detect_language(path):
    _, ext = os.path.splitext(path.lower())
    return LANG_BY_EXT.get(ext, "text")


def chunk_file(path, source):
    lang = detect_language(path)
    if lang == "python":
        try:
            return chunk_python(path, source)
        except SyntaxError:
            return chunk_generic(path, source)
    return chunk_generic(path, source)


def chunk_python(path, source):
    tree = ast.parse(source)
    lines = source.splitlines()
    chunks = []
    module_name = os.path.splitext(os.path.basename(path))[0]
    module_text = "\n".join(lines)
    chunks.append({
        "chunk_type": "file",
        "name": module_name,
        "start_line": 1,
        "end_line": max(1, len(lines)),
        "raw_source": module_text,
        "imports": _collect_imports(tree),
    })
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            chunks.append(_chunk_from_node(node, "function", lines))
        elif isinstance(node, ast.ClassDef):
            chunks.append(_chunk_from_node(node, "class", lines))
    return chunks


def _chunk_from_node(node, kind, lines):
    start = node.lineno
    end = getattr(node, "end_lineno", start) or start
    src = "\n".join(lines[start - 1 : end])
    return {
        "chunk_type": kind,
        "name": node.name,
        "start_line": start,
        "end_line": end,
        "raw_source": src,
        "imports": [],
    }


def _collect_imports(tree):
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.append(a.name)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            for a in node.names:
                if base:
                    out.append(f"{base}.{a.name}" if a.name != "*" else base)
                else:
                    out.append(a.name)
    return out


def chunk_generic(path, source):
    lines = source.splitlines() or [""]
    size = 80
    chunks = []
    name = os.path.basename(path)
    for i in range(0, len(lines), size):
        block = lines[i : i + size]
        chunks.append({
            "chunk_type": "block",
            "name": f"{name}:{i + 1}",
            "start_line": i + 1,
            "end_line": i + len(block),
            "raw_source": "\n".join(block),
            "imports": [],
        })
    return chunks
