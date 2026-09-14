"""
Renders an AST back as C source text.
"""
from functools import singledispatch

from ast_nodes import (
    Index, SizeOfType, SizeOfExpr,
    Assign, BinOp, Block, Break, Call, CompoundAssign, Const, Continue,
    DoWhile, ExprStmt, For, FuncDecl, FuncProto, Group, Id, If, IncDec,
    LogicalOp, Print, Program, Return, StringConst, Ternary, UnaryOp, VarDecl,
    While,
)
from constants import ArrayType, ESCAPE_SEQUENCES, INDENT_UNIT

# Inverse of the lexer's table, for putting escapes back into a literal.
_ESCAPE_BACK = {character: escape for escape, character in ESCAPE_SEQUENCES.items()}


def print_c(program: Program) -> str:
    """Returns `program` rendered as C source."""
    return _statement(program, 0)


def _pad(indent: int) -> str:
    return INDENT_UNIT * indent


def _declaration_head(node) -> str:
    qualifier = "const " if getattr(node, "is_const", False) else ""
    if isinstance(node.type, ArrayType):
        # C writes the size after the name: `int a[10]`, not `int[10] a`.
        length = node.type.length if node.type.length is not None else ""
        return f"{node.type.element} {node.name}[{length}]"
    return f"{qualifier}{node.type} {node.name}"


def _parameters(params: list) -> str:
    if not params:
        return "void"
    return ", ".join(_declaration_head(param) for param in params)


@singledispatch
def _statement(node, indent: int) -> str:
    raise TypeError(f"No C printing rule for statement node {type(node).__name__}")


@_statement.register(Program)
def _print_program(node: Program, indent: int) -> str:
    pieces = []
    for position, declaration in enumerate(node.declarations):
        if position > 0 and (
            isinstance(declaration, FuncDecl) or isinstance(node.declarations[position - 1], FuncDecl)
        ):
            pieces.append("\n")
        pieces.append(_statement(declaration, indent))
    return "".join(pieces)


@_statement.register(Block)
def _print_block(node: Block, indent: int) -> str:
    inner = "".join(_statement(statement, indent + 1) for statement in node.statements)
    return f"{_pad(indent)}{{\n{inner}{_pad(indent)}}}\n"


@_statement.register(FuncDecl)
def _print_func_decl(node: FuncDecl, indent: int) -> str:
    header = f"{_pad(indent)}{node.return_type} {node.name}({_parameters(node.params)}) "
    body = _statement(node.body, indent)
    return header + body.lstrip()


@_statement.register(FuncProto)
def _print_func_proto(node: FuncProto, indent: int) -> str:
    return f"{_pad(indent)}{node.return_type} {node.name}({_parameters(node.params)});\n"


@_statement.register(VarDecl)
def _print_var_decl(node: VarDecl, indent: int) -> str:
    return f"{_pad(indent)}{_declarator(node)};\n"


@_statement.register(ExprStmt)
def _print_expr_stmt(node: ExprStmt, indent: int) -> str:
    return f"{_pad(indent)}{_expression(node.expression)};\n"


@_statement.register(Print)
def _print_print(node: Print, indent: int) -> str:
    return f"{_pad(indent)}print({_expression(node.value)});\n"


@_statement.register(Return)
def _print_return(node: Return, indent: int) -> str:
    if node.value is None:
        return f"{_pad(indent)}return;\n"
    return f"{_pad(indent)}return {_expression(node.value)};\n"


@_statement.register(Break)
def _print_break(node: Break, indent: int) -> str:
    return f"{_pad(indent)}break;\n"


@_statement.register(Continue)
def _print_continue(node: Continue, indent: int) -> str:
    return f"{_pad(indent)}continue;\n"


@_statement.register(If)
def _print_if(node: If, indent: int) -> str:
    text = f"{_pad(indent)}if ({_expression(node.condition)}) " + _statement(node.then_branch, indent).lstrip()
    if node.else_branch is None:
        return text

    inner = node.else_branch.statements
    if len(inner) == 1 and isinstance(inner[0], If):
        # `else { if ... }` reads better written as the `else if` it came from.
        return text.rstrip("\n") + f" else " + _statement(inner[0], indent).lstrip()
    return text.rstrip("\n") + " else " + _statement(node.else_branch, indent).lstrip()


