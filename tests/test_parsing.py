from resulve.parsing import chunk_file, detect_language


def test_detect_language_python():
    assert detect_language("a/b/foo.py") == "python"
    assert detect_language("x.js") == "javascript"
    assert detect_language("readme.md") == "markdown"
    assert detect_language("unknown.xyz") == "text"


def test_chunk_python_file_produces_file_and_symbol_chunks():
    src = (
        "import os\n"
        "from math import sqrt\n"
        "\n"
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "class Thing:\n"
        "    def hello(self):\n"
        "        return 'hi'\n"
    )
    chunks = chunk_file("app/util.py", src)
    kinds = [c["chunk_type"] for c in chunks]
    assert "file" in kinds
    assert "function" in kinds
    assert "class" in kinds
    names = {c["name"] for c in chunks}
    assert "add" in names
    assert "Thing" in names
    file_chunk = [c for c in chunks if c["chunk_type"] == "file"][0]
    assert "os" in file_chunk["imports"]
    assert any("sqrt" in i or "math" in i for i in file_chunk["imports"])


def test_chunk_python_with_syntax_error_falls_back():
    src = "def broken(\n"
    chunks = chunk_file("bad.py", src)
    assert len(chunks) >= 1
    assert all(c["chunk_type"] == "block" for c in chunks)


def test_chunk_generic_splits_lines():
    src = "\n".join(f"line {i}" for i in range(200))
    chunks = chunk_file("x.txt", src)
    assert len(chunks) >= 2
    total = sum(len(c["raw_source"].splitlines()) for c in chunks)
    assert total == 200
