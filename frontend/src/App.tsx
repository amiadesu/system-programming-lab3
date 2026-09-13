import { useEffect, useState } from "react";
import CodeEditor from "./components/editor/CodeEditor";
import AstTree from "./components/ast-view/AstTree";
import PythonOutput from "./components/output/PythonOutput";
import { compileSource, fetchExamples, CompileError } from "./api/compileApi";
import type { CompileResult, Example } from "./types/ast";
import "./App.css";

const FALLBACK_SOURCE_CODE = `int main(void) {
    print(1 + 2 * 3);
    return 0;
}
`;

export default function App() {
  const [sourceCode, setSourceCode] = useState(FALLBACK_SOURCE_CODE);
  const [examples, setExamples] = useState<Example[]>([]);
  const [result, setResult] = useState<CompileResult | null>(null);
  const [compileErrorMessage, setCompileErrorMessage] = useState<string | null>(null);
  const [isCompiling, setIsCompiling] = useState(false);

  // The examples live in examples/*.c and are served by the backend, so the
  // repository stays the single source of truth for them.
  useEffect(() => {
    let cancelled = false;
    fetchExamples()
      .then((loadedExamples: Example[]) => {
        if (cancelled || loadedExamples.length === 0) return;
        setExamples(loadedExamples);
        setSourceCode((current) =>
          current === FALLBACK_SOURCE_CODE ? loadedExamples[0].sourceCode : current,
        );
      })
      .catch(() => {
        /* the examples are a convenience; the editor works without them */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleCompile() {
    setIsCompiling(true);
    setCompileErrorMessage(null);
    try {
      const nextResult = await compileSource(sourceCode);
      setResult(nextResult);
    } catch (error) {
      setResult(null);
      setCompileErrorMessage(
        error instanceof CompileError ? error.message : "Не вдалося з'єднатися з backend",
      );
    } finally {
      setIsCompiling(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1 className="app-title">C → Python</h1>

        <div className="app-header-actions">
          {examples.length > 0 && (
            <div className="app-examples">
              <span className="app-examples-label">Приклади:</span>
              {examples.map((example) => (
                <button
                  key={example.name}
                  className="app-example-button"
                  onClick={() => setSourceCode(example.sourceCode)}
                  disabled={isCompiling}
                >
                  {example.name}
                </button>
              ))}
            </div>
          )}

          <button className="app-run-button" onClick={handleCompile} disabled={isCompiling}>
            {isCompiling ? "Компіляція…" : "Скомпілювати"}
          </button>
        </div>
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
            codegenError={result?.codegenError ?? null}
            executionOutput={result?.executionOutput ?? ""}
            executionError={result?.executionError ?? null}
          />
        </section>
      </main>
    </div>
  );
}