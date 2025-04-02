import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface ToolExecutionModalProps {
  toolName: string;
  toolDescription: string;
  toolParams: Record<string, string>;
  isOpen: boolean;
  isExecuting: boolean;
  onChange: (key: string, value: string) => void;
  onExecute: () => void;
  onCancel: () => void;
}

export const ToolExecutionModal: React.FC<ToolExecutionModalProps> = ({
  toolName,
  toolDescription,
  toolParams,
  isOpen,
  isExecuting,
  onChange,
  onExecute,
  onCancel,
}) => {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          transition={{ duration: 0.25 }}
          className="mt-4 p-4 bg-muted rounded-xl shadow-xl"
        >
          <p className="text-sm font-semibold mb-2">Execute: {toolName}</p>
          {Object.entries(toolParams).map(([key, value]) => (
            <div key={key} className="mb-2">
              <label className="text-xs font-medium">{key}</label>
              <Input
                value={value}
                onChange={(e) => onChange(key, e.target.value)}
              />
            </div>
          ))}
          <div className="flex space-x-2 mt-2">
            <Button disabled={isExecuting} onClick={onExecute}>
              {isExecuting ? "Running..." : "Run"}
            </Button>
            <Button variant="outline" onClick={onCancel}>
              Cancel
            </Button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
