"""
Direct execution of the AST using C semantics.
"""
import sys
from functools import singledispatch

from ast_nodes import (
    Index, SizeOfType, SizeOfExpr,
    Group, Program, VarDecl, FuncDecl, Block, If, While, For, DoWhile, Break,
    Continue, Return, Print, ExprStmt, Assign, CompoundAssign, IncDec, BinOp,
    LogicalOp, UnaryOp, Ternary, Call, Id, Const, StringConst,
)
from constants import ArrayType, ValueType, CType, DOUBLE_OUTPUT_PRECISION, ENTRY_POINT, MAX_CALL_DEPTH, MAX_STEPS
from errors import error_prefix, ExecutionLimitExceeded, RuntimeErrorInProgram, SemanticError

# Each interpreted C call costs several Python frames, so the default limit of
# 1000 would be hit long before MAX_CALL_DEPTH.
sys.setrecursionlimit(20_000)


Value = int | float | list


def convert(value: Value, type_name: ValueType) -> Value:
    """
    Applies a C conversion to `value` on its way into a slot of `type_name`.
    Assignment, parameter passing and `return` all convert: a double stored in
    an int is truncated toward zero, an int stored in a double widens.
    """
    if isinstance(type_name, ArrayType):
        # An array is passed and stored by reference; there is nothing to
        # convert, and converting would copy it.
        return value
    if isinstance(value, list):
        raise RuntimeErrorInProgram("масив не можна перетворити на число")
    if type_name == CType.DOUBLE:
        return float(value)
    return int(value)  # int() truncates toward zero, as C does


def new_array(array_type: ArrayType) -> list:
    """A freshly declared array. C leaves it uninitialised; we start at zero,
    the same as a scalar without an initialiser."""
    zero = 0.0 if array_type.element == CType.DOUBLE else 0
    return [zero] * (array_type.length or 0)


def number_operand(node, value: Value) -> int | float:
    """
    A value used as a number.

    An array can only reach a numeric position if an earlier pass let it
    through, so this reports that as a program error rather than letting Python
    raise something unrecognisable.
    """
    if isinstance(value, list):
        raise RuntimeErrorInProgram(
            f"{error_prefix(node)}масив не можна використати як окреме значення"
        )
    return value


def array_operand(node, value: Value) -> list:
    """
    The list a subscript applies to.

    Type inference has already proved the base is an array; narrowing it again
    here keeps that fact visible to a reader and to a type checker, and turns a
    bug in an earlier pass into a clear message instead of a Python TypeError.
    """
    if not isinstance(value, list):
        raise RuntimeErrorInProgram(f"{error_prefix(node)}індексувати можна лише масив")
    return value


def subscript_value(node, value: Value) -> int:
    """The integer a subscript evaluates to; inference has already checked it."""
    if not isinstance(value, int):
        raise RuntimeErrorInProgram(f"{error_prefix(node)}індекс масиву має бути цілим")
    return value


def checked_index(container: list, index: int, node) -> int:
    """
    Validates a subscript.

    C does not check, and reading out of bounds is undefined; Python would
    silently wrap a negative index round to the end and raise only past the
    top. Neither is reproducible, so both back ends refuse instead.
    """
    if index < 0 or index >= len(container):
        raise RuntimeErrorInProgram(
            f"{error_prefix(node)}індекс {index} поза межами масиву "
            f"довжини {len(container)}"
        )
    return index


def format_value(value: Value) -> str:
    """Renders a value the way `print` shows it."""
    if isinstance(value, float):
        return f"{value:.{DOUBLE_OUTPUT_PRECISION}f}"
    if isinstance(value, list):
        raise RuntimeErrorInProgram("масив не можна надрукувати як число")
    return str(int(value))


def c_divide(left, right):
    """Truncating for two integers, ordinary division otherwise, as in C."""
    if right == 0:
        raise RuntimeErrorInProgram("Ділення на нуль")
    if isinstance(left, float) or isinstance(right, float):
        return left / right
    quotient = abs(left) // abs(right)
    return quotient if (left < 0) == (right < 0) else -quotient


def c_modulo(left: int, right: int) -> int:
    if right == 0:
        raise RuntimeErrorInProgram("Ділення на нуль (операція %)")
    return left - c_divide(left, right) * right # type: ignore


BINARY_OPERATORS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": c_divide,
    "%": c_modulo,
    "==": lambda a, b: int(a == b),
    "!=": lambda a, b: int(a != b),
    "<": lambda a, b: int(a < b),
    ">": lambda a, b: int(a > b),
    "<=": lambda a, b: int(a <= b),
    ">=": lambda a, b: int(a >= b),
    "&": lambda a, b: a & b,
    "|": lambda a, b: a | b,
    "^": lambda a, b: a ^ b,
    "<<": lambda a, b: a << b,
    ">>": lambda a, b: a >> b,
}

