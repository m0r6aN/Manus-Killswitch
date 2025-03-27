"use client";

import { useState } from "react";
import { Sidebar } from "@/components/custom/Sidebar";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label"; // Add this import
import { useToast } from "@/app/hooks/use-toast";
import { Clipboard } from "lucide-react";

export default function LogCleanerPage() {
  const [inputLogs, setInputLogs] = useState("");
  const [cleanedLogs, setCleanedLogs] = useState("");
  const [addLineBreaks, setAddLineBreaks] = useState(false); // New state
  const { toast } = useToast();

  const cleanLogs = () => {
    if (!inputLogs.trim()) {
      toast({ title: "Error", description: "Please paste some logs first.", variant: "destructive" });
      return;
    }

    const cleaned = inputLogs
      .split("\n")
      .map((line) => {
        const parts = line.split("|");
        if (parts.length < 2) return line;
        const service = parts[0].trim();
        const rest = parts[1].split(" - ");
        if (rest.length < 2) return line;
        const logContent = rest.slice(1).join(" - ");
        return `${service} | ${logContent}`;
      })
      .join(addLineBreaks ? "\n\n" : "\n"); // Toggle between \n\n or \n

    setCleanedLogs(cleaned);
    toast({ title: "Success", description: "Logs cleaned! Ready to copy." });
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(cleanedLogs);
    toast({ title: "Copied", description: "Cleaned logs copied to clipboard!" });
  };

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 p-6 bg-background text-foreground">
        <h1 className="text-2xl font-bold mb-4">Log Cleaner</h1>
        <div className="space-y-4">
          <Textarea
            placeholder="Paste your logs here..."
            value={inputLogs}
            onChange={(e) => setInputLogs(e.target.value)}
            className="h-40"
          />
          <div className="flex items-center space-x-4">
            <Button onClick={cleanLogs}>Clean Logs</Button>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="line-breaks"
                checked={addLineBreaks}
                onCheckedChange={(checked: boolean) => setAddLineBreaks(!!checked)}
              />
              <Label htmlFor="line-breaks">Add line breaks</Label>
            </div>
          </div>
          <div className="relative">
            <Textarea
              placeholder="Cleaned logs will appear here..."
              value={cleanedLogs}
              readOnly
              className="h-40"
            />
            {cleanedLogs && (
              <Button
                variant="outline"
                size="sm"
                className="absolute top-2 right-2"
                onClick={copyToClipboard}
              >
                <Clipboard className="h-4 w-4 mr-2" />
                Copy
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}