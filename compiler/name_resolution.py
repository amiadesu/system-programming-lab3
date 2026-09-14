"""
Module for resolving collisions between global and local identifiers.

Maps every variable occurrence in the AST to the identifier that the generated
Python code must use.

Two mismatches make a name-for-name translation wrong:

* C has block scope, Python only has function scope. A declaration inside a
  nested `{ ... }` that shadows an outer name would collapse into that outer
  name in Python, so it has to be renamed (alpha-conversion).
* A C identifier may collide with a Python keyword or with a name the generated
  module needs for itself (`math`, a function name, ...).

Renaming is deliberately applied only where a collision really exists, so
ordinary programs keep their original identifiers and the generated code stays
readable.
"""
from __future__ import annotations

import keyword
from dataclasses import dataclass, field

from ast_nodes import (
    Assign, BinOp, Block, Break, Call, CompoundAssign, Continue, DoWhile,
    ExprStmt, For, FuncDecl, Group, Id, If, IncDec, LogicalOp, Print, Program,
    Return, Ternary, UnaryOp, VarDecl, While,
)
from errors import SemanticError


def _at(node) -> str:
    """Source position prefix for an error message, when the node has one."""
    line = getattr(node, "line", None)
    return f"Рядок {line}: " if line else ""

# Names the generated module uses itself and therefore may not be shadowed.
RESERVED_NAMES = {"math"}


def _pick_name(preferred: str, forbidden: set[str]) -> str:
    """
    Returns `preferred`, or the first free `preferred__N` if it cannot be
    used as a Python identifier here.
    """
    if preferred not in forbidden and not keyword.iskeyword(preferred) and preferred not in RESERVED_NAMES:
        return preferred
    index = 1
    while f"{preferred}__{index}" in forbidden:
        index += 1
    return f"{preferred}__{index}"


@dataclass
class NameResolution:
    """
    Lookup tables keyed by `id()` of the AST node.

    `_kept_alive` holds references to every keyed node so that CPython cannot
    recycle an `id()` while the resolution is in use.
    """

    python_name: dict[int, str] = field(default_factory=dict)
    function_name: dict[str, str] = field(default_factory=dict)
    assigned_globals: dict[str, list[str]] = field(default_factory=dict)
    _kept_alive: list = field(default_factory=list)

    def name_of(self, node) -> str:
        return self.python_name.get(id(node), node.name) # type: ignore

    def name_of_function(self, c_name: str) -> str:
        return self.function_name.get(c_name, c_name)

    def _record(self, node, name: str) -> None:
        self.python_name[id(node)] = name
        self._kept_alive.append(node)


class _Binder:
    """
    Walks the AST, keeping track of the current scope and recording which
    declaration each occurrence binds to. Also collects the set of globals and
    functions that are actually used, so that the next phase can avoid collisions
    with them.
    """

    def __init__(self, global_names: set[str]):
        self.global_names = global_names
        self.scopes: list[dict[str, object]] = []
        # occurrence node → (node, declaration it binds to; None == global)
        self.binding: dict[int, tuple] = {}
        # declaration node → declarations visible at that point
        self.visible_declarations: dict[int, list] = {}
        self.declarations: list = []
        self.globals_used: set[str] = set()
        self.functions_called: set[str] = set()
        self.assigned_globals: list[str] = []
        self.all_names: set[str] = set()

    def push(self) -> None:
        self.scopes.append({})

    def pop(self) -> None:
        self.scopes.pop()

    def visible(self) -> list:
        return [declaration for scope in self.scopes for declaration in scope.values()]

    def lookup(self, name: str):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def declare(self, node, name: str, where: str) -> None:
        if name in self.scopes[-1]:
            raise SemanticError(f"{_at(node)}повторне оголошення '{name}' {where}")
        self.visible_declarations[id(node)] = self.visible()
        self.scopes[-1][name] = node
        self.declarations.append(node)
        self.all_names.add(name)

    def use(self, node, name: str, is_assignment: bool) -> None:
        declaration = self.lookup(name)
        self.binding[id(node)] = (node, declaration)
        self.all_names.add(name)
        if declaration is None:
            if name not in self.global_names:
                raise SemanticError(
                    f"{_at(node)}використання неоголошеної змінної '{name}'"
                )
            self.globals_used.add(name)
            if is_assignment and name not in self.assigned_globals:
                self.assigned_globals.append(name)


def resolve_names(program: Program) -> NameResolution:
    resolution = NameResolution()
    global_names, module_names = _name_module_level(program, resolution)

    for declaration in program.declarations:
        if isinstance(declaration, VarDecl) and declaration.value is not None:
            _bind_global_initializer(declaration.value, global_names, module_names, resolution)

    for declaration in program.declarations:
        if not isinstance(declaration, FuncDecl):
            continue
        binder = _Binder(global_names)
        binder.push()
        for param in declaration.params:
            binder.declare(param, param.name, f"у параметрах функції '{declaration.name}'")
        _bind_block(declaration.body, binder, new_scope=False)
        binder.pop()
        _assign_python_names(binder, module_names, resolution)
        resolution.assigned_globals[declaration.name] = [
            module_names[name] for name in binder.assigned_globals
        ]

    return resolution


