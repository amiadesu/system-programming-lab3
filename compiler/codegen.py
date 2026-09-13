"""
Translation of the AST into Python source text.
"""
from functools import singledispatch

from ast_nodes import (
    Group, Program, VarDecl, FuncDecl, Block, If, While, Return, Print,
    ExprStmt, Assign, BinOp, UnaryOp, Call, Id, Const,
)
from name_resolution import NameResolution, resolve_names

INDENT_UNIT = "    "

# Python precedence levels, lowest binds loosest.
#
# For left-associative operations right precedence is one higher than left precedence, 
# so that the right operand of a left-associative operator is parenthesised when it has the same operator.
#
# For right-associative operations it is the other way around.
#
# For comparison operators, both sides are parenthesised when they have the same operator, 
# to prevent Python from chaining them.
PREC_WALRUS = 0
PREC_COMPARISON = 1
PREC_ADDITIVE = 2
PREC_MULTIPLICATIVE = 3
PREC_UNARY = 4
PREC_ATOM = 5

COMPARISON_OPERATORS = {"==", "!=", "<", ">", "<=", ">="}

PREC_DEFAULT_MINIMUM = PREC_COMPARISON
PREC_INSIDE_PARENTHESES = PREC_WALRUS # absolute minimum precedence

PREAMBLE = (
    "import math\n"
)


def generate_python(program: Program, resolution: NameResolution | None = None) -> str:
    resolution = resolution if resolution is not None else resolve_names(program)
    context = _Context(resolution)
    body = _generate_statement(program, 0, context)
    preamble = PREAMBLE if context.uses_math else ""
    return preamble + body


class _Context:
    """Per-translation state: replaces the module-level globals of the old
    implementation so two translations can never interfere."""

    def __init__(self, resolution: NameResolution):
        self.resolution = resolution
        self.uses_math = False
        self.current_function: str | None = None

    def name_of(self, node) -> str:
        return self.resolution.name_of(node)

    def name_of_function(self, c_name: str) -> str:
        return self.resolution.name_of_function(c_name)


def _pad(indent: int) -> str:
    return INDENT_UNIT * indent


def _generate_statement_block(statements: list, indent: int, context: _Context) -> str:
    body = "".join(_generate_statement(stmt, indent, context) for stmt in statements)
    if not body.strip():
        return _pad(indent) + "pass\n"
    return body


@singledispatch
def _generate_statement(node, indent: int, context: _Context) -> str:
    raise TypeError(f"No Python codegen rule for statement node {type(node).__name__}")


@_generate_statement.register(Program)
def _generate_program(node: Program, indent: int, context: _Context) -> str:
    return _generate_statement_block(node.declarations, indent, context)


@_generate_statement.register(Block)
def _generate_block(node: Block, indent: int, context: _Context) -> str:
    return _generate_statement_block(node.statements, indent, context)


@_generate_statement.register(FuncDecl)
def _generate_func_decl(node: FuncDecl, indent: int, context: _Context) -> str:
    param_names = ", ".join(context.name_of(param) for param in node.params)
    header = f"{_pad(indent)}def {context.name_of_function(node.name)}({param_names}):\n"

    previous_function = context.current_function
    context.current_function = node.name
    body = _generate_statement(node.body, indent + 1, context)
    context.current_function = previous_function

    assigned_globals = context.resolution.assigned_globals.get(node.name, [])
    global_stmt = (
        f"{_pad(indent + 1)}global {', '.join(assigned_globals)}\n"
        if assigned_globals
        else ""
    )
    return "\n" + header + global_stmt + body


@_generate_statement.register(VarDecl)
def _generate_var_decl(node: VarDecl, indent: int, context: _Context) -> str:
    name = context.name_of(node)
    if node.value is not None:
        return f"{_pad(indent)}{name} = {_int_normalised(node.value, context)}\n"
    return f"{_pad(indent)}{name} = 0\n"


@_generate_statement.register(If)
def _generate_if(node: If, indent: int, context: _Context) -> str:
    text = f"{_pad(indent)}if {_expression(node.condition, PREC_DEFAULT_MINIMUM, context)}:\n"
    text += _generate_statement(node.then_branch, indent + 1, context)
    if node.else_branch is not None and node.else_branch.statements:
        text += f"{_pad(indent)}else:\n"
        text += _generate_statement(node.else_branch, indent + 1, context)
    return text


@_generate_statement.register(While)
def _generate_while(node: While, indent: int, context: _Context) -> str:
    text = f"{_pad(indent)}while {_expression(node.condition, PREC_DEFAULT_MINIMUM, context)}:\n"
    text += _generate_statement(node.body, indent + 1, context)
    return text


@_generate_statement.register(Return)
def _generate_return(node: Return, indent: int, context: _Context) -> str:
    if node.value is None:
        return f"{_pad(indent)}return\n"
    return f"{_pad(indent)}return {_int_normalised(node.value, context)}\n"


