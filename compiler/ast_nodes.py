from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Program:
    declarations: list


@dataclass
class VarDecl:
    type: str
    name: str
    value: object | None = None


@dataclass
class Group:
    """
    An explicit `( ... )` in the source.

    Kept in the tree on purpose: a left-to-right walk of the AST has to be able
    to reproduce the original source text, and that is impossible once explicit
    parentheses are dropped.
    """

    expression: object


@dataclass
class Param:
    type: str
    name: str


@dataclass
class FuncDecl:
    return_type: str
    name: str
    params: list[Param]
    body: "Block"


@dataclass
class Block:
    statements: list


@dataclass
class If:
    condition: object
    then_branch: Block
    else_branch: Block | None


@dataclass
class While:
    condition: object
    body: Block


@dataclass
class Return:
    value: object | None


@dataclass
class Print:
    value: object


@dataclass
class ExprStmt:
    expression: object


@dataclass
class Assign:
    name: str
    value: object


@dataclass
class BinOp:
    operator: str
    left: object
    right: object


@dataclass
class UnaryOp:
    operator: str
    operand: object


@dataclass
class Call:
    name: str
    arguments: list


@dataclass
class Id:
    name: str


@dataclass
class Const:
    value: int