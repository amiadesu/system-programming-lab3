import { useState } from "react";
import CodeEditor from "./components/editor/CodeEditor";
import AstTree from "./components/ast-view/AstTree";
import PythonOutput from "./components/output/PythonOutput";
import { compileSource, CompileError } from "./api/compileApi";
import type { CompileResult } from "./types/ast";
import "./App.css";

const DEFAULT_SOURCE_CODE = `int fib(int n) {
    if (n <= 1) {
        return n;
    } else {
        return fib(n - 1) + fib(n - 2);
    }
}

int main(void) {
    int i;
    i = 0;
    while (i < 8) {
        print(fib(i));
        i = i + 1;
    }
    return 0;
}
`;

export default function App() {
  const [sourceCode, setSourceCode] = useState(DEFAULT_SOURCE_CODE);
  const [result, setResult] = useState<CompileResult | null>(null);
  const [compileErrorMessage, setCompileErrorMessage] = useState<string | null>(null);
  const [isCompiling, setIsCompiling] = useState(false);

  async function handleCompile() {
    setIsCompiling(true);
    setCompileErrorMessage(null);
    try {
      const nextResult = await compileSource(sourceCode);
      setResult(nextResult);
    } catch (error) {
      setResult(null);
      setCompileErrorMessage(error instanceof CompileError ? error.message : "Не вдалося з'єднатися з backend");
    } finally {
      setIsCompiling(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1 className="app-title">C → Python</h1>
        <button className="app-run-button" onClick={handleCompile} disabled={isCompiling}>
          {isCompiling ? "Компіляція…" : "Скомпілювати"}
        </button>
      </header>

      {compileErrorMessage && <div className="app-error-banner">{compileErrorMessage}</div>}

      <main className="app-columns">
        <section className="app-column">
          <h2 className="app-column-heading">C-код</h2>
          <CodeEditor sourceCode={sourceCode} onChange={setSourceCode} />
        </section>

        <section className="app-column">
          <h2 className="app-column-heading">AST</h2>
          <AstTree root={result?.ast ?? null} />
        </section>

        <section className="app-column">
          <h2 className="app-column-heading">Python</h2>
          <PythonOutput
            pythonCode={result?.pythonCode ?? ""}
            executionOutput={result?.executionOutput ?? ""}
            executionError={result?.executionError ?? null}
          />
        </section>
      </main>
    </div>
  );
}
