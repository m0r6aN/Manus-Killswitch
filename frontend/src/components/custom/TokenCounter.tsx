import React, { useMemo } from 'react';
import { estimateTokenCount, estimateTokenCost } from '@/lib/tokenizer';

interface TokenCounterProps {
  text: string;
  maxCharacters?: number;
  maxTokens?: number;
  showTokens?: boolean;
  showCost?: boolean;
  model?: string;
}

/**
 * A utility component that displays character count and estimated token count
 * for a given text. Useful for LLM input interfaces.
 */
const TokenCounter: React.FC<TokenCounterProps> = ({
  text,
  maxCharacters,
  maxTokens,
  showTokens = true,
  showCost = false,
  model = 'gpt-3.5-turbo',
}) => {
  // Character count is straightforward
  const charCount = text.length;
  
  // Use our more accurate tokenizer
  const estimatedTokenCount = useMemo(() => {
    return estimateTokenCount(text, model);
  }, [text, model]);
  
  // Calculate cost if requested
  const estimatedCost = useMemo(() => {
    if (!showCost) return 0;
    return estimateTokenCost(text, model);
  }, [text, model, showCost]);
  
  // Calculate percentages for the progress bars
  const charPercentage = maxCharacters ? Math.min(100, (charCount / maxCharacters) * 100) : 0;
  const tokenPercentage = maxTokens ? Math.min(100, (estimatedTokenCount / maxTokens) * 100) : 0;
  
  // Determine colors based on usage
  const getColorClass = (percentage: number): string => {
    if (percentage < 75) return 'bg-green-500';
    if (percentage < 90) return 'bg-yellow-500';
    return 'bg-red-500';
  };
  
  const charColorClass = getColorClass(charPercentage);
  const tokenColorClass = getColorClass(tokenPercentage);

  return (
    <div className="text-xs text-muted-foreground flex flex-col gap-1">
      {/* Character counter */}
      <div className="flex items-center justify-between">
        <span>Characters: {charCount}{maxCharacters ? ` / ${maxCharacters}` : ''}</span>
        
        {maxCharacters && (
          <div className="w-24 h-1 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div 
              className={`h-full ${charColorClass} transition-all duration-300 ease-in-out`} 
              style={{ width: `${charPercentage}%` }}
            />
          </div>
        )}
      </div>
      
      {/* Token counter (optional) */}
      {showTokens && (
        <div className="flex items-center justify-between">
          <span>
            Est. Tokens: {estimatedTokenCount}{maxTokens ? ` / ${maxTokens}` : ''}
            {showCost && estimatedCost > 0 && (
              <span className="ml-2 text-xs opacity-75">
                (~${estimatedCost.toFixed(4)})
              </span>
            )}
          </span>
          
          {maxTokens && (
            <div className="w-24 h-1 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div 
                className={`h-full ${tokenColorClass} transition-all duration-300 ease-in-out`} 
                style={{ width: `${tokenPercentage}%` }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default TokenCounter;