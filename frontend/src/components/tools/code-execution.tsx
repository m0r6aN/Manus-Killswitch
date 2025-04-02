import React, { useState, useEffect, JSX } from 'react';
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter,
  Button, Input, Label, Textarea, Switch, Badge, Alert, AlertDescription, 
  AlertTitle
} from '@/components/ui';
import {
  AlertCircle, CheckCircle, Clock, FileText, Terminal, XCircle
} from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Progress } from '../ui/progress';
import Image from 'next/image'

interface OutputFiles {
  [filename: string]: string;
}

interface ExecutionResult {
  status: 'success' | 'timeout' | 'error' | 'processing' | string;
  stdout?: string;
  stderr?: string;
  output_files?: OutputFiles;
  error_message?: string;
  execution_time: number;
}

interface StatusBadgeProps {
  status: string;
}

interface CodeExecutionProps {
  initialCode?: string;
  setCodeInput?: (code: string) => void;
  onResult?: (result: ExecutionResult) => void;
}

const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  switch (status) {
    case 'submitting': return <Badge className="bg-blue-100 text-blue-800">Submitting...</Badge>;
    case 'pending': return <Badge className="bg-blue-100 text-blue-800">Pending</Badge>;
    case 'processing': return <Badge className="bg-yellow-100 text-yellow-800">Processing</Badge>;
    case 'success': return <Badge className="bg-green-100 text-green-800">Success</Badge>;
    case 'timeout': return <Badge className="bg-orange-100 text-orange-800">Timeout</Badge>;
    case 'error': return <Badge className="bg-red-100 text-red-800">Error</Badge>;
    default: return <Badge>Unknown</Badge>;
  }
};

export const CodeExecution: React.FC<CodeExecutionProps> = ({
  initialCode = '',
  setCodeInput,
  onResult,
}) => {
  const [code, setCode] = useState<string>(initialCode);
  const [taskId, setTaskId] = useState<string>(`task_${Math.random().toString(36).substring(2, 12)}`);
  const [dependencies, setDependencies] = useState<string>('matplotlib,numpy');
  const [timeout, setTimeoutSec] = useState<number>(30);
  const [allowFileAccess, setAllowFileAccess] = useState<boolean>(true);
  const [executionMode, setExecutionMode] = useState<'docker' | 'subprocess'>('docker');
  const [executionId, setExecutionId] = useState<string>('');
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [executionStatus, setExecutionStatus] = useState<string>('');
  const [executionResult, setExecutionResult] = useState<ExecutionResult | null>(null);
  const [executionError, setExecutionError] = useState<string>('');
  const [executionTime, setExecutionTime] = useState<number>(0);
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);
  const [activeTab, setActiveTab] = useState<'stdout' | 'stderr' | 'files'>('stdout');
  const [textareaHeight, setTextareaHeight] = useState<string>('auto');
  const [language, setLanguage] = useState<string>('python');

  const generateNewTaskId = (): void => {
    setTaskId(`task_${Math.random().toString(36).substring(2, 12)}`);
  };

  useEffect(() => {
    if (executionResult && onResult) {
      onResult(executionResult);
    }
  }, [executionResult, onResult]);

  useEffect(() => {
    if (setCode) {
      setCode(code);
    }
  }, [code, setCode]);

  const executeCode = async (): Promise<void> => {
    try {
      setExecutionError('');
      setExecutionResult(null);
      setExecutionStatus('submitting');
      setIsExecuting(true);

      const depsArray = dependencies
        .split(',')
        .map(dep => dep.trim())
        .filter(dep => dep);

      const executionRequest = {
        code,
        task_id: taskId,
        timeout,
        dependencies: depsArray,
        allow_file_access: allowFileAccess,
        execution_mode: executionMode,
        requesting_agent: 'UI'
      };

      const response = await fetch('/api/sandbox/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(executionRequest)
      });

      if (!response.ok) throw new Error(`Execution request failed: ${response.statusText}`);

      const result = await response.json();
      setExecutionId(result.execution_id);
      setExecutionStatus('pending');

      const intervalId = setInterval(() => {
        pollExecutionResult(result.execution_id);
      }, 1000);
      setPollingInterval(intervalId);
    } catch (error) {
      console.error('Error executing code:', error);
      if (error instanceof Error) {
        setExecutionError(error.message);
      } else {
        setExecutionError('An unknown error occurred');
      }
      setIsExecuting(false);
      setExecutionStatus('error');
    }
  };

  const pollExecutionResult = async (execId: string): Promise<void> => {
    try {
      const response = await fetch(`/api/sandbox/result/${execId}`);

      if (response.status === 202) {
        setExecutionStatus('processing');
        return;
      }

      if (!response.ok) throw new Error(`Failed to get execution result: ${response.statusText}`);

      const result: ExecutionResult = await response.json();

      if (pollingInterval) {
        clearInterval(pollingInterval);
        setPollingInterval(null);
      }

      setExecutionResult(result);
      setExecutionTime(result.execution_time);
      setExecutionStatus(result.status);
      setIsExecuting(false);
    } catch (error) {
      console.error('Polling error:', error);
    }
  };

  useEffect(() => {
    return () => {
      if (pollingInterval) clearInterval(pollingInterval);
    };
  }, [pollingInterval]);

  const renderOutputFiles = (files?: OutputFiles): JSX.Element => {
    if (!files || Object.keys(files).length === 0) {
      return <p className="text-gray-500 italic">No output files generated</p>;
    }

    return (
      <div className="space-y-2">
        {Object.entries(files).map(([filename, base64Content]) => {
          const isImage = filename.match(/\.(jpg|jpeg|png|gif|svg)$/i);
          const isText = filename.match(/\.(txt|md|py|js|html|css|json|csv)$/i);

          return (
            <div key={filename} className="border rounded p-2">
              <div className="flex justify-between items-center mb-2">
                <div className="flex items-center">
                  <FileText className="w-4 h-4 mr-2" />
                  <span className="font-mono text-sm">{filename}</span>
                </div>
                <span className="text-xs text-gray-500">
                  {Math.round(base64Content.length * 0.75)} bytes
                </span>
              </div>

              {isImage && (
                <Image
                  src={`data:image/${filename.split('.').pop()};base64,${base64Content}`}
                  alt={filename}
                  width={300}
                  height={300}
                  className="max-w-full h-auto mx-auto"
                  style={{ maxHeight: '300px' }}
                />
              )}

              {isText && (
                <pre className="p-2 text-xs overflow-auto max-h-36 bg-gray-50">
                  {atob(base64Content)}
                </pre>
              )}

              {!isImage && !isText && (
                <div className="flex justify-center p-2 text-gray-500">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const linkSource = `data:application/octet-stream;base64,${base64Content}`;
                      const downloadLink = document.createElement('a');
                      downloadLink.href = linkSource;
                      downloadLink.download = filename;
                      downloadLink.click();
                    }}
                  >
                    Download File
                  </Button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle>Python Code Execution</CardTitle>
              <CardDescription>
                Execute Python code in a sandboxed environment
              </CardDescription>
            </div>
            {executionStatus && <StatusBadge status={executionStatus} />}
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div>
              <Label htmlFor="taskId">Task ID</Label>
              <div className="flex space-x-2">
                <Input id="taskId" value={taskId} onChange={(e) => setTaskId(e.target.value)} disabled={isExecuting} />
                <Button variant="outline" onClick={generateNewTaskId} disabled={isExecuting}>Generate</Button>
              </div>
            </div>
            <div>
              <Label htmlFor="code">Python Code</Label>
              <Textarea
                id="code"
                value={code}
                onChange={(e) => {
                  setCode(e.target.value);
                  setTextareaHeight('auto');
                }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement;
                  setTextareaHeight('auto');
                  setTextareaHeight(`${target.scrollHeight}px`);
                }}
                style={{ height: textareaHeight }}
                className="font-mono resize-none"
                disabled={isExecuting}
              />
            </div>
            <div>
              <Label htmlFor="language">Language</Label>
              <select
                id="language"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                disabled={isExecuting}
                className="rounded border px-2 py-1 text-sm bg-background"
              >
                <option value="python">Python</option>
                <option value="javascript">JavaScript</option>
                <option value="bash">Bash</option>
              </select>
            </div>
          </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="dependencies">Dependencies</Label>
                <Input id="dependencies" value={dependencies} onChange={(e) => setDependencies(e.target.value)} disabled={isExecuting} />
              </div>
              <div>
                <Label htmlFor="timeout">Timeout (seconds)</Label>
                <Input id="timeout" type="number" value={timeout} onChange={(e) => setTimeoutSec(Number(e.target.value))} min={1} max={300} disabled={isExecuting} />
              </div>
            </div>
            <div className="flex items-center space-x-10">
              <div className="flex items-center space-x-2">
                <Switch id="allowFileAccess" checked={allowFileAccess} onCheckedChange={setAllowFileAccess} disabled={isExecuting} />
                <Label htmlFor="allowFileAccess">Allow File Access</Label>
              </div>
              <div className="flex items-center space-x-2">
                <input type="radio" id="dockerMode" name="executionMode" value="docker" checked={executionMode === 'docker'} onChange={() => setExecutionMode('docker')} disabled={isExecuting} />
                <Label htmlFor="dockerMode">Docker</Label>
              </div>
              <div className="flex items-center space-x-2">
                <input type="radio" id="subprocessMode" name="executionMode" value="subprocess" checked={executionMode === 'subprocess'} onChange={() => setExecutionMode('subprocess')} disabled={isExecuting} />
                <Label htmlFor="subprocessMode">Subprocess</Label>
              </div>
            </div>         
        </CardContent>
        <CardFooter className="flex justify-between">
          <div>{executionId && <span className="text-xs text-gray-500">Execution ID: {executionId}</span>}</div>
          <Button onClick={executeCode} disabled={isExecuting}>
            {isExecuting ? (<><Clock className="mr-2 h-4 w-4 animate-spin" />Executing...</>) : ('Execute Code')}
          </Button>
        </CardFooter>
      </Card>

      {isExecuting && (
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-2 text-center">
              <Clock className="mx-auto h-8 w-8 text-blue-500 animate-spin" />
              <p>Executing Python code...</p>
              <Progress value={executionStatus === 'processing' ? 66 : 33} className="w-full" />
            </div>
          </CardContent>
        </Card>
      )}

      {executionError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{executionError}</AlertDescription>
        </Alert>
      )}

      {executionResult && (
        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <CardTitle>Execution Result</CardTitle>
              <div className="flex items-center space-x-2">
                <span className="text-sm text-gray-500">{executionTime.toFixed(2)}s</span>
                {executionResult.status === 'success' ? <CheckCircle className="h-5 w-5 text-green-500" /> : executionResult.status === 'timeout' ? <Clock className="h-5 w-5 text-orange-500" /> : <XCircle className="h-5 w-5 text-red-500" />}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'stdout' | 'stderr' | 'files')}>
              <TabsList className="mb-4">
                <TabsTrigger value="stdout"><Terminal className="mr-2 h-4 w-4" />Output</TabsTrigger>
                <TabsTrigger value="stderr"><AlertCircle className="mr-2 h-4 w-4" />Errors</TabsTrigger>
                <TabsTrigger value="files"><FileText className="mr-2 h-4 w-4" />Files</TabsTrigger>
              </TabsList>
              <TabsContent value="stdout">
                <pre className="p-4 bg-black text-green-400 font-mono text-sm rounded-md overflow-auto max-h-96">{executionResult.stdout || 'No standard output'}</pre>
              </TabsContent>
              <TabsContent value="stderr">
                <pre className="p-4 bg-black text-red-400 font-mono text-sm rounded-md overflow-auto max-h-96">{executionResult.stderr || 'No standard error'}</pre>
              </TabsContent>
              <TabsContent value="files">
                <div className="p-4 border rounded-md">{renderOutputFiles(executionResult.output_files)}</div>
              </TabsContent>
            </Tabs>
            {executionResult.error_message && (
              <Alert className="mt-4" variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Execution Error</AlertTitle>
                <AlertDescription>{executionResult.error_message}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};
