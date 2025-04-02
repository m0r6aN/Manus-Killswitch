import React, { useState, useCallback, useMemo } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Loader2, ChevronDown } from 'lucide-react';
import TokenCounter from '@/components/chat/token-counter'; // Assuming this component exists and works
import { estimateTokenCount } from '@/lib/tokenizer'; // Assuming this uses the optimized version
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface ChatInputProps {
    onSendMessage: (message: string, model: string) => void; // Pass model back
    isConnected: boolean;
    isReconnecting?: boolean;
    maxCharacters?: number;
    maxTokens?: number;
    showCost?: boolean;
}

// Consider moving to a constants file if shared
const MODEL_OPTIONS = [
    { label: "GPT-3.5 Turbo", value: "gpt-3.5-turbo" },
    { label: "GPT-4", value: "gpt-4" },
    { label: "Claude 3 Sonnet", value: "claude-3-sonnet" }, // Example more specific model
    { label: "Claude Instant", value: "claude-instant-1" } // Example more specific model
];

const ChatInput: React.FC<ChatInputProps> = ({
    onSendMessage,
    isConnected,
    isReconnecting = false,
    maxCharacters = 4000,
    maxTokens = 1000,
    showCost = true
}) => {
    const [inputText, setInputText] = useState('');
    const [selectedModel, setSelectedModel] = useState(MODEL_OPTIONS[0]);

    const handleInputChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
        setInputText(event.target.value);
    }, []);

    const handleModelChange = useCallback((modelValue: string) => {
        const model = MODEL_OPTIONS.find(m => m.value === modelValue) || MODEL_OPTIONS[0];
        setSelectedModel(model);
    }, []);

    const handleSendClick = useCallback(() => {
        const trimmedInput = inputText.trim();
        if (trimmedInput) {
            onSendMessage(trimmedInput, selectedModel.value); // Send model value too
            setInputText(''); // Clear input after sending
        }
    }, [inputText, onSendMessage, selectedModel.value]);

    const handleKeyDown = useCallback((event: React.KeyboardEvent<HTMLInputElement>) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            handleSendClick();
        }
    }, [handleSendClick]);

    const getPlaceholderText = useMemo(() => {
        if (isReconnecting) {
            return "Reconnecting... Messages will be queued";
        } else if (!isConnected) {
            return "Disconnected... Waiting to reconnect";
        }
        return "Type your message or task...";
    }, [isConnected, isReconnecting]);

    const tokenCount = useMemo(() => {
        // Debounce might be useful for very complex tokenizers, but likely fine for estimation
        return estimateTokenCount(inputText, selectedModel.value);
    }, [inputText, selectedModel.value]);

    const isOverCharLimit = maxCharacters && inputText.length > maxCharacters;
    const isOverTokenLimit = maxTokens && tokenCount > maxTokens;
    const isOverLimit = isOverCharLimit || isOverTokenLimit;

    const getLimitWarning = () => {
        if (isOverCharLimit) return `Character limit exceeded (${inputText.length}/${maxCharacters})`;
        if (isOverTokenLimit) return `Token limit exceeded (~${tokenCount}/${maxTokens})`;
        return "Input exceeds limit";
    }

    return (
        <div className="p-4 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
            <div className="flex flex-col space-y-2">
                <div className="flex space-x-2">
                    <Input
                        type="text"
                        placeholder={getPlaceholderText}
                        value={inputText}
                        onChange={handleInputChange}
                        onKeyDown={handleKeyDown}
                        disabled={!isConnected && !isReconnecting} // Disable input fully if disconnected and not trying to reconnect
                        className={`flex-1 ${isOverLimit ? 'border-red-500 focus-visible:ring-red-500' : ''}`}
                    />
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button
                                variant="outline"
                                // size="icon" // Removed size="icon" to allow text
                                className="px-3 flex items-center gap-1 min-w-[100px] justify-between" // Added fixed width and gap
                            >
                                <span className="truncate text-xs flex-1 text-left">{selectedModel.label}</span>
                                <ChevronDown className="h-4 w-4 opacity-70" />
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
                        // Disable sending if disconnected, OR if input is empty/overlimit
                        disabled={!isConnected || !inputText.trim() || Boolean(isOverLimit)}
                        // Keep variant logic, but rely on disabled state primarily
                        variant={isConnected ? "default" : isReconnecting ? "outline" : "secondary"}
                        aria-label={isReconnecting ? "Queue Message" : "Send Message"}
                    >
                        {isReconnecting && !isConnected && ( // Show loader only when actively reconnecting
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        )}
                        {isReconnecting ? "Queue" : "Send"}
                    </Button>
                </div>

                {/* Token counter integration */}
                <div className="flex justify-between items-center px-1 h-5"> {/* Added fixed height */}
                    {(inputText || showCost) && ( // Show counter only if there's text or showCost is true
                         <TokenCounter
                            text={inputText}
                            maxCharacters={maxCharacters}
                            maxTokens={maxTokens}
                            showCost={showCost}
                            model={selectedModel.value}
                        />
                    )}

                    {/* Warning message when over limit */}
                    {isOverLimit && (
                        <span className="text-xs text-red-500 ml-auto"> {/* Push warning right */}
                            {getLimitWarning()}
                        </span>
                    )}

                    {/* Reconnecting message */}
                    {isReconnecting && !isOverLimit && (
                        <p className="text-xs text-muted-foreground ml-auto"> {/* Push message right */}
                            Connection lost. Message will be sent when reconnected.
                        </p>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ChatInput;