from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Program:
    declarations: list
    line: int | None = None


@dataclass
class VarDecl:
    type: str
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
    type: str
    name: str
    is_const: bool = False
    line: int | None = None


@dataclass
class FuncDecl:
    return_type: str
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
    name: str
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
    return_type: str
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
    name: str
    value: object
    line: int | None = None


@dataclass
class IncDec:
    operator: str
    name: str
    is_prefix: bool
    line: int | None = None