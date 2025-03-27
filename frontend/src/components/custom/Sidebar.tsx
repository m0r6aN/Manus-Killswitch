import React from 'react';
import { Button } from '@/components/ui/button'; // Assuming shadcn Button
import { ScrollArea } from '@/components/ui/scroll-area'; // Assuming shadcn ScrollArea

interface SidebarProps {
   isConnected: boolean;
   agentStatus: Record<string, string>;
}

const Sidebar: React.FC<SidebarProps> = ({ isConnected, agentStatus }) => {
  return (
    <ScrollArea className="h-full p-4 w-48 lg:w-64"> {/* Responsive width */}
      <div className="flex flex-col space-y-4">
        <h2 className="text-lg font-semibold mb-4">Manus Killswitch</h2>

        {/* Connection Status */}
        <div className="text-sm">
          <span className={`inline-block w-3 h-3 rounded-full mr-2 ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></span>
          {isConnected ? 'Connected' : 'Disconnected'}
        </div>

         {/* Agent Status */}
         <div className="space-y-1">
            <h3 className="text-md font-medium mb-1">Agent Status</h3>
             {Object.entries(agentStatus).map(([name, status]) => (
               <div key={name} className="text-xs flex items-center">
                 <span className={`inline-block w-2 h-2 rounded-full mr-2 ${status === 'alive' ? 'bg-green-400' : 'bg-red-400'}`}></span>
                 <span className="capitalize mr-1">{name}:</span>
                 <span className={status === 'alive' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                    {status}
                 </span>
               </div>
             ))}
             {Object.keys(agentStatus).length === 0 && <p className='text-xs text-gray-500'>Loading status...</p>}
         </div>


        {/* Navigation (Placeholders) */}
        <nav className="flex flex-col space-y-2 pt-4 border-t dark:border-gray-700">
          <Button variant="ghost" className="justify-start">Dashboard</Button>
          <Button variant="ghost" className="justify-start">Tasks</Button>
          <Button variant="ghost" className="justify-start">Tools</Button>
          <Button variant="ghost" className="justify-start">Settings</Button>
        </nav>

        {/* Add more sidebar elements as needed */}
      </div>
    </ScrollArea>
  );
};

export default Sidebar;