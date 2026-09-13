import CodeMirror from "@uiw/react-codemirror";
import { cpp } from "@codemirror/lang-cpp";
import "./CodeEditor.css";

interface CodeEditorProps {
  sourceCode: string;
  onChange: (nextSourceCode: string) => void;
}

export default function CodeEditor({ sourceCode, onChange }: CodeEditorProps) {
  return (
    <div className="code-editor">
      <CodeMirror
        value={sourceCode}
        height="100%"
        theme="dark"
        extensions={[cpp()]}
        onChange={onChange}
        basicSetup={{ lineNumbers: true, foldGutter: true }}
      />
    </div>
  );
}
