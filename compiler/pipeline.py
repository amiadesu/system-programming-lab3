"""
The static compilation pipeline: turns C source text into a validated,
annotated AST, and the AST into Python source text.

This is deliberately modelled as data, not as one long function. Each stage
below is a small function with the same shape - `(context) -> None`, reading
fields earlier stages filled in and filling in its own - and `STAGES` lists
them in the order they must run. `run_pipeline` just walks that list.

The payoff is that the *order and composition* of the compiler's passes live
in exactly one place (`STAGES`), separate from what each pass does. Adding a
new one - an optimisation pass, an extra lint check, a second code generator
- means writing one function of that shape and inserting one line, instead of
threading a new call (and its inputs and outputs) through a growing
`translate()`. Nothing here needs to catch anything: a stage that finds a
problem raises the matching `CompilerError` subclass (`LexicalError`,
`SyntaxErrorAtLine`, `SemanticError`, ...) exactly as it always did, which
unwinds out of `run_pipeline` and tells the caller which stage rejected the
program.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ast_nodes import Program
from codegen import generate_python
from name_resolution import NameResolution, resolve_names
from parser import parse_source
from semantic_analysis import AnalysisResult, analyse
from type_inference import TypeInformation, infer_types


@dataclass
class CompilationContext:
    """
    The artifacts the pipeline produces, accumulated as stages run.

    Only `source_code` is required up front; every other field starts out
    `None` and is filled in by the stage responsible for it (see `STAGES`).
    Once `run_pipeline` returns normally, every field is populated.
    """

    source_code: str
    ast: Program | None = None
    analysis: AnalysisResult | None = None
    resolution: NameResolution | None = None
    types: TypeInformation | None = None
    python_code: str | None = None


#: The shape every pipeline stage has: read what it needs from `context`,
#: write what it produces back onto `context`, return nothing.
Stage = Callable[[CompilationContext], None]


def _parse(context: CompilationContext) -> None:
    context.ast = parse_source(context.source_code)


def _analyse(context: CompilationContext) -> None:
    context.analysis = analyse(context.ast) # type: ignore


def _resolve_names(context: CompilationContext) -> None:
    context.resolution = resolve_names(context.ast) # type: ignore


def _infer_types(context: CompilationContext) -> None:
    context.types = infer_types(context.ast, context.resolution) # type: ignore


def _generate_code(context: CompilationContext) -> None:
    context.python_code = generate_python(context.ast, context.resolution, context.types) # type: ignore


#: The pipeline itself, in the order its stages must run:
#: lex+parse -> validate -> resolve names -> infer types -> generate Python.
#: Each stage after `_parse` depends only on fields the stages before it in
#: this tuple have already filled in.
STAGES: tuple[Stage, ...] = (
    _parse,
    _analyse,
    _resolve_names,
    _infer_types,
    _generate_code,
)


def run_pipeline(source_code: str) -> CompilationContext:
    """
    Runs every stage in `STAGES` against `source_code`, in order.

    Stops at (and propagates) the first stage that raises. Whatever fields
    earlier stages managed to fill in are still on the returned-from
    exception's `context` local if a caller wants them for diagnostics, but
    ordinarily a raised `CompilerError` means the program simply does not
    compile and there is nothing further to look at.
    """
    context = CompilationContext(source_code=source_code)
    for stage in STAGES:
        stage(context)
    return context