@_statement.register(While)
def _print_while(node: While, indent: int) -> str:
    return f"{_pad(indent)}while ({_expression(node.condition)}) " + _statement(node.body, indent).lstrip()


@_statement.register(DoWhile)
def _print_do_while(node: DoWhile, indent: int) -> str:
    body = _statement(node.body, indent).lstrip().rstrip("\n")
    return f"{_pad(indent)}do {body} while ({_expression(node.condition)});\n"


@_statement.register(For)
def _print_for(node: For, indent: int) -> str:
    condition = _expression(node.condition) if node.condition is not None else ""
    step = _expression(node.step) if node.step is not None else ""
    header = f"{_pad(indent)}for ({_for_init(node.init)}; {condition}; {step}) "
    return header + _statement(node.body, indent).lstrip()


def _for_init(statements: list) -> str:
    """The first clause of a `for`, which is a declaration or an expression but
    carries no semicolon of its own."""
    if not statements:
        return ""
    if isinstance(statements[0], ExprStmt):
        return ", ".join(_expression(statement.expression) for statement in statements)
    # Several declarators of one declaration became several nodes; the type is
    # written once, as it was in the source.
    head = _declarator(statements[0])
    rest = [_declarator(statement, with_type=False) for statement in statements[1:]]
    return ", ".join([head] + rest)


def _declarator(node: VarDecl, with_type: bool = True) -> str:
    name = _declaration_head(node) if with_type else node.name
    if node.value is None:
        return name
    return f"{name} = {_expression(node.value)}"


@singledispatch
def _expression(node) -> str:
    raise TypeError(f"No C printing rule for expression node {type(node).__name__}")


@_expression.register(Group)
def _print_group(node: Group) -> str:
    return f"({_expression(node.expression)})"


@_expression.register(BinOp)
def _print_binop(node: BinOp) -> str:
    return f"{_expression(node.left)} {node.operator} {_expression(node.right)}"


@_expression.register(LogicalOp)
def _print_logical(node: LogicalOp) -> str:
    return f"{_expression(node.left)} {node.operator} {_expression(node.right)}"


@_expression.register(UnaryOp)
def _print_unary(node: UnaryOp) -> str:
    return f"{node.operator}{_expression(node.operand)}"


@_expression.register(Ternary)
def _print_ternary(node: Ternary) -> str:
    return (
        f"{_expression(node.condition)} ? "
        f"{_expression(node.if_true)} : {_expression(node.if_false)}"
    )


@_expression.register(Assign)
def _print_assign(node: Assign) -> str:
    return f"{_expression(node.target)} = {_expression(node.value)}"


@_expression.register(CompoundAssign)
def _print_compound_assign(node: CompoundAssign) -> str:
    return f"{_expression(node.target)} {node.operator}= {_expression(node.value)}"


@_expression.register(IncDec)
def _print_inc_dec(node: IncDec) -> str:
    step = node.operator * 2
    target = _expression(node.target)
    return f"{step}{target}" if node.is_prefix else f"{target}{step}"


@_expression.register(Call)
def _print_call(node: Call) -> str:
    return f"{node.name}({', '.join(_expression(argument) for argument in node.arguments)})"


@_expression.register(Index)
def _print_index(node: Index) -> str:
    return f"{_expression(node.base)}[{_expression(node.index)}]"


@_expression.register(SizeOfType)
def _print_sizeof_type(node: SizeOfType) -> str:
    return f"sizeof({node.type})"


@_expression.register(SizeOfExpr)
def _print_sizeof_expr(node: SizeOfExpr) -> str:
    operand = _expression(node.operand)
    # `sizeof(a)` came through as a Group, so the space would look wrong.
    separator = "" if operand.startswith("(") else " "
    return f"sizeof{separator}{operand}"


@_expression.register(Id)
def _print_id(node: Id) -> str:
    return node.name


@_expression.register(Const)
def _print_const(node: Const) -> str:
    return repr(node.value)


@_expression.register(StringConst)
def _print_string_const(node: StringConst) -> str:
    body = "".join(f"\\{_ESCAPE_BACK[c]}" if c in _ESCAPE_BACK else c for c in node.value)
    return f'"{body}"'