UNARY_OPERATORS = {
    "-": lambda a: -a,
    "!": lambda a: int(not a),
    "~": lambda a: ~a,
}


class _ReturnSignal(Exception):
    """Unwinds execution back to the enclosing function call."""

    def __init__(self, value):
        self.value = value


class _BreakSignal(Exception):
    """Unwinds execution out of the innermost loop."""


class _ContinueSignal(Exception):
    """Unwinds execution to the next iteration of the innermost loop."""


class Scope:
    """One lexical scope: a function call frame or a `{ ... }` block."""

    def __init__(self, parent: "Scope | None" = None):
        self.variables: dict[str, Value] = {}
        self.types: dict[str, ValueType] = {}
        self.parent = parent

    def declare(self, name: str, value: Value, type_name: ValueType = CType.INT) -> None:
        """Introduces `name` in *this* scope, shadowing any outer one."""
        if name in self.variables:
            raise SemanticError(f"Повторне оголошення змінної '{name}'")
        self.types[name] = type_name
        self.variables[name] = convert(value, type_name)

    def type_of(self, name: str) -> ValueType:
        scope = self._find(name)
        if scope is None:
            raise RuntimeErrorInProgram(f"Використання неоголошеної змінної '{name}'")
        return scope.types[name]

    def get(self, name: str) -> Value:
        scope = self._find(name)
        if scope is None:
            raise RuntimeErrorInProgram(f"Використання неоголошеної змінної '{name}'")
        return scope.variables[name]

    def set(self, name: str, value) -> None:
        scope = self._find(name)
        if scope is None:
            raise RuntimeErrorInProgram(f"Присвоєння неоголошеній змінній '{name}'")
        scope.variables[name] = convert(value, scope.types.get(name, CType.INT))

    def _find(self, name: str) -> "Scope | None":
        scope: Scope | None = self
        while scope is not None:
            if name in scope.variables:
                return scope
            scope = scope.parent
        return None


class Interpreter:
    """
    Executes a parsed Program, collecting everything printed by the
    program's own `print(...)` statements.
    """

    def __init__(self, program: Program, types=None, max_steps: int = MAX_STEPS):
        self._functions: dict[str, FuncDecl] = {}
        for declaration in program.declarations:
            if isinstance(declaration, FuncDecl):
                if declaration.name in self._functions:
                    raise SemanticError(f"Повторне оголошення функції '{declaration.name}'")
                self._functions[declaration.name] = declaration

        self._types = types
        self._global_scope = Scope()
        self.output_lines: list[str] = []
        self._steps = 0
        self._depth = 0
        self._max_steps = max_steps

        # Evaluate global variable declarations immediately
        for declaration in program.declarations:
            if isinstance(declaration, VarDecl):
                _execute_statement(declaration, self._global_scope, self)

    def size_of(self, node) -> int:
        return self._types.size_of(node) # type: ignore

    def type_of(self, node) -> str:
        return self._types.type_of(node) if self._types is not None else CType.INT

    def count_step(self) -> None:
        self._steps += 1
        if self._steps > self._max_steps:
            raise ExecutionLimitExceeded(
                f"Перевищено ліміт у {self._max_steps} кроків виконання — "
                "ймовірно, програма зациклилась"
            )

    def run(self, entry_point: str = ENTRY_POINT) -> Value:
        if entry_point not in self._functions:
            raise SemanticError(f"У програмі немає функції '{entry_point}'")
        if self._functions[entry_point].params:
            raise SemanticError(f"Функція '{entry_point}' не повинна мати параметрів")
        return self.call_function(entry_point, [])

    def call_function(self, name: str, argument_values: list[Value]) -> Value:
        function = self._functions.get(name)
        if function is None:
            raise RuntimeErrorInProgram(f"Виклик неоголошеної функції '{name}'")
        if len(argument_values) != len(function.params):
            raise SemanticError(
                f"Функція '{name}' очікує {len(function.params)} аргумент(ів), "
                f"передано {len(argument_values)}"
            )

        self._depth += 1
        if self._depth > MAX_CALL_DEPTH:
            self._depth -= 1
            raise ExecutionLimitExceeded(
                f"Перевищено максимальну глибину рекурсії ({MAX_CALL_DEPTH})"
            )

        scope = Scope(parent=self._global_scope)
        for param, value in zip(function.params, argument_values):
            scope.declare(param.name, value, param.type)
        try:
            _execute_statement(function.body, scope, self)
        except _ReturnSignal as signal:
            return convert(signal.value, function.return_type) if function.return_type != CType.VOID else 0
        finally:
            self._depth -= 1
        return 0


