"""
Top-level entry point: turns C source text into everything the frontend
wants to show for it.

Two things happen with the result of `pipeline.run_pipeline`, independently
of each other:

* the generated Python is compiled (not run) as a self-check on the code
  generator, separate from whether the *program itself* is correct;
* the AST is executed directly by the interpreter, which is how
  `execution_output`/`execution_error` are obtained without needing a Python
  runtime for the generated code.
"""
from dataclasses import dataclass

from ast_serializer import ast_to_dict
from error_normalization import describe as _describe_error
from interpreter import Interpreter
from pipeline import CompilationContext, run_pipeline


@dataclass
class TranslationResult:
    ast: dict | None
    python_code: str
    codegen_error: str | None
    warnings: list[str]
    execution_output: str
    execution_error: str | None


def translate(source_code: str) -> TranslationResult:
    context = run_pipeline(source_code)

    execution_output, execution_error = _interpret(context)

    return TranslationResult(
        ast=ast_to_dict(context.ast),
        python_code=context.python_code, # type: ignore
        codegen_error=_check_generated_python(context.python_code), # type: ignore
        warnings=context.analysis.warnings, # type: ignore
        execution_output=execution_output,
        execution_error=execution_error,
    )


def _check_generated_python(python_code: str) -> str | None:
    """Compiles (but does not run) the generated Python, to catch a bug in
    the code generator itself rather than in the submitted program."""
    try:
        compile(python_code, "<generated>", "exec")
    except SyntaxError as error:
        return f"Згенеровано некоректний Python: {error}"
    return None


def _interpret(context: CompilationContext) -> tuple[str, str | None]:
    """Runs the AST directly. Any failure - a genuine runtime error in the
    program, or an execution-limit guard tripping - is reported as text
    rather than raised, since it describes the *submitted program*, not a
    fault in the service."""
    try:
        interpreter = Interpreter(context.ast, context.types) # type: ignore
        interpreter.run()
        return "\n".join(interpreter.output_lines), None
    except Exception as error:
        return "", _describe_error(error)
