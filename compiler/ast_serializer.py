"""
AST to JSON serialization.
"""
import dataclasses

from ast_nodes import (
    Assign, BinOp, Call, CompoundAssign, Const, FuncDecl, FuncProto, Group, Id,
    IncDec, LogicalOp, Param, StringConst, UnaryOp, VarDecl,
)


def _node_label(node) -> str | None:
    if isinstance(node, Const):
        return str(node.value)
    if isinstance(node, StringConst):
        return repr(node.value)
    if isinstance(node, (VarDecl, Param)):
        qualifier = "const " if node.is_const else ""
        return f"{qualifier}{node.type} {node.name}"
    if isinstance(node, (FuncDecl, FuncProto)):
        return f"{node.return_type} {node.name}"
    if isinstance(node, (Id, Assign, Call)):
        return node.name
    if isinstance(node, CompoundAssign):
        return f"{node.name} {node.operator}="
    if isinstance(node, IncDec):
        step = f"{node.operator}{node.operator}"
        return f"{step}{node.name}" if node.is_prefix else f"{node.name}{step}"
    if isinstance(node, (BinOp, UnaryOp, LogicalOp)):
        return node.operator
    if isinstance(node, Group):
        return "( )"
    return None


def _child_nodes(node) -> list[tuple[str, object]]:
    """Returns (role, child) pairs in declaration order."""
    children: list[tuple[str, object]] = []
    for field in dataclasses.fields(node):
        value = getattr(node, field.name)
        if isinstance(value, list):
            for item in value:
                if dataclasses.is_dataclass(item):
                    children.append((field.name, item))
        elif dataclasses.is_dataclass(value):
            children.append((field.name, value))
    return children


def ast_to_dict(node, role: str | None = None) -> dict | None:
    if node is None:
        return None
    return {
        "type": type(node).__name__,
        "label": _node_label(node),
        "role": role,
        "children": [
            ast_to_dict(child, child_role) for child_role, child in _child_nodes(node)
        ],
    }