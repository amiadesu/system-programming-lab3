"""
Checks that are about the *meaning* of the program rather than its shape.

Three rules are enforced here, all of them cases where the AST interpreter and
the generated Python would otherwise quietly disagree:

* a non-void function must return a value on every path, and a void one must
  not return a value at all;
* `break` and `continue` may only appear inside a loop;
* a prototype must be followed by a matching definition;
* a `const` variable may not be assigned to after its declaration;
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
    Assign, BinOp, Block, Break, Call, CompoundAssign, Const, Continue,
    DoWhile, ExprStmt, For, FuncDecl, FuncProto, Group, Id, If, IncDec,
    LogicalOp, Print, Program, Return, StringConst, Ternary, UnaryOp, VarDecl,
    While,
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

    _check_prototypes(program, functions)

    for declaration in program.declarations:
        if isinstance(declaration, FuncProto):
            continue
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


def _check_prototypes(program: Program, functions: dict[str, FuncDecl]) -> None:
    """A prototype only promises a definition; without a linker it has to keep
    that promise in the same file, and agree with it."""
    seen: set[str] = set()
    for declaration in program.declarations:
        if not isinstance(declaration, FuncProto):
            continue
        if declaration.name in seen:
            raise SemanticError(f"{_at(declaration)}повторний прототип '{declaration.name}'")
        seen.add(declaration.name)

        definition = functions.get(declaration.name)
        if definition is None:
            raise SemanticError(
                f"{_at(declaration)}функцію '{declaration.name}' оголошено, але не визначено"
            )
        if definition.return_type != declaration.return_type:
            raise SemanticError(
                f"{_at(declaration)}прототип '{declaration.name}' повертає "
                f"{declaration.return_type}, а визначення — {definition.return_type}"
            )
        prototype_types = [param.type for param in declaration.params]
        definition_types = [param.type for param in definition.params]
        if prototype_types != definition_types:
            raise SemanticError(
                f"{_at(declaration)}прототип '{declaration.name}' не збігається з "
                "визначенням за типами параметрів"
            )


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
        return _is_constant_true(node.condition) and not _contains_break(node.body)
    if isinstance(node, For):
        endless = node.condition is None or _is_constant_true(node.condition)
        return endless and not _contains_break(node.body)
    if isinstance(node, DoWhile):
        # The body always runs once, so a body that returns is enough.
        if _always_returns(node.body):
            return True
        return _is_constant_true(node.condition) and not _contains_break(node.body)
    return False


def _contains_break(node) -> bool:
    """
    True when `node` holds a `break` that belongs to the enclosing loop.
    """
    if isinstance(node, Break):
        return True
    if isinstance(node, Block):
        return any(_contains_break(statement) for statement in node.statements)
    if isinstance(node, If):
        return _contains_break(node.then_branch) or (
            node.else_branch is not None and _contains_break(node.else_branch)
        )
    return False


def _is_constant_true(node) -> bool:
    if isinstance(node, Group):
        return _is_constant_true(node.expression)
    return isinstance(node, Const) and node.value != 0


def _check_statement(
    node,
    function: FuncDecl,
    functions: dict[str, FuncDecl],
    result: AnalysisResult,
    in_loop: bool = False,
) -> None:
    if isinstance(node, Block):
        for statement in node.statements:
            _check_statement(statement, function, functions, result, in_loop)
    elif isinstance(node, If):
        _check_expression(node.condition, functions, result)
        _check_statement(node.then_branch, function, functions, result, in_loop)
        if node.else_branch is not None:
            _check_statement(node.else_branch, function, functions, result, in_loop)
    elif isinstance(node, While):
        _check_expression(node.condition, functions, result)
        _check_statement(node.body, function, functions, result, in_loop=True)
    elif isinstance(node, DoWhile):
        _check_statement(node.body, function, functions, result, in_loop=True)
        _check_expression(node.condition, functions, result)
    elif isinstance(node, For):
        for statement in node.init:
            _check_statement(statement, function, functions, result, in_loop)
        if node.condition is not None:
            _check_expression(node.condition, functions, result)
        if node.step is not None:
            _check_expression(node.step, functions, result)
        _check_statement(node.body, function, functions, result, in_loop=True)
    elif isinstance(node, (Break, Continue)):
        if not in_loop:
            keyword_name = "break" if isinstance(node, Break) else "continue"
            raise SemanticError(f"{_at(node)}'{keyword_name}' поза циклом")
    elif isinstance(node, VarDecl):
        if node.value is not None:
            _check_expression(node.value, functions, result)
    elif isinstance(node, Print):
        if not isinstance(node.value, StringConst):
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
        if isinstance(node.value, int):
            _warn_if_outside_int32(node.value, result)
        return

    if isinstance(node, UnaryOp) and node.operator == "-":
        literal = _unwrap_literal(node.operand)
        if literal is not None:
            _warn_if_outside_int32(-literal, result)
            return

    if isinstance(node, Call):
        _check_call(node, functions, expects_value=True)

    if isinstance(node, (Id, IncDec, StringConst)):
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
    if isinstance(node, Const) and isinstance(node.value, int):
        return node.value
    return None


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
    if isinstance(node, (BinOp, LogicalOp)):
        return [node.left, node.right]
    if isinstance(node, UnaryOp):
        return [node.operand]
    if isinstance(node, Ternary):
        return [node.condition, node.if_true, node.if_false]
    if isinstance(node, (Assign, CompoundAssign)):
        return [node.value]
    if isinstance(node, Call):
        return list(node.arguments)
    return []