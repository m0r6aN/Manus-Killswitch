import React, { useState } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  isConnected: boolean;
}

const ChatInput: React.FC<ChatInputProps> = ({ onSendMessage, isConnected }) => {
  const [inputText, setInputText] = useState('');

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setInputText(event.target.value);
  };

  const handleSendClick = () => {
    if (inputText.trim() && isConnected) {
      onSendMessage(inputText);
      setInputText(''); // Clear input after sending
    } else if (!isConnected) {
       console.error("Cannot send, WebSocket disconnected.");
       // Optionally show a visual indicator
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) { // Send on Enter, allow Shift+Enter for newline
      event.preventDefault(); // Prevent default form submission/newline
      handleSendClick();
    }
  };

  return (
    <div className="p-4 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
      <div className="flex space-x-2">
        <Input
          type="text"
          placeholder={isConnected ? "Type your message or task..." : "Connecting..."}
          value={inputText}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          disabled={!isConnected}
          className="flex-1"
        />
        <Button onClick={handleSendClick} disabled={!isConnected || !inputText.trim()}>
          Send
        </Button>
      </div>
    </div>
  );
};

export default ChatInput;