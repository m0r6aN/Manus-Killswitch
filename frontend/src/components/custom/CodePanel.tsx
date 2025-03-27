// src/components/chat/CodePanel.tsx

import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { ChevronLeft, ChevronRight, Code, Send, Play, Trash, Save } from "lucide-react";
import { useToast } from "@/app/hooks/use-toast";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import axios from "axios";

interface CodePanelProps {
  outputContent: string; // For displaying results/logs
  codeInput: string; // The current value of the input area
  isConnected: boolean;
  isCodePanelOpen: boolean;  // Assuming this controls visibility (though layout handles columns)
  setCodeInput: (value: string) => void; // Function to update input state
  setIsCodePanelOpen: (value: boolean) => void; // Function to toggle panel (might not be needed if layout 
  sendCode: () => void; // Function to execute code
  testCode: () => void; // Function to test code
  clearCode: () => void; // Function to clear input
}

export const CodePanel: React.FC<CodePanelProps> = ({
  outputContent, // Use the renamed prop
  codeInput,
  isConnected,
  isCodePanelOpen, // Use this prop if needed
  setCodeInput,
  setIsCodePanelOpen, // Use this prop if needed
  sendCode,
  testCode,
  clearCode,
}) => {
  // If panel state is managed externally, conditionally render or style
  if (!isCodePanelOpen) {
      // return null; // Or return a placeholder/collapsed view
  }

  const { toast } = useToast();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [textareaHeight, setTextareaHeight] = useState("auto");
  const [language, setLanguage] = useState("python");
  const [isSaveModalOpen, setIsSaveModalOpen] = useState(false);
  const [toolName, setToolName] = useState("");
  const [toolDescription, setToolDescription] = useState("");
  const [toolParameters, setToolParameters] = useState("");
  const [toolPath, setToolPath] = useState("");
  const [toolEntrypoint, setToolEntrypoint] = useState("");
  const [toolType, setToolType] = useState("function");
  const [toolVersion, setToolVersion] = useState("1.0");
  const [toolTags, setToolTags] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (textareaRef.current) {
      setTextareaHeight(`${textareaRef.current.scrollHeight}px`);
    }
  }, [codeInput]);

  const handleSaveTool = async () => {
    if (!toolName.trim() || !codeInput.trim()) {
      toast({
        title: "Error",
        description: "Tool name and code are required.",
        variant: "destructive",
      });
      return;
    }

    setIsSaving(true);
    try {
      // Validate and parse parameters as JSON
      let parameters = {};
      try {
        parameters = toolParameters.trim() ? JSON.parse(toolParameters) : {};
      } catch (error) {
        toast({
          title: "Error",
          description: "Parameters must be valid JSON (e.g., {\"param1\": \"number\"}).",
          variant: "destructive",
        });
        setIsSaving(false);
        return;
      }

      const toolData = {
        name: toolName,
        description: toolDescription,
        parameters: JSON.stringify(parameters),
        path: toolPath.trim() || null,
        entrypoint: toolEntrypoint.trim() || null,
        type: toolType,
        version: toolVersion,
        tags: toolTags.split(",").map(tag => tag.trim()).filter(tag => tag).join(","),
        language: language,
        code: codeInput,
      };

      const response = await axios.post("http://localhost:5000/tools", toolData);

      toast({
        title: "Tool Saved",
        description: `Tool "${toolName}" has been saved successfully.`,
      });
      setIsSaveModalOpen(false);
      setToolName("");
      setToolDescription("");
      setToolParameters("");
      setToolPath("");
      setToolEntrypoint("");
      setToolType("function");
      setToolVersion("1.0");
      setToolTags("");
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to save the tool. Please try again.",
        variant: "destructive",
      });
      console.error("Error saving tool:", error);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className={`flex flex-col border-l border-border bg-muted/20 transition-all duration-300 ${isCodePanelOpen ? 'w-96' : 'w-12'}`}>
      <div className="h-16 border-b border-border flex items-center justify-center">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setIsCodePanelOpen(!isCodePanelOpen)}
          className="w-full h-full rounded-none"
        >
          {isCodePanelOpen ? (
            <ChevronRight className="h-5 w-5" />
          ) : (
            <ChevronLeft className="h-5 w-5" />
          )}
        </Button>
      </div>

      {isCodePanelOpen && (
        <div className="flex flex-col flex-1 p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-2">
              <Code className="h-5 w-5 text-foreground" />
              <h2 className="text-lg font-bold">Code Editor</h2>
            </div>
            <Select onValueChange={setLanguage} defaultValue="python">
              <SelectTrigger className="w-32">
                <SelectValue placeholder="Language" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="python">Python</SelectItem>
                <SelectItem value="javascript">JavaScript</SelectItem>
                <SelectItem value="java">Java</SelectItem>
                <SelectItem value="cpp">C++</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="relative flex-1">
            <SyntaxHighlighter
              language={language}
              style={vscDarkPlus}
              customStyle={{
                margin: 0,
                padding: "0.75rem",
                background: "transparent",
                height: textareaHeight,
                overflow: "hidden",
                fontSize: "0.875rem",
                lineHeight: "1.5",
                borderRadius: "0.75rem",
              }}
              wrapLines={true}
              lineProps={{ style: { whiteSpace: "pre-wrap", wordBreak: "break-all" } }}
            >
              {codeInput || " "}
            </SyntaxHighlighter>
            <Textarea
              ref={textareaRef}
              placeholder="Enter your code here..."
              className="absolute inset-0 flex-1 resize-none rounded-xl bg-transparent text-transparent caret-foreground focus:ring-2 focus:ring-primary focus:border-transparent transition-all font-mono text-sm"
              style={{ color: "transparent", caretColor: "white" }}
              value={codeInput}
              onChange={(e) => setCodeInput(e.target.value)}
            />
          </div>
          <div className="flex space-x-2 mt-3">
            <Button
              onClick={sendCode}
              className="flex-1 rounded-xl"
              disabled={!isConnected || !codeInput.trim()}
            >
              <Send className="h-4 w-4 mr-2" />
              Send
            </Button>
            <Button
              onClick={() => setIsSaveModalOpen(true)}
              variant="outline"
              className="flex-1 rounded-xl"
              disabled={!codeInput.trim()}
            >
              <Save className="h-4 w-4 mr-2" />
              Save as Tool
            </Button>
            <Button
              onClick={testCode}
              variant="outline"
              className="flex-1 rounded-xl"
            >
              <Play className="h-4 w-4 mr-2" />
              Test
            </Button>
            <Button
              onClick={clearCode}
              variant="outline"
              className="flex-1 rounded-xl"
            >
              <Trash className="h-4 w-4 mr-2" />
              Clear
            </Button>
          </div>
        </div>
      )}

      {/* Save as Tool Modal */}
      <Dialog open={isSaveModalOpen} onOpenChange={setIsSaveModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save Code as Tool</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">Tool Name</label>
              <Input
                placeholder="e.g., calculate_sum"
                value={toolName}
                onChange={(e) => setToolName(e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Description</label>
              <Textarea
                placeholder="e.g., Calculates the sum of two numbers"
                value={toolDescription}
                onChange={(e) => setToolDescription(e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Parameters (JSON)</label>
              <Input
                placeholder='e.g., {"a": "number", "b": "number"}'
                value={toolParameters}
                onChange={(e) => setToolParameters(e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Path (optional)</label>
              <Input
                placeholder="e.g., /tools/calculate_sum.py"
                value={toolPath}
                onChange={(e) => setToolPath(e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Entrypoint (optional)</label>
              <Input
                placeholder="e.g., calculate_sum"
                value={toolEntrypoint}
                onChange={(e) => setToolEntrypoint(e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Type</label>
              <Select onValueChange={setToolType} defaultValue="function">
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="function">Function</SelectItem>
                  <SelectItem value="script">Script</SelectItem>
                  <SelectItem value="module">Module</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium">Version</label>
              <Input
                placeholder="e.g., 1.0"
                value={toolVersion}
                onChange={(e) => setToolVersion(e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Tags (comma-separated)</label>
              <Input
                placeholder="e.g., math, utility"
                value={toolTags}
                onChange={(e) => setToolTags(e.target.value)}
                className="mt-1"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsSaveModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveTool} disabled={isSaving}>
              {isSaving ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}