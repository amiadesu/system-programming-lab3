"""
AST to JSON serialization.
"""
import dataclasses

from ast_nodes import Const, Id


def _node_label(node) -> str | None:
    if isinstance(node, Const):
        return str(node.value)
    if hasattr(node, "name"):
        return node.name
    if hasattr(node, "operator"):
        return node.operator
    return None


def _child_nodes(node) -> list:
    children = []
    for field in dataclasses.fields(node):
        value = getattr(node, field.name)
        if isinstance(value, list):
            children.extend(item for item in value if dataclasses.is_dataclass(item))
        elif dataclasses.is_dataclass(value):
            children.append(value)
    return children


def ast_to_dict(node) -> dict | None:
    if node is None:
        return None
    return {
        "type": type(node).__name__,
        "label": _node_label(node),
        "children": [ast_to_dict(child) for child in _child_nodes(node)],
    }