@singledispatch
def _execute_statement(node, scope: Scope, interpreter: Interpreter) -> None:
    raise TypeError(f"No interpreter rule for statement node {type(node).__name__}")


@_execute_statement.register(Block)
def _execute_block(node: Block, scope: Scope, interpreter: Interpreter) -> None:
    block_scope = Scope(parent=scope)
    for statement in node.statements:
        interpreter.count_step()
        _execute_statement(statement, block_scope, interpreter)


@_execute_statement.register(VarDecl)
def _execute_var_decl(node: VarDecl, scope: Scope, interpreter: Interpreter) -> None:
    if isinstance(node.type, ArrayType):
        scope.declare(node.name, new_array(node.type), node.type)
        return
    value = _evaluate_expression(node.value, scope, interpreter) if node.value is not None else 0
    scope.declare(node.name, value, node.type)


@_execute_statement.register(ExprStmt)
def _execute_expr_stmt(node: ExprStmt, scope: Scope, interpreter: Interpreter) -> None:
    _evaluate_expression(node.expression, scope, interpreter)


@_execute_statement.register(Print)
def _execute_print(node: Print, scope: Scope, interpreter: Interpreter) -> None:
    if isinstance(node.value, StringConst):
        interpreter.output_lines.append(node.value.value)
        return
    value = _evaluate_expression(node.value, scope, interpreter)
    interpreter.output_lines.append(format_value(value))


@_execute_statement.register(If)
def _execute_if(node: If, scope: Scope, interpreter: Interpreter) -> None:
    if _evaluate_expression(node.condition, scope, interpreter):
        _execute_statement(node.then_branch, scope, interpreter)
    elif node.else_branch is not None:
        _execute_statement(node.else_branch, scope, interpreter)


@_execute_statement.register(While)
def _execute_while(node: While, scope: Scope, interpreter: Interpreter) -> None:
    while _evaluate_expression(node.condition, scope, interpreter):
        interpreter.count_step()
        try:
            _execute_statement(node.body, scope, interpreter)
        except _ContinueSignal:
            continue
        except _BreakSignal:
            break


@_execute_statement.register(DoWhile)
def _execute_do_while(node: DoWhile, scope: Scope, interpreter: Interpreter) -> None:
    while True:
        interpreter.count_step()
        try:
            _execute_statement(node.body, scope, interpreter)
        except _ContinueSignal:
            pass  # `continue` in a do-while still reaches the condition
        except _BreakSignal:
            break
        if not _evaluate_expression(node.condition, scope, interpreter):
            break


@_execute_statement.register(For)
def _execute_for(node: For, scope: Scope, interpreter: Interpreter) -> None:
    # The init part gets a scope of its own so `for (int i = ...)` does not leak
    # `i` into the enclosing block, exactly as in C.
    loop_scope = Scope(parent=scope)
    for statement in node.init:
        _execute_statement(statement, loop_scope, interpreter)

    while node.condition is None or _evaluate_expression(node.condition, loop_scope, interpreter):
        interpreter.count_step()
        try:
            _execute_statement(node.body, loop_scope, interpreter)
        except _ContinueSignal:
            pass  # `continue` skips the rest of the body but still runs the step
        except _BreakSignal:
            break
        if node.step is not None:
            _evaluate_expression(node.step, loop_scope, interpreter)


@_execute_statement.register(Break)
def _execute_break(node: Break, scope: Scope, interpreter: Interpreter) -> None:
    raise _BreakSignal()


@_execute_statement.register(Continue)
def _execute_continue(node: Continue, scope: Scope, interpreter: Interpreter) -> None:
    raise _ContinueSignal()


@_execute_statement.register(Return)
def _execute_return(node: Return, scope: Scope, interpreter: Interpreter) -> None:
    value = _evaluate_expression(node.value, scope, interpreter) if node.value is not None else 0
    raise _ReturnSignal(value)


@singledispatch
def _evaluate_expression(node, scope: Scope, interpreter: Interpreter) -> Value:
    raise TypeError(f"No interpreter rule for expression node {type(node).__name__}")


@_evaluate_expression.register(Const)
def _evaluate_const(node: Const, scope: Scope, interpreter: Interpreter) -> Value:
    return node.value


@_evaluate_expression.register(Id)
def _evaluate_id(node: Id, scope: Scope, interpreter: Interpreter) -> Value:
    return scope.get(node.name)


@_evaluate_expression.register(Group)
def _evaluate_group(node: Group, scope: Scope, interpreter: Interpreter) -> Value:
    return _evaluate_expression(node.expression, scope, interpreter)


