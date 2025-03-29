import React, { useState } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Loader2, ChevronDown } from 'lucide-react';
import TokenCounter from '@/components/custom/TokenCounter';
import { estimateTokenCount } from '@/lib/tokenizer';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  isConnected: boolean;
  isReconnecting?: boolean;
  maxCharacters?: number;
  maxTokens?: number;
  showCost?: boolean;
}

// Model options for token counting
const MODEL_OPTIONS = [
  { label: "GPT-3.5 Turbo", value: "gpt-3.5-turbo" },
  { label: "GPT-4", value: "gpt-4" },
  { label: "Claude 3", value: "claude-3" },
  { label: "Claude Instant", value: "claude-instant" }
];

const ChatInput: React.FC<ChatInputProps> = ({ 
  onSendMessage, 
  isConnected, 
  isReconnecting = false,
  maxCharacters = 4000,  // Default max characters
  maxTokens = 1000,      // Default max tokens
  showCost = true        // Show cost estimation by default
}) => {
  const [inputText, setInputText] = useState('');
  const [selectedModel, setSelectedModel] = useState(MODEL_OPTIONS[0]);

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setInputText(event.target.value);
  };
  
  const handleModelChange = (modelValue: string) => {
    const model = MODEL_OPTIONS.find(m => m.value === modelValue) || MODEL_OPTIONS[0];
    setSelectedModel(model);
  };

  const handleSendClick = () => {
    if (inputText.trim()) {
      onSendMessage(inputText);
      setInputText(''); // Clear input after sending
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) { // Send on Enter, allow Shift+Enter for newline
      event.preventDefault(); // Prevent default form submission/newline
      handleSendClick();
    }
  };

  // Determine the appropriate placeholder text based on connection state
  const getPlaceholderText = () => {
    if (isReconnecting) {
      return "Reconnecting... Message will be queued";
    } else if (!isConnected) {
      return "Disconnected... Reconnect to send messages";
    }
    return "Type your message or task...";
  };

  // Check if input exceeds limits with better token estimation
  const tokenCount = estimateTokenCount(inputText, selectedModel.value);
  const isOverLimit = 
    (maxCharacters && inputText.length > maxCharacters) || 
    (maxTokens && tokenCount > maxTokens);

  return (
    <div className="p-4 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
      <div className="flex flex-col space-y-2">
        <div className="flex space-x-2">
          <Input
            type="text"
            placeholder={getPlaceholderText()}
            value={inputText}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            // Allow typing even when disconnected/reconnecting - messages will be queued
            className={`flex-1 ${isOverLimit ? 'border-red-500 focus-visible:ring-red-500' : ''}`}
          />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button 
                variant="outline" 
                size="icon"
                className="px-2 w-auto"
              >
                <span className="sr-only">Select model</span>
                <ChevronDown className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {MODEL_OPTIONS.map((model) => (
                <DropdownMenuItem
                  key={model.value}
                  onClick={() => handleModelChange(model.value)}
                  className={selectedModel.value === model.value ? "bg-accent" : ""}
                >
                  {model.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <Button 
            onClick={handleSendClick} 
            disabled={!inputText.trim() || Boolean(isOverLimit)}
            variant={isConnected ? "default" : isReconnecting ? "outline" : "secondary"}
          >
            {isReconnecting && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            {isReconnecting ? "Queue" : "Send"}
          </Button>
        </div>
        
        {/* Token counter integration */}
        <div className="flex justify-between items-center px-1">
          <TokenCounter 
            text={inputText} 
            maxCharacters={maxCharacters}
            maxTokens={maxTokens}
            showCost={showCost}
            model={selectedModel.value}
          />
          
          {/* Warning message when over limit */}
          {isOverLimit && (
            <span className="text-xs text-red-500">
              Input exceeds limit
            </span>
          )}
          
          {/* Reconnecting message */}
          {isReconnecting && !isOverLimit && (
            <p className="text-xs text-muted-foreground">
              Connection lost. Message will be sent when reconnected.
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatInput;