import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { ToolData } from '@/types/models';

interface CodePanelProps {
  onSave: (tool: ToolData) => void;
}

export const CodePanel: React.FC<CodePanelProps> = ({ onSave }) => {
  const [toolName, setToolName] = useState('');
  const [toolDescription, setToolDescription] = useState('');
  //const [parameters, setParameters] = useState<Record<string, string>>({});
  const [language, setLanguage] = useState('python');
  const [code, setCode] = useState('');

  const handleSave = () => {
    const toolData: ToolData = {
      name: toolName,
      description: toolDescription,
      //parameters: JSON.stringify(parameters),
      language,
      code,
    };
    onSave(toolData);
  };

  return (
    <div className="space-y-6">
      <div>
        <Label htmlFor="toolName">Tool Name</Label>
        <Input
          id="toolName"
          value={toolName}
          onChange={(e) => setToolName(e.target.value)}
        />
      </div>

      <div>
        <Label htmlFor="toolDescription">Description</Label>
        <Textarea
          id="toolDescription"
          value={toolDescription}
          onChange={(e) => setToolDescription(e.target.value)}
        />
      </div>

      <div>
        <Label htmlFor="code">Code</Label>
        <Textarea
          id="code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          className="font-mono"
        />
      </div>

      <div>
        <Label htmlFor="language">Language</Label>
        <select
          id="language"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className="rounded border px-2 py-1 text-sm bg-background"
        >
          <option value="python">Python</option>
          <option value="javascript">JavaScript</option>
          <option value="bash">Bash</option>
        </select>
      </div>

      <Button onClick={handleSave}>Save Tool</Button>
    </div>
  );
};
