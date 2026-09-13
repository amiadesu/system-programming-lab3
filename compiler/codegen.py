from functools import singledispatch
import re

from ast_nodes import (
    Group, Program, VarDecl, Param, FuncDecl, Block, If, While, Return, Print,
    ExprStmt, Assign, BinOp, UnaryOp, Call, Id, Const,
)

INDENT_UNIT = "    "

_CURRENT_GLOBALS = []

def generate_python(program: Program) -> str:
    global _CURRENT_GLOBALS
    _CURRENT_GLOBALS = [d.name for d in program.declarations if isinstance(d, VarDecl)]
    return _generate_statement(program, indent=0)


def _pad(indent: int) -> str:
    return INDENT_UNIT * indent


def _generate_statement_block(statements: list, indent: int) -> str:
    body = "".join(_generate_statement(stmt, indent) for stmt in statements)
    if not body.strip():
        return _pad(indent) + "pass\n"
    return body


@singledispatch
def _generate_statement(node, indent: int) -> str:
    raise TypeError(f"No Python codegen rule for statement node {type(node).__name__}")


@_generate_statement.register(Program)
def _generate_program(node: Program, indent: int) -> str:
    return _generate_statement_block(node.declarations, indent)


@_generate_statement.register(Block)
def _generate_block(node: Block, indent: int) -> str:
    return _generate_statement_block(node.statements, indent)


@_generate_statement.register(FuncDecl)
def _generate_func_decl(node: FuncDecl, indent: int) -> str:
    param_names = ", ".join(param.name for param in node.params)
    header = f"{_pad(indent)}def {node.name}({param_names}):\n"

    local_vars = {param.name for param in node.params}
    for stmt in node.body.statements:
        if isinstance(stmt, VarDecl):
            local_vars.add(stmt.name)
            
    body = _generate_statement(node.body, indent + 1)
    active_globals = []
    for g in _CURRENT_GLOBALS:
        if g not in local_vars and re.search(rf'\b{g}\b', body):
            active_globals.append(g)
    global_stmt = f"{_pad(indent + 1)}global {', '.join(active_globals)}\n" if active_globals else ""

    return "\n" + header + global_stmt + body


@_generate_statement.register(VarDecl)
def _generate_var_decl(node: VarDecl, indent: int) -> str:
    if node.value is not None: # global or local variable with initialization
        return f"{_pad(indent)}{node.name} = {_generate_expression(node.value)}\n"
    
    if indent == 0: # global variables without initialization
        return f"{_pad(indent)}{node.name} = 0\n"
    
    return "" # local variable declaration without initialization is a no-op in Python


@_generate_statement.register(If)
def _generate_if(node: If, indent: int) -> str:
    text = f"{_pad(indent)}if {_generate_expression(node.condition)}:\n"
    text += _generate_statement(node.then_branch, indent + 1)
    if node.else_branch is not None and node.else_branch.statements:
        text += f"{_pad(indent)}else:\n"
        text += _generate_statement(node.else_branch, indent + 1)
    return text


@_generate_statement.register(While)
def _generate_while(node: While, indent: int) -> str:
    text = f"{_pad(indent)}while {_generate_expression(node.condition)}:\n"
    text += _generate_statement(node.body, indent + 1)
    return text


@_generate_statement.register(Return)
def _generate_return(node: Return, indent: int) -> str:
    if node.value is None:
        return f"{_pad(indent)}return\n"
    return f"{_pad(indent)}return {_generate_expression(node.value)}\n"


@_generate_statement.register(Print)
def _generate_print(node: Print, indent: int) -> str:
    return f"{_pad(indent)}print({_generate_expression(node.value)})\n"


@_generate_statement.register(ExprStmt)
def _generate_expr_stmt(node: ExprStmt, indent: int) -> str:
    return f"{_pad(indent)}{_generate_expression(node.expression)}\n"


@singledispatch
def _generate_expression(node) -> str:
    raise TypeError(f"No Python codegen rule for expression node {type(node).__name__}")

@_generate_expression.register(Group)
def _generate_group_expr(node: Group) -> str:
    return f"({_generate_expression(node.expression)})"


@_generate_expression.register(Assign)
def _generate_assign_expr(node: Assign) -> str:
    return f"{node.name} = {_generate_expression(node.value)}"


@_generate_expression.register(BinOp)
def _generate_binop_expr(node: BinOp) -> str:
    return f"{_generate_expression(node.left)} {node.operator} {_generate_expression(node.right)}"


@_generate_expression.register(UnaryOp)
def _generate_unary_expr(node: UnaryOp) -> str:
    return f"-({_generate_expression(node.operand)})"


@_generate_expression.register(Call)
def _generate_call_expr(node: Call) -> str:
    args = ", ".join(_generate_expression(arg) for arg in node.arguments)
    return f"{node.name}({args})"


@_generate_expression.register(Id)
def _generate_id_expr(node: Id) -> str:
    return node.name


@_generate_expression.register(Const)
def _generate_const_expr(node: Const) -> str:
    return str(node.value)
