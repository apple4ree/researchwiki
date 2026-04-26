"""Python symbol scanner — stdlib `ast`, no tree-sitter dependency.

Extracts top-level classes/functions and class methods. Skips local
functions (functions defined inside other functions). All extracted
symbols carry `confidence='verified'` because they came from a successful
AST parse.
"""

from __future__ import annotations

import ast

from researchwiki.scanner.base import ScanError, Symbol


def scan(path: str, source: str) -> tuple[list[Symbol], list[ScanError]]:
    """Scan one Python file's source. Return (symbols, errors)."""
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as e:
        return [], [ScanError(path=path, line=e.lineno, message=f"SyntaxError: {e.msg}")]

    symbols: list[Symbol] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            symbols.append(_class_symbol(path, node))
            symbols.extend(_method_symbols(path, node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(_function_symbol(path, node))

    return symbols, []


def _class_symbol(path: str, node: ast.ClassDef) -> Symbol:
    bases = ", ".join(_unparse(b) for b in node.bases)
    sig = f"class {node.name}({bases}):" if bases else f"class {node.name}:"
    return Symbol(path=path, name=node.name, kind="class", signature=sig, line=node.lineno)


def _function_symbol(path: str, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Symbol:
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    args = _stringify_args(node.args)
    ret = f" -> {_unparse(node.returns)}" if node.returns else ""
    sig = f"{prefix} {node.name}({args}){ret}:"
    return Symbol(path=path, name=node.name, kind="function", signature=sig, line=node.lineno)


def _method_symbols(path: str, cls: ast.ClassDef) -> list[Symbol]:
    out: list[Symbol] = []
    for item in cls.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            prefix = "async def" if isinstance(item, ast.AsyncFunctionDef) else "def"
            args = _stringify_args(item.args)
            ret = f" -> {_unparse(item.returns)}" if item.returns else ""
            sig = f"{prefix} {item.name}({args}){ret}:"
            out.append(Symbol(
                path=path,
                name=item.name,
                kind="method",
                signature=sig,
                line=item.lineno,
                parent=cls.name,
            ))
    return out


def _stringify_args(args: ast.arguments) -> str:
    parts: list[str] = []
    for a in args.args:
        ann = f": {_unparse(a.annotation)}" if a.annotation else ""
        parts.append(f"{a.arg}{ann}")
    if args.vararg:
        ann = f": {_unparse(args.vararg.annotation)}" if args.vararg.annotation else ""
        parts.append(f"*{args.vararg.arg}{ann}")
    for a in args.kwonlyargs:
        ann = f": {_unparse(a.annotation)}" if a.annotation else ""
        parts.append(f"{a.arg}{ann}")
    if args.kwarg:
        ann = f": {_unparse(args.kwarg.annotation)}" if args.kwarg.annotation else ""
        parts.append(f"**{args.kwarg.arg}{ann}")
    return ", ".join(parts)


def _unparse(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return "<unparseable>"
