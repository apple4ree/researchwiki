"""JSON top-level key scanner — stdlib `json`.

Extracts only top-level keys. Nested structures are summarized in the
signature line (`int`, `str`, `list[int]`, etc.) but not recursed into.
This keeps `signatures.json` from exploding for deeply nested configs.

Top-level lists and scalars produce a single synthetic symbol named
`<root>` with `kind='json-key'` and a signature describing the type.
"""

from __future__ import annotations

import json

from researchwiki.scanner.base import ScanError, Symbol


def scan(path: str, source: str) -> tuple[list[Symbol], list[ScanError]]:
    try:
        data = json.loads(source)
    except json.JSONDecodeError as e:
        return [], [ScanError(path=path, line=e.lineno, message=f"JSONDecodeError: {e.msg}")]

    if isinstance(data, dict):
        return [_key_symbol(path, key, value) for key, value in data.items()], []

    # Top-level array or scalar: emit one synthetic entry so reverse_refs
    # against this file still resolves to *something* nameable.
    return [Symbol(
        path=path,
        name="<root>",
        kind="json-key",
        signature=_type_summary(data),
        line=1,
    )], []


def _key_symbol(path: str, key: str, value: object) -> Symbol:
    return Symbol(
        path=path,
        name=key,
        kind="json-key",
        signature=_type_summary(value),
        line=0,  # stdlib json doesn't expose line positions; 0 = unknown
    )


def _type_summary(value: object) -> str:
    if isinstance(value, dict):
        n = len(value)
        return f"object ({n} keys)" if n else "object (empty)"
    if isinstance(value, list):
        if not value:
            return "list (empty)"
        # Sample first few element types.
        sample = {type(v).__name__ for v in value[:8]}
        return f"list[{', '.join(sorted(sample))}] (len={len(value)})"
    if isinstance(value, bool):
        return f"bool: {value}"
    if isinstance(value, int):
        return f"int: {value}"
    if isinstance(value, float):
        return f"float: {value}"
    if isinstance(value, str):
        truncated = value if len(value) <= 60 else value[:57] + "..."
        return f"str: {truncated!r}"
    if value is None:
        return "null"
    return type(value).__name__
