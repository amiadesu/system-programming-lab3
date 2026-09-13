"""
Direct execution of the AST.
"""
from functools import singledispatch

from ast_nodes import (
    Group, Program, VarDecl, FuncDecl, Block, If, While, Return, Print,
    ExprStmt, Assign, BinOp, UnaryOp, Call, Id, Const,
)

BINARY_OPERATORS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a // b,
    "%": lambda a, b: a % b,
    "==": lambda a, b: int(a == b),
    "!=": lambda a, b: int(a != b),
    "<": lambda a, b: int(a < b),
    ">": lambda a, b: int(a > b),
    "<=": lambda a, b: int(a <= b),
    ">=": lambda a, b: int(a >= b),
}


class _ReturnSignal(Exception):
    """Unwinds execution back to the enclosing function call."""

    def __init__(self, value):
        self.value = value


class Scope:
    """One function call's local variables."""

    def __init__(self, parent: "Scope | None" = None):
        self.variables: dict[str, int] = {}
        self.parent = parent

    def get(self, name: str) -> int:
        if name in self.variables:
            return self.variables[name]
        if self.parent is not None:
            return self.parent.get(name)
        raise NameError(f"Use of undeclared variable '{name}'")

    def set(self, name: str, value: int) -> None:
        if name in self.variables:
            self.variables[name] = value
        elif self.parent is not None and self.parent.has(name):
            self.parent.set(name, value)
        else:
            self.variables[name] = value

    def has(self, name: str) -> bool:
        if name in self.variables: return True
        return self.parent.has(name) if self.parent is not None else False


class Interpreter:
    """Executes a parsed Program, collecting everything printed by the
    program's own `print(...)` statements."""

    def __init__(self, program: Program):
        self._functions: dict[str, FuncDecl] = {
            decl.name: decl for decl in program.declarations if isinstance(decl, FuncDecl)
        }
        self._global_scope = Scope()
        self.output_lines: list[str] = []
        
        # Evaluate global variable declarations immediately
        for decl in program.declarations:
            if isinstance(decl, VarDecl):
                _execute_statement(decl, self._global_scope, self)

    def run(self, entry_point: str = "main") -> int:
        if entry_point not in self._functions:
            raise NameError(f"No '{entry_point}' function to run")
        return self.call_function(entry_point, [])

    def call_function(self, name: str, argument_values: list[int]) -> int:
        function = self._functions[name]
        scope = Scope(parent=self._global_scope)
        for param, value in zip(function.params, argument_values):
            scope.set(param.name, value)
        try:
            _execute_statement(function.body, scope, self)
        except _ReturnSignal as signal:
            return signal.value
        return 0


@singledispatch
def _execute_statement(node, scope: Scope, interpreter: Interpreter) -> None:
    raise TypeError(f"No interpreter rule for statement node {type(node).__name__}")


@_execute_statement.register(Block)
def _execute_block(node: Block, scope: Scope, interpreter: Interpreter) -> None:
    for statement in node.statements:
        _execute_statement(statement, scope, interpreter)


@_execute_statement.register(VarDecl)
def _execute_var_decl(node: VarDecl, scope: Scope, interpreter: Interpreter) -> None:
    val = _evaluate_expression(node.value, scope, interpreter) if node.value is not None else 0
    scope.set(node.name, val)


@_execute_statement.register(ExprStmt)
def _execute_expr_stmt(node: ExprStmt, scope: Scope, interpreter: Interpreter) -> None:
    _evaluate_expression(node.expression, scope, interpreter)


@_execute_statement.register(Print)
def _execute_print(node: Print, scope: Scope, interpreter: Interpreter) -> None:
    value = _evaluate_expression(node.value, scope, interpreter)
    interpreter.output_lines.append(str(value))


@_execute_statement.register(If)
def _execute_if(node: If, scope: Scope, interpreter: Interpreter) -> None:
    if _evaluate_expression(node.condition, scope, interpreter):
        _execute_statement(node.then_branch, scope, interpreter)
    elif node.else_branch is not None:
        _execute_statement(node.else_branch, scope, interpreter)


@_execute_statement.register(While)
def _execute_while(node: While, scope: Scope, interpreter: Interpreter) -> None:
    while _evaluate_expression(node.condition, scope, interpreter):
        _execute_statement(node.body, scope, interpreter)


@_execute_statement.register(Return)
def _execute_return(node: Return, scope: Scope, interpreter: Interpreter) -> None:
    value = _evaluate_expression(node.value, scope, interpreter) if node.value is not None else 0
    raise _ReturnSignal(value)


@singledispatch
def _evaluate_expression(node, scope: Scope, interpreter: Interpreter) -> int:
    raise TypeError(f"No interpreter rule for expression node {type(node).__name__}")


@_evaluate_expression.register(Const)
def _evaluate_const(node: Const, scope: Scope, interpreter: Interpreter) -> int:
    return node.value


@_evaluate_expression.register(Id)
def _evaluate_id(node: Id, scope: Scope, interpreter: Interpreter) -> int:
    return scope.get(node.name)


@_evaluate_expression.register(Group)
def _evaluate_group(node: Group, scope: Scope, interpreter: Interpreter) -> int:
    return _evaluate_expression(node.expression, scope, interpreter)


@_evaluate_expression.register(Assign)
def _evaluate_assign(node: Assign, scope: Scope, interpreter: Interpreter) -> int:
    value = _evaluate_expression(node.value, scope, interpreter)
    scope.set(node.name, value)
    return value


@_evaluate_expression.register(BinOp)
def _evaluate_binop(node: BinOp, scope: Scope, interpreter: Interpreter) -> int:
    left = _evaluate_expression(node.left, scope, interpreter)
    right = _evaluate_expression(node.right, scope, interpreter)
    return BINARY_OPERATORS[node.operator](left, right)


@_evaluate_expression.register(UnaryOp)
def _evaluate_unary(node: UnaryOp, scope: Scope, interpreter: Interpreter) -> int:
    return -_evaluate_expression(node.operand, scope, interpreter)


@_evaluate_expression.register(Call)
def _evaluate_call(node: Call, scope: Scope, interpreter: Interpreter) -> int:
    argument_values = [_evaluate_expression(arg, scope, interpreter) for arg in node.arguments]
    return interpreter.call_function(node.name, argument_values)
