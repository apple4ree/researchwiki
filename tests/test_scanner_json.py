"""Tests for the JSON top-level key scanner."""

from researchwiki.scanner import json_scanner


def test_top_level_keys_extracted():
    source = '{"batch_size": 256, "lr": 3e-4, "model": {"layers": 12}}'
    symbols, errors = json_scanner.scan("configs/train.json", source)
    assert errors == []

    by_name = {s.name: s for s in symbols}
    assert set(by_name) == {"batch_size", "lr", "model"}

    assert by_name["batch_size"].kind == "json-key"
    assert by_name["batch_size"].signature.startswith("int:")
    assert "256" in by_name["batch_size"].signature

    # Nested dict summarized but not recursed.
    assert by_name["model"].signature.startswith("object")


def test_top_level_array():
    source = "[1, 2, 3]"
    symbols, errors = json_scanner.scan("configs/list.json", source)
    assert errors == []
    assert len(symbols) == 1
    assert symbols[0].name == "<root>"
    assert symbols[0].signature.startswith("list[")


def test_invalid_json_reports_error():
    source = "{not json}"
    symbols, errors = json_scanner.scan("configs/bad.json", source)
    assert symbols == []
    assert len(errors) == 1
    assert "JSONDecodeError" in errors[0].message