def _resolve_target(node, scope: Scope, interpreter: Interpreter):
    """
    Locates what an assignment writes to, evaluating any subscript exactly once.

    Returns a pair of functions, so `a[f()] += 1` calls `f` a single time just
    as C requires.
    """
    if isinstance(node, Index):
        base = node.base
        assert isinstance(base, Id)  # the grammar allows nothing else as a base
        container = array_operand(base, _evaluate_expression(base, scope, interpreter))
        index = checked_index(
            container,
            subscript_value(node.index, _evaluate_expression(node.index, scope, interpreter)),
            node,
        )
        declared = scope.type_of(base.name)
        element_type = declared.element if isinstance(declared, ArrayType) else CType.INT

        def read() -> Value:
            return container[index]

        def write(value: Value) -> Value:
            container[index] = convert(value, element_type)
            return container[index]

        return read, write

    assert isinstance(node, Id)  # the only other lvalue the grammar produces
    name = node.name

    def read_name() -> Value:
        return scope.get(name)

    def write_name(value: Value) -> Value:
        scope.set(name, value)
        return scope.get(name)

    return read_name, write_name


@_evaluate_expression.register(Index)
def _evaluate_index(node: Index, scope: Scope, interpreter: Interpreter) -> Value:
    container = array_operand(node.base, _evaluate_expression(node.base, scope, interpreter))
    index = subscript_value(node.index, _evaluate_expression(node.index, scope, interpreter))
    return container[checked_index(container, index, node)]


@_evaluate_expression.register(SizeOfType)
def _evaluate_sizeof_type(node: SizeOfType, scope: Scope, interpreter: Interpreter) -> int:
    return interpreter.size_of(node)


@_evaluate_expression.register(SizeOfExpr)
def _evaluate_sizeof_expr(node: SizeOfExpr, scope: Scope, interpreter: Interpreter) -> int:
    # The operand is deliberately not evaluated: `sizeof` looks at its type.
    return interpreter.size_of(node)


@_evaluate_expression.register(Assign)
def _evaluate_assign(node: Assign, scope: Scope, interpreter: Interpreter) -> Value:
    value = _evaluate_expression(node.value, scope, interpreter)
    _, write = _resolve_target(node.target, scope, interpreter)
    return write(value)


@_evaluate_expression.register(BinOp)
def _evaluate_binop(node: BinOp, scope: Scope, interpreter: Interpreter) -> Value:
    interpreter.count_step()
    left = _evaluate_expression(node.left, scope, interpreter)
    right = _evaluate_expression(node.right, scope, interpreter)
    return BINARY_OPERATORS[node.operator](left, right)


@_evaluate_expression.register(UnaryOp)
def _evaluate_unary(node: UnaryOp, scope: Scope, interpreter: Interpreter) -> Value:
    value = _evaluate_expression(node.operand, scope, interpreter)
    return UNARY_OPERATORS[node.operator](value)


@_evaluate_expression.register(LogicalOp)
def _evaluate_logical(node: LogicalOp, scope: Scope, interpreter: Interpreter) -> int:
    interpreter.count_step()
    left = _evaluate_expression(node.left, scope, interpreter)

    # Short-circuit: the right operand is only evaluated when it can still change
    # the answer, so its side effects follow C.
    if node.operator == "&&":
        if not left:
            return 0
    elif node.operator == "||":
        if left:
            return 1
    else:
        raise TypeError(f"Unknown logical operator {node.operator!r}")

    return int(bool(_evaluate_expression(node.right, scope, interpreter)))


@_evaluate_expression.register(Ternary)
def _evaluate_ternary(node: Ternary, scope: Scope, interpreter: Interpreter) -> Value:
    interpreter.count_step()
    branch = node.if_true if _evaluate_expression(node.condition, scope, interpreter) else node.if_false
    value = _evaluate_expression(branch, scope, interpreter)
    return convert(value, CType(interpreter.type_of(node)))


@_evaluate_expression.register(CompoundAssign)
def _evaluate_compound_assign(node: CompoundAssign, scope: Scope, interpreter: Interpreter) -> Value:
    read, write = _resolve_target(node.target, scope, interpreter)
    operand = _evaluate_expression(node.value, scope, interpreter)
    return write(BINARY_OPERATORS[node.operator](read(), operand))


@_evaluate_expression.register(IncDec)
def _evaluate_inc_dec(node: IncDec, scope: Scope, interpreter: Interpreter) -> Value:
    read, write = _resolve_target(node.target, scope, interpreter)
    previous = number_operand(node.target, read())
    updated = write(previous + 1 if node.operator == "+" else previous - 1)
    return updated if node.is_prefix else previous


@_evaluate_expression.register(Call)
def _evaluate_call(node: Call, scope: Scope, interpreter: Interpreter) -> Value:
    argument_values = [_evaluate_expression(arg, scope, interpreter) for arg in node.arguments]
    return interpreter.call_function(node.name, argument_values)