import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "compiler"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from translator import translate
from schemas import CompileRequest, CompileResponse

app = FastAPI(title="C to Python translator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["POST"],
    allow_headers=["*"],
)


@app.post("/compile", response_model=CompileResponse)
def compile_source(request: CompileRequest) -> CompileResponse:
    try:
        result = translate(request.source_code)
    except SyntaxError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return CompileResponse(
        ast=result.ast,
        python_code=result.python_code,
        execution_output=result.execution_output,
        execution_error=result.execution_error,
    )
