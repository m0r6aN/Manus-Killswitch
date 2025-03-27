import React from 'react';

// Define a type for the expected children structure (optional but good practice)
// interface LayoutWrapperProps {
//   children: [React.ReactNode, React.ReactNode, React.ReactNode, React.ReactNode]; // Expecting 4 children
// }

export const LayoutWrapper = ({ children }: { children: React.ReactNode[] }) => {
  // Ensure we have exactly 4 children or handle differently
  if (React.Children.count(children) !== 4) {
    console.warn("LayoutWrapper expects exactly 4 children for the 4-column layout.");
    // Fallback rendering or error handling
    return <div className="p-4 text-red-500">Layout Error: Expected 4 children components.</div>;
  }

  const [sidebar, chatList, chatContent, codePanel] = React.Children.toArray(children);

  return (
    <div className="grid grid-cols-layout h-screen w-screen overflow-hidden">
      {/* Column 1: Sidebar */}
      <div className="bg-gray-100 dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 overflow-y-auto">
        {sidebar}
      </div>

      {/* Column 2: Chat List */}
      <div className="bg-white dark:bg-gray-850 border-r border-gray-200 dark:border-gray-700 flex flex-col overflow-y-auto">
         {chatList}
      </div>

      {/* Column 3: Chat Content */}
      <div className="bg-gray-50 dark:bg-gray-900 flex flex-col h-full overflow-hidden">
         {/* Chat content should handle its own scrolling */}
         {chatContent}
      </div>

      {/* Column 4: Code Panel */}
      <div className="bg-gray-100 dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 overflow-y-auto">
        {codePanel}
      </div>
    </div>
  );
};