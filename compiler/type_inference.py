"""
Assigns a C type to every expression in the AST.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ast_nodes import (
    Assign, BinOp, Call, CompoundAssign, Const, FuncDecl, Group, Id, IncDec,
    LogicalOp, Program, StringConst, Ternary, UnaryOp,
)
from errors import SemanticError
from name_resolution import NameResolution

INT = "int"
DOUBLE = "double"
VOID = "void"

# Operators C only defines for integer operands.
INTEGER_ONLY_OPERATORS = {"%", "&", "|", "^", "<<", ">>"}

COMPARISON_OPERATORS = {"==", "!=", "<", ">", "<=", ">="}


def _at(node) -> str:
    line = getattr(node, "line", None)
    return f"Рядок {line}: " if line else ""


@dataclass
class TypeInformation:
    """Expression node -> its C type, keyed by `id()` as elsewhere."""

    expression_type: dict[int, str] = field(default_factory=dict)
    _kept_alive: list = field(default_factory=list)

    def type_of(self, node) -> str:
        return self.expression_type.get(id(node), INT)

    def _record(self, node, type_name: str) -> str:
        self.expression_type[id(node)] = type_name
        self._kept_alive.append(node)
        return type_name


def infer_types(program: Program, resolution: NameResolution) -> TypeInformation:
    information = TypeInformation()
    return_types = {
        declaration.name: declaration.return_type
        for declaration in program.declarations
        if isinstance(declaration, FuncDecl)
    }
    _Inference(resolution, return_types, information).walk_program(program)
    return information


class _Inference:
    def __init__(self, resolution: NameResolution, return_types: dict[str, str], information: TypeInformation):
        self.resolution = resolution
        self.return_types = return_types
        self.information = information

    def walk_program(self, program: Program) -> None:
        for declaration in program.declarations:
            if isinstance(declaration, FuncDecl):
                self.walk_statement(declaration.body)
            elif getattr(declaration, "value", None) is not None:
                self.type_of(declaration.value)

    def walk_statement(self, node) -> None:
        for child, is_expression in _statement_children(node):
            if is_expression:
                self.type_of(child)
            else:
                self.walk_statement(child)

    def type_of(self, node) -> str:
        record = self.information._record

        if isinstance(node, StringConst):
            return record(node, "text")

        if isinstance(node, Const):
            return record(node, DOUBLE if isinstance(node.value, float) else INT)

        if isinstance(node, Group):
            return record(node, self.type_of(node.expression))

        if isinstance(node, (Id, Assign, CompoundAssign, IncDec)):
            declaration = self.resolution.declaration_for(node)
            declared = declaration.type if declaration is not None else INT # type: ignore
            if isinstance(node, (Assign, CompoundAssign)):
                self.type_of(node.value)
            if isinstance(node, CompoundAssign):
                self._check_operand_types(node, node.operator, declared, self.type_of(node.value))
            return record(node, declared)

        if isinstance(node, Call):
            for argument in node.arguments:
                self.type_of(argument)
            return record(node, self.return_types.get(node.name, INT))

        if isinstance(node, UnaryOp):
            operand = self.type_of(node.operand)
            if node.operator == "!":
                return record(node, INT)
            if node.operator == "~" and operand == DOUBLE:
                raise SemanticError(f"{_at(node)}оператор '~' не застосовується до double")
            return record(node, operand)

        if isinstance(node, LogicalOp):
            self.type_of(node.left)
            self.type_of(node.right)
            return record(node, INT)

        if isinstance(node, Ternary):
            self.type_of(node.condition)
            branches = (self.type_of(node.if_true), self.type_of(node.if_false))
            return record(node, DOUBLE if DOUBLE in branches else INT)

        if isinstance(node, BinOp):
            left = self.type_of(node.left)
            right = self.type_of(node.right)
            self._check_operand_types(node, node.operator, left, right)
            if node.operator in COMPARISON_OPERATORS:
                return record(node, INT)
            return record(node, DOUBLE if DOUBLE in (left, right) else INT)

        raise TypeError(f"Немає правила виведення типу для вузла {type(node).__name__}")

    def _check_operand_types(self, node, operator: str, left: str, right: str) -> None:
        if operator in INTEGER_ONLY_OPERATORS and DOUBLE in (left, right):
            raise SemanticError(
                f"{_at(node)}оператор '{operator}' не застосовується до double"
            )


def _statement_children(node) -> list[tuple[object, bool]]:
    """(child, child_is_an_expression) pairs for a statement node."""
    from ast_nodes import (
        Block, Break, Continue, DoWhile, ExprStmt, For, If, Print, Return, VarDecl, While,
    )

    if isinstance(node, Block):
        return [(statement, False) for statement in node.statements]
    if isinstance(node, VarDecl):
        return [(node.value, True)] if node.value is not None else []
    if isinstance(node, ExprStmt):
        return [(node.expression, True)]
    if isinstance(node, Print):
        return [(node.value, True)]
    if isinstance(node, Return):
        return [(node.value, True)] if node.value is not None else []
    if isinstance(node, If):
        children = [(node.condition, True), (node.then_branch, False)]
        if node.else_branch is not None:
            children.append((node.else_branch, False))
        return children
    if isinstance(node, While):
        return [(node.condition, True), (node.body, False)]
    if isinstance(node, DoWhile):
        return [(node.body, False), (node.condition, True)]
    if isinstance(node, For):
        children: list[tuple[object, bool]] = [(statement, False) for statement in node.init]
        if node.condition is not None:
            children.append((node.condition, True))
        if node.step is not None:
            children.append((node.step, True))
        children.append((node.body, False))
        return children
    if isinstance(node, (Break, Continue)):
        return []
    raise TypeError(f"Немає правила виведення типу для оператора {type(node).__name__}")