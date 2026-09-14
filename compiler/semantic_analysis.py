"""
Checks that are about the *meaning* of the program rather than its shape.

Three rules are enforced here, all of them cases where the AST interpreter and
the generated Python would otherwise quietly disagree:

* a non-void function must return a value on every path, and a void one must
  not return a value at all;
* every call must name a declared function and pass the right number of
  arguments;
* the result of a void function may not be used as a value;
* integer literals outside the 32-bit range are reported as warnings, because
  the generated code routes `/` and `%` through floating point and is only
  exact for 32-bit operands.

Rule violations raise `SemanticError`; warnings are collected and returned.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ast_nodes import (
    Assign, BinOp, Block, Call, Const, ExprStmt, FuncDecl, Group, Id, If,
    Print, Program, Return, UnaryOp, VarDecl, While,
)
from errors import SemanticError

INT32_MIN = -(2 ** 31)
INT32_MAX = 2 ** 31 - 1


def _at(node) -> str:
    """Source position prefix for an error message, when the node has one."""
    line = getattr(node, "line", None)
    return f"Рядок {line}: " if line else ""


@dataclass
class AnalysisResult:
    warnings: list[str] = field(default_factory=list)


def analyse(program: Program) -> AnalysisResult:
    result = AnalysisResult()
    functions = {
        declaration.name: declaration
        for declaration in program.declarations
        if isinstance(declaration, FuncDecl)
    }

    for declaration in program.declarations:
        if isinstance(declaration, VarDecl):
            if declaration.value is not None:
                _check_expression(declaration.value, functions, result)
            continue

        _check_statement(declaration.body, declaration, functions, result)
        if declaration.return_type != "void" and not _always_returns(declaration.body):
            raise SemanticError(
                f"{_at(declaration)}функція '{declaration.name}' має тип "
                f"{declaration.return_type}, але не повертає значення на всіх "
                "шляхах виконання"
            )

    return result


def _always_returns(node) -> bool:
    """
    True when control cannot reach past `node` - every path hits a return.

    A `while` whose condition is a non-zero constant counts as returning: the
    loop has no normal exit, so `int f(void) { while (1) { ... return x; } }`
    is accepted, exactly as a C compiler would.
    """
    if isinstance(node, Return):
        return True
    if isinstance(node, Block):
        return any(_always_returns(statement) for statement in node.statements)
    if isinstance(node, If):
        return (
            node.else_branch is not None
            and _always_returns(node.then_branch)
            and _always_returns(node.else_branch)
        )
    if isinstance(node, While):
        return _is_constant_true(node.condition)
    return False


def _is_constant_true(node) -> bool:
    if isinstance(node, Group):
        return _is_constant_true(node.expression)
    return isinstance(node, Const) and node.value != 0


def _check_statement(node, function: FuncDecl, functions: dict[str, FuncDecl], result: AnalysisResult) -> None:
    if isinstance(node, Block):
        for statement in node.statements:
            _check_statement(statement, function, functions, result)
    elif isinstance(node, If):
        _check_expression(node.condition, functions, result)
        _check_statement(node.then_branch, function, functions, result)
        if node.else_branch is not None:
            _check_statement(node.else_branch, function, functions, result)
    elif isinstance(node, While):
        _check_expression(node.condition, functions, result)
        _check_statement(node.body, function, functions, result)
    elif isinstance(node, VarDecl):
        if node.value is not None:
            _check_expression(node.value, functions, result)
    elif isinstance(node, Print):
        _check_expression(node.value, functions, result)
    elif isinstance(node, Return):
        _check_return(node, function, functions, result)
    elif isinstance(node, ExprStmt):
        # The one position where a void call is legitimate: as a statement of
        # its own, with its value discarded.
        if isinstance(node.expression, Call):
            _check_call(node.expression, functions, expects_value=False)
            for argument in node.expression.arguments:
                _check_expression(argument, functions, result)
        else:
            _check_expression(node.expression, functions, result)
    else:
        raise TypeError(f"Невідомий вузол оператора {type(node).__name__}")


def _check_return(node: Return, function: FuncDecl, functions: dict[str, FuncDecl], result: AnalysisResult) -> None:
    if function.return_type == "void":
        if node.value is not None:
            raise SemanticError(
                f"{_at(node)}функція '{function.name}' має тип void "
                "і не може повертати значення"
            )
        return

    if node.value is None:
        raise SemanticError(
            f"{_at(node)}функція '{function.name}' має тип {function.return_type}, "
            "тому 'return' має повертати значення"
        )
    _check_expression(node.value, functions, result)


def _check_expression(node, functions: dict[str, FuncDecl], result: AnalysisResult) -> None:
    if isinstance(node, Const):
        _warn_if_outside_int32(node.value, result)
        return

    if isinstance(node, UnaryOp) and node.operator == "-":
        literal = _unwrap_literal(node.operand)
        if literal is not None:
            _warn_if_outside_int32(-literal, result)
            return

    if isinstance(node, Call):
        _check_call(node, functions, expects_value=True)

    if isinstance(node, Id):
        return

    for child in _expression_children(node):
        _check_expression(child, functions, result)


def _check_call(node: Call, functions: dict[str, FuncDecl], expects_value: bool) -> None:
    function = functions.get(node.name)
    if function is None:
        raise SemanticError(f"{_at(node)}виклик неоголошеної функції '{node.name}'")

    expected = len(function.params)
    given = len(node.arguments)
    if expected != given:
        raise SemanticError(
            f"{_at(node)}функція '{node.name}' очікує {expected} аргумент(ів), "
            f"передано {given}"
        )

    if expects_value and function.return_type == "void":
        raise SemanticError(
            f"{_at(node)}функція '{node.name}' має тип void, "
            "її результат не можна використати як значення"
        )


def _unwrap_literal(node) -> int | None:
    while isinstance(node, Group):
        node = node.expression
    return node.value if isinstance(node, Const) else None


def _warn_if_outside_int32(value: int, result: AnalysisResult) -> None:
    if INT32_MIN <= value <= INT32_MAX:
        return
    message = (
        f"Літерал {value} не вміщається в 32-бітне ціле "
        f"({INT32_MIN}..{INT32_MAX}); згенерований Python може дати інший "
        "результат для операцій / та %"
    )
    if message not in result.warnings:
        result.warnings.append(message)


def _expression_children(node) -> list:
    if isinstance(node, Group):
        return [node.expression]
    if isinstance(node, BinOp):
        return [node.left, node.right]
    if isinstance(node, UnaryOp):
        return [node.operand]
    if isinstance(node, Assign):
        return [node.value]
    if isinstance(node, Call):
        return list(node.arguments)
    return []