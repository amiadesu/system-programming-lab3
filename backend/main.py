import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "compiler"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from errors import CompilerError
from translator import translate
from schemas import CompileRequest, CompileResponse, Example

EXAMPLES_DIRECTORY = PROJECT_ROOT / "examples"

app = FastAPI(title="C to Python translator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.post("/compile", response_model=CompileResponse)
def compile_source(request: CompileRequest) -> CompileResponse:
    try:
        result = translate(request.source_code)
    except CompilerError as error:
        # A fault in the submitted program, not in the service.
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RecursionError as error:
        raise HTTPException(
            status_code=422, detail="Вираз занадто глибоко вкладений"
        ) from error

    return CompileResponse(
        ast=result.ast,
        python_code=result.python_code,
        codegen_error=result.codegen_error,
        execution_output=result.execution_output,
        execution_error=result.execution_error,
    )


@app.get("/examples", response_model=list[Example])
def list_examples() -> list[Example]:
    """
    Serves the files in examples/ so the UI and the repository cannot drift
    apart.
    """
    if not EXAMPLES_DIRECTORY.is_dir():
        return []
    return [
        Example(name=path.stem.replace("_", " "), source_code=path.read_text(encoding="utf-8"))
        for path in sorted(EXAMPLES_DIRECTORY.glob("*.c"))
    ]