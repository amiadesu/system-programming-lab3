from __future__ import annotations

from dataclasses import dataclass

from constants import CType, ValueType


@dataclass
class Program:
    declarations: list
    line: int | None = None


@dataclass
class VarDecl:
    type: ValueType
    name: str
    value: object | None = None
    is_const: bool = False
    line: int | None = None


@dataclass
class Group:
    """
    An explicit `( ... )` in the source.

    Kept in the tree on purpose: a left-to-right walk of the AST has to be able
    to reproduce the original source text, and that is impossible once explicit
    parentheses are dropped.
    """

    expression: object
    line: int | None = None


@dataclass
class Param:
    type: ValueType
    name: str
    is_const: bool = False
    line: int | None = None


@dataclass
class FuncDecl:
    return_type: CType
    name: str
    params: list[Param]
    body: "Block"
    line: int | None = None


@dataclass
class Block:
    statements: list
    line: int | None = None


@dataclass
class If:
    condition: object
    then_branch: Block
    else_branch: Block | None
    line: int | None = None


@dataclass
class While:
    condition: object
    body: Block
    line: int | None = None


@dataclass
class Return:
    value: object | None
    line: int | None = None


@dataclass
class Print:
    value: object
    line: int | None = None


@dataclass
class ExprStmt:
    expression: object
    line: int | None = None


@dataclass
class Assign:
    target: object
    value: object
    line: int | None = None


@dataclass
class BinOp:
    operator: str
    left: object
    right: object
    line: int | None = None


@dataclass
class UnaryOp:
    operator: str
    operand: object
    line: int | None = None


@dataclass
class Call:
    name: str
    arguments: list
    line: int | None = None


@dataclass
class Id:
    name: str
    line: int | None = None


@dataclass
class Const:
    value: int | float
    line: int | None = None


@dataclass
class StringConst:
    value: str
    line: int | None = None


@dataclass
class FuncProto:
    return_type: CType
    name: str
    params: list["Param"]
    line: int | None = None


@dataclass
class For:
    init: list
    condition: object | None
    step: object | None
    body: "Block"
    line: int | None = None


@dataclass
class DoWhile:
    body: "Block"
    condition: object
    line: int | None = None


@dataclass
class Break:
    line: int | None = None


@dataclass
class Continue:
    line: int | None = None


@dataclass
class LogicalOp:
    operator: str
    left: object
    right: object
    line: int | None = None


@dataclass
class Ternary:
    condition: object
    if_true: object
    if_false: object
    line: int | None = None


@dataclass
class CompoundAssign:
    operator: str
    target: object
    value: object
    line: int | None = None


@dataclass
class IncDec:
    operator: str
    target: object
    is_prefix: bool
    line: int | None = None


@dataclass
class Index:
    base: object
    index: object
    line: int | None = None


@dataclass
class SizeOfType:
    type: ValueType
    line: int | None = None


@dataclass
class SizeOfExpr:
    operand: object
    line: int | None = None


def expression_children(node) -> list:
    """
    The direct sub-expressions of an expression node, in evaluation order.
    """
    if isinstance(node, Group):
        return [node.expression]
    if isinstance(node, (BinOp, LogicalOp)):
        return [node.left, node.right]
    if isinstance(node, UnaryOp):
        return [node.operand]
    if isinstance(node, Ternary):
        return [node.condition, node.if_true, node.if_false]
    if isinstance(node, (Assign, CompoundAssign)):
        return [node.target, node.value]
    if isinstance(node, IncDec):
        return [node.target]
    if isinstance(node, Index):
        return [node.base, node.index]
    if isinstance(node, SizeOfExpr):
        return [node.operand]
    if isinstance(node, Call):
        return list(node.arguments)
    return []