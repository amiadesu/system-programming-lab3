"""
Assigns a C type to every expression in the AST.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ast_nodes import (
    Index, SizeOfType, SizeOfExpr,
    Assign, BinOp, Call, CompoundAssign, Const, FuncDecl, Group, Id, IncDec,
    LogicalOp, Program, StringConst, Ternary, UnaryOp,
)
from constants import ArrayType, TYPE_SIZES, COMPARISON_OPERATORS, CType, INTEGER_ONLY_OPERATORS
from errors import SemanticError
from errors import error_prefix as _at
from name_resolution import NameResolution


@dataclass
class TypeInformation:
    """Expression node -> its C type, keyed by `id()` as elsewhere."""

    expression_type: dict[int, CType] = field(default_factory=dict)
    sizeof_value: dict[int, int] = field(default_factory=dict)
    _kept_alive: list = field(default_factory=list)

    def type_of(self, node):
        return self.expression_type.get(id(node), CType.INT)

    def size_of(self, node) -> int:
        return self.sizeof_value[id(node)]

    def _record(self, node, type_name: CType) -> CType:
        self.expression_type[id(node)] = type_name
        self._kept_alive.append(node)
        return type_name


def infer_types(program: Program, resolution: NameResolution) -> TypeInformation:
    information = TypeInformation()
    functions = {
        declaration.name: declaration
        for declaration in program.declarations
        if isinstance(declaration, FuncDecl)
    }
    _Inference(resolution, functions, information).walk_program(program)
    return information


class _Inference:
    def __init__(self, resolution: NameResolution, functions: dict[str, FuncDecl], information: TypeInformation):
        self.resolution = resolution
        self.functions = functions
        self.information = information

    def walk_program(self, program: Program) -> None:
        for declaration in program.declarations:
            if isinstance(declaration, FuncDecl):
                self.walk_statement(declaration.body)
            elif getattr(declaration, "value", None) is not None:
                self._scalar(declaration.value)

    def walk_statement(self, node) -> None:
        for child, is_expression in _statement_children(node):
            if is_expression:
                self._scalar(child)
            else:
                self.walk_statement(child)

    def _scalar(self, node):
        """
        The type of `node`, rejecting an array.
        """
        node_type = self.type_of(node)
        if isinstance(node_type, ArrayType):
            raise SemanticError(
                f"{_at(node)}масив не можна використати як окреме значення"
            )
        return node_type

    def type_of(self, node):
        record = self.information._record

        if isinstance(node, (SizeOfType, SizeOfExpr)):
            measured = node.type if isinstance(node, SizeOfType) else self.type_of(node.operand)
            self.information.sizeof_value[id(node)] = self._size_of(node, measured)
            return record(node, CType.INT)

        if isinstance(node, Index):
            base = self.type_of(node.base)
            if not isinstance(base, ArrayType):
                raise SemanticError(f"{_at(node)}індексувати можна лише масив")
            index = self._scalar(node.index)
            if index != CType.INT:
                raise SemanticError(f"{_at(node)}індекс масиву має бути цілим")
            return record(node, base.element)

        if isinstance(node, StringConst):
            return record(node, CType.TEXT)

        if isinstance(node, Const):
            return record(node, CType.DOUBLE if isinstance(node.value, float) else CType.INT)

        if isinstance(node, Group):
            return record(node, self.type_of(node.expression))

        if isinstance(node, Id):
            declaration = self.resolution.declaration_for(node)
            return record(node, declaration.type if declaration is not None else CType.INT) # type: ignore

        if isinstance(node, (Assign, CompoundAssign, IncDec)):
            target = self.type_of(node.target)
            if isinstance(target, ArrayType):
                raise SemanticError(f"{_at(node)}масив не можна присвоювати цілком")
            if isinstance(node, (Assign, CompoundAssign)):
                value = self._scalar(node.value)
                if isinstance(node, CompoundAssign):
                    self._check_operand_types(node, node.operator, target, value)
            return record(node, target)

        if isinstance(node, Call):
            function = self.functions.get(node.name)
            parameters = function.params if function is not None else []
            for position, argument in enumerate(node.arguments):
                given = self.type_of(argument)
                expected = parameters[position].type if position < len(parameters) else None
                if expected is None:
                    self._scalar(argument)
                    continue
                if isinstance(expected, ArrayType) != isinstance(given, ArrayType):
                    raise SemanticError(
                        f"{_at(argument)}аргумент {position + 1} функції '{node.name}': "
                        f"очікується {expected}, передано {given}"
                    )
                if isinstance(expected, ArrayType) and expected.element != given.element:
                    raise SemanticError(
                        f"{_at(argument)}аргумент {position + 1} функції '{node.name}': "
                        f"очікується {expected}, передано {given}"
                    )
            return record(node, function.return_type if function is not None else CType.INT)

        if isinstance(node, UnaryOp):
            operand = self._scalar(node.operand)
            if node.operator == "!":
                return record(node, CType.INT)
            if node.operator == "~" and operand == CType.DOUBLE:
                raise SemanticError(f"{_at(node)}оператор '~' не застосовується до double")
            return record(node, operand)

        if isinstance(node, LogicalOp):
            self._scalar(node.left)
            self._scalar(node.right)
            return record(node, CType.INT)

        if isinstance(node, Ternary):
            self._scalar(node.condition)
            branches = (self._scalar(node.if_true), self._scalar(node.if_false))
            return record(node, CType.DOUBLE if CType.DOUBLE in branches else CType.INT)

        if isinstance(node, BinOp):
            left = self._scalar(node.left)
            right = self._scalar(node.right)
            self._check_operand_types(node, node.operator, left, right)
            if node.operator in COMPARISON_OPERATORS:
                return record(node, CType.INT)
            return record(node, CType.DOUBLE if CType.DOUBLE in (left, right) else CType.INT)

        raise TypeError(f"Немає правила виведення типу для вузла {type(node).__name__}")

    def _size_of(self, node, measured) -> int:
        """Bytes `sizeof` reports for `measured`."""
        if isinstance(measured, ArrayType):
            if measured.length is None:
                raise SemanticError(
                    f"{_at(node)}розмір масиву-параметра невідомий: у C він "
                    "перетворюється на вказівник"
                )
            return measured.length * TYPE_SIZES[measured.element]
        if measured not in TYPE_SIZES:
            raise SemanticError(f"{_at(node)}sizeof не застосовується до {measured}")
        return TYPE_SIZES[measured]

    def _check_operand_types(self, node, operator: str, left: CType, right: CType) -> None:
        if operator in INTEGER_ONLY_OPERATORS and CType.DOUBLE in (left, right):
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