import type { CompileResult } from "../types/ast";

const BACKEND_URL = "http://localhost:8000";

export class CompileError extends Error {}

interface CompileResponseBody {
  ast: CompileResult["ast"];
  python_code: string;
  execution_output: string;
  execution_error: string | null;
}

export async function compileSource(sourceCode: string): Promise<CompileResult> {
  const response = await fetch(`${BACKEND_URL}/compile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_code: sourceCode }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new CompileError(body?.detail ?? `Request failed with status ${response.status}`);
  }

  const body = (await response.json()) as CompileResponseBody;
  return {
    ast: body.ast,
    pythonCode: body.python_code,
    executionOutput: body.execution_output,
    executionError: body.execution_error,
  };
}
