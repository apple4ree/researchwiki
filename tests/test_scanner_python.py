"""Tests for the Python AST scanner."""

from researchwiki.scanner import python


def test_extracts_class_function_method():
    source = (
        "class Trainer(Base):\n"
        "    def train_one_epoch(self, loader) -> dict:\n"
        "        return {}\n"
        "\n"
        "def helper(x: int) -> int:\n"
        "    return x + 1\n"
    )
    symbols, errors = python.scan("src/trainer.py", source)
    assert errors == []

    by_name = {s.name: s for s in symbols}
    assert "Trainer" in by_name
    assert by_name["Trainer"].kind == "class"
    assert by_name["Trainer"].signature == "class Trainer(Base):"
    assert by_name["Trainer"].line == 1

    assert "train_one_epoch" in by_name
    assert by_name["train_one_epoch"].kind == "method"
    assert by_name["train_one_epoch"].parent == "Trainer"
    assert "loader" in by_name["train_one_epoch"].signature
    assert "-> dict" in by_name["train_one_epoch"].signature

    assert "helper" in by_name
    assert by_name["helper"].kind == "function"
    assert by_name["helper"].parent is None


def test_async_function():
    source = "async def fetch(url: str) -> bytes:\n    return b''\n"
    symbols, errors = python.scan("src/io.py", source)
    assert errors == []
    assert len(symbols) == 1
    assert symbols[0].kind == "function"
    assert symbols[0].signature.startswith("async def fetch")


def test_skips_local_function_inside_function():
    source = (
        "def outer():\n"
        "    def inner():\n"
        "        pass\n"
        "    return inner\n"
    )
    symbols, _ = python.scan("src/x.py", source)
    names = {s.name for s in symbols}
    assert names == {"outer"}


def test_syntax_error_reported_not_raised():
    source = "def broken(:\n"
    symbols, errors = python.scan("src/broken.py", source)
    assert symbols == []
    assert len(errors) == 1
    assert "SyntaxError" in errors[0].message
    assert errors[0].path == "src/broken.py"


def test_symbol_to_json_drops_empty_fields():
    source = "def f(): pass\n"
    symbols, _ = python.scan("a.py", source)
    j = symbols[0].to_json()
    assert "parent" not in j  # was None
    assert "extra" not in j  # was empty
    assert j["name"] == "f"
    assert j["kind"] == "function"