def _name_module_level(program: Program, resolution: NameResolution) -> tuple[set[str], dict[str, str]]:
    """
    Globals and functions live in one Python namespace, so they are named
    together. Returns the set of C global variable names and the C → Python
    name map for everything declared at module level.
    """
    global_names: set[str] = set()
    function_names: set[str] = set()
    module_names: dict[str, str] = {}
    taken: set[str] = set()

    for declaration in program.declarations:
        name = declaration.name
        is_function = isinstance(declaration, FuncDecl)

        if name in module_names:
            if is_function and name in function_names:
                raise SemanticError(f"{_at(declaration)}повторне оголошення функції '{name}'")
            if not is_function and name in global_names:
                raise SemanticError(
                    f"{_at(declaration)}повторне оголошення глобальної змінної '{name}'"
                )
            raise SemanticError(
                f"{_at(declaration)}'{name}' оголошено і як змінну, і як функцію"
            )

        python_name = _pick_name(name, taken)
        taken.add(python_name)
        module_names[name] = python_name

        if is_function:
            function_names.add(name)
            resolution.function_name[name] = python_name
        else:
            global_names.add(name)
            resolution._record(declaration, python_name)

    return global_names, module_names


def _assign_python_names(binder: _Binder, module_names: dict[str, str], resolution: NameResolution) -> None:
    """
    Picks a Python identifier for every local declaration.
    """
    reachable_module_names = {
        module_names[name]
        for name in binder.globals_used | binder.functions_called
        if name in module_names
    }

    assigned: set[str] = set()
    for declaration in binder.declarations:
        name = declaration.name
        enclosing_names = {
            resolution.python_name[id(enclosing)]
            for enclosing in binder.visible_declarations[id(declaration)]
        }
        can_keep_name = (
            not keyword.iskeyword(name)
            and name not in RESERVED_NAMES
            and name not in enclosing_names
            and name not in reachable_module_names
        )
        if can_keep_name:
            python_name = name
        else:
            # `all_names` is included so a generated `x__1` cannot collide with
            # a variable the programmer actually called `x__1`.
            taken = enclosing_names | reachable_module_names | assigned | binder.all_names
            python_name = _pick_name(name, taken)
        assigned.add(python_name)
        resolution._record(declaration, python_name)

    for node, declaration in binder.binding.values():
        if declaration is None:
            resolution._record(node, module_names[node.name])
        else:
            resolution._record(node, resolution.python_name[id(declaration)])


def _bind_global_initializer(
    node, global_names: set[str], module_names: dict[str, str], resolution: NameResolution
) -> None:
    if isinstance(node, Call):
        # Module-level statements run top to bottom in the generated Python, so
        # an initializer calling a function declared further down would hit a
        # NameError, while the interpreter - which builds its function table
        # first - would happily run it. Forbidding the call keeps the two in
        # step regardless of declaration order.
        raise SemanticError(
            f"{_at(node)}ініціалізатор глобальної змінної не може викликати "
            f"функції (виклик '{node.name}')"
        )
    if isinstance(node, (Id, Assign, CompoundAssign, IncDec)):
        if node.name not in global_names:
            raise SemanticError(
                f"{_at(node)}ініціалізатор глобальної змінної посилається на "
                f"'{node.name}', яка не є глобальною змінною"
            )
        resolution._record(node, module_names[node.name])
    for child in _expression_children(node):
        _bind_global_initializer(child, global_names, module_names, resolution)


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


def _bind_block(block: Block, binder: _Binder, new_scope: bool = True) -> None:
    if new_scope:
        binder.push()
    for statement in block.statements:
        _bind_statement(statement, binder)
    if new_scope:
        binder.pop()


def _bind_statement(node, binder: _Binder) -> None:
    if isinstance(node, VarDecl):
        if node.value is not None:  # evaluated before the name comes into scope
            _bind_expression(node.value, binder)
        binder.declare(node, node.name, "у цій області видимості")
    elif isinstance(node, Block):
        _bind_block(node, binder)
    elif isinstance(node, If):
        _bind_expression(node.condition, binder)
        _bind_block(node.then_branch, binder)
        if node.else_branch is not None:
            _bind_block(node.else_branch, binder)
    elif isinstance(node, While):
        _bind_expression(node.condition, binder)
        _bind_block(node.body, binder)
    elif isinstance(node, DoWhile):
        _bind_block(node.body, binder)
        _bind_expression(node.condition, binder)
    elif isinstance(node, For):
        # `for (int i = ...)` declares `i` in a scope around the loop, not in
        # the enclosing block.
        binder.push()
        for statement in node.init:
            _bind_statement(statement, binder)
        if node.condition is not None:
            _bind_expression(node.condition, binder)
        _bind_block(node.body, binder)
        if node.step is not None:
            _bind_expression(node.step, binder)
        binder.pop()
    elif isinstance(node, (Break, Continue)):
        pass
    elif isinstance(node, Return):
        if node.value is not None:
            _bind_expression(node.value, binder)
    elif isinstance(node, Print):
        _bind_expression(node.value, binder)
    elif isinstance(node, ExprStmt):
        _bind_expression(node.expression, binder)
    else:
        raise TypeError(f"Невідомий вузол оператора {type(node).__name__}")


def _bind_expression(node, binder: _Binder) -> None:
    if isinstance(node, (Assign, CompoundAssign)):
        _bind_expression(node.value, binder)
        binder.use(node, node.name, is_assignment=True)
        return
    if isinstance(node, IncDec):
        binder.use(node, node.name, is_assignment=True)
        return
    if isinstance(node, Id):
        binder.use(node, node.name, is_assignment=False)
        return
    if isinstance(node, Call):
        binder.functions_called.add(node.name)
    for child in _expression_children(node):
        _bind_expression(child, binder)