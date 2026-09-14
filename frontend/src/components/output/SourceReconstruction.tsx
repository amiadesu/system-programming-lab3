import CodeMirror from "@uiw/react-codemirror";
import { cpp } from "@codemirror/lang-cpp";
import "./SourceReconstruction.css";

interface SourceReconstructionProps {
  reconstructedSource: string;
}

export default function SourceReconstruction({ reconstructedSource }: SourceReconstructionProps) {
  return (
    <div className="source-reconstruction">
      <CodeMirror
        value={reconstructedSource || "// код, відновлений з дерева, з'явиться тут після компіляції"}
        height="100%"
        theme="dark"
        extensions={[cpp()]}
        editable={false}
        basicSetup={{ lineNumbers: true, foldGutter: true }}
      />
    </div>
  );
}