@_generate_statement.register(Print)
def _generate_print(node: Print, indent: int, context: _Context) -> str:
    return f"{_pad(indent)}print({_int_normalised(node.value, context)})\n"


@_generate_statement.register(ExprStmt)
def _generate_expr_stmt(node: ExprStmt, indent: int, context: _Context) -> str:
    if isinstance(node.expression, Assign):
        target = context.name_of(node.expression)
        value = _int_normalised(node.expression.value, context)
        return f"{_pad(indent)}{target} = {value}\n"
    return f"{_pad(indent)}{_expression(node.expression, PREC_DEFAULT_MINIMUM, context)}\n"


def _yields_int(node) -> bool:
    """
    Returns True when the generated Python for `node` is certainly an `int`.
    """
    if isinstance(node, Group):
        return _yields_int(node.expression)
    if isinstance(node, BinOp):
        return node.operator not in COMPARISON_OPERATORS
    return True


def _int_normalised(node, context: _Context) -> str:
    """
    Renders `node` so that the result is an `int` and never a `bool`.
    """
    if _yields_int(node):
        return _expression(node, PREC_INSIDE_PARENTHESES, context)
    return f"int({_expression(node, PREC_INSIDE_PARENTHESES, context)})"


def _expression(node, minimum_precedence: int, context: _Context) -> str:
    """
    Renders `node`, adding parentheses if its precedence is too low here.
    """
    text, precedence = _generate_expression(node, context)
    if precedence < minimum_precedence:
        return f"({text})"
    return text


@singledispatch
def _generate_expression(node, context: _Context) -> tuple[str, int]:
    raise TypeError(f"No Python codegen rule for expression node {type(node).__name__}")


@_generate_expression.register(Group)
def _generate_group_expr(node: Group, context: _Context) -> tuple[str, int]:
    return f"({_expression(node.expression, PREC_INSIDE_PARENTHESES, context)})", PREC_ATOM


@_generate_expression.register(Assign)
def _generate_assign_expr(node: Assign, context: _Context) -> tuple[str, int]:
    target = context.name_of(node)
    value = _int_normalised(node.value, context)
    return f"{target} := {value}", PREC_WALRUS


@_generate_expression.register(BinOp)
def _generate_binop_expr(node: BinOp, context: _Context) -> tuple[str, int]:
    if node.operator == "/":
        context.uses_math = True
        left = _expression(node.left, PREC_DEFAULT_MINIMUM, context)
        right = _expression(node.right, PREC_DEFAULT_MINIMUM, context)
        return f"math.trunc({left} / {right})", PREC_ATOM # Best equivalent to C's integer division, which truncates toward zero.

    if node.operator == "%":
        context.uses_math = True
        left = _expression(node.left, PREC_INSIDE_PARENTHESES, context)
        right = _expression(node.right, PREC_INSIDE_PARENTHESES, context)
        return f"int(math.fmod({left}, {right}))", PREC_ATOM # Best equivalent to C's integer modulo, which truncates toward zero.

    if node.operator in COMPARISON_OPERATORS:
        # Requiring PREC_ADDITIVE on both sides parenthesises any nested
        # comparison, which is what stops Python from chaining them.
        left = _expression(node.left, PREC_ADDITIVE, context)
        right = _expression(node.right, PREC_ADDITIVE, context)
        return f"{left} {node.operator} {right}", PREC_COMPARISON

    if node.operator in ("+", "-"):
        left = _expression(node.left, PREC_ADDITIVE, context)
        right = _expression(node.right, PREC_MULTIPLICATIVE, context)
        return f"{left} {node.operator} {right}", PREC_ADDITIVE

    if node.operator == "*":
        left = _expression(node.left, PREC_MULTIPLICATIVE, context)
        right = _expression(node.right, PREC_UNARY, context)
        return f"{left} * {right}", PREC_MULTIPLICATIVE

    raise TypeError(f"Unknown binary operator {node.operator!r}")


@_generate_expression.register(UnaryOp)
def _generate_unary_expr(node: UnaryOp, context: _Context) -> tuple[str, int]:
    return f"-{_expression(node.operand, PREC_ATOM, context)}", PREC_UNARY


@_generate_expression.register(Call)
def _generate_call_expr(node: Call, context: _Context) -> tuple[str, int]:
    args = ", ".join(_int_normalised(arg, context) for arg in node.arguments)
    return f"{context.name_of_function(node.name)}({args})", PREC_ATOM


@_generate_expression.register(Id)
def _generate_id_expr(node: Id, context: _Context) -> tuple[str, int]:
    return context.name_of(node), PREC_ATOM


@_generate_expression.register(Const)
def _generate_const_expr(node: Const, context: _Context) -> tuple[str, int]:
    return str(node.value), PREC_ATOM