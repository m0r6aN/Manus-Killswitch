import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, ScatterChart, Scatter, ZAxis
} from 'recharts';

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8'];
const EFFORT_COLORS = {
  low: '#4CAF50',   // Green
  medium: '#FF9800', // Orange
  high: '#F44336'    // Red
};

const TaskDashboard = () => {
  const [data, setData] = useState({
    taskStats: {
      total_tasks: 0,
      completed_tasks: 0,
      active_tasks: 0,
      effort_distribution: { low: 0, medium: 0, high: 0 },
      outcome_distribution: { completed: 0, merged: 0, escalated: 0 },
      avg_duration_by_effort: { low: 0, medium: 0, high: 0 }
    },
    recentTasks: [],
    agentPerformance: []
  });
  
  // Fetch data
  useEffect(() => {
    // In a real app, this would fetch from your API
    // For demo purposes, we'll use mock data
    const mockData = {
      taskStats: {
        total_tasks: 125,
        completed_tasks: 87,
        active_tasks: 38,
        effort_distribution: { low: 32, medium: 64, high: 29 },
        outcome_distribution: { completed: 65, merged: 12, escalated: 10 },
        avg_duration_by_effort: { low: 45.5, medium: 126.8, high: 318.2 }
      },
      recentTasks: [
        { task_id: 'T007', content: 'Analyze data, redesign architecture...', effort: 'high', duration: 305.8, outcome: 'completed' },
        { task_id: 'T005', content: 'Compare approaches A and B...', effort: 'high', duration: 275.2, outcome: 'completed' },
        { task_id: 'T002', content: 'Design a new system to optimize...', effort: 'high', duration: 340.1, outcome: 'escalated' },
        { task_id: 'T006', content: 'Run a quick benchmark test', effort: 'medium', duration: 118.7, outcome: 'completed' },
        { task_id: 'T004', content: 'Refactor now', effort: 'high', duration: 289.5, outcome: 'completed' }
      ],
      agentPerformance: [
        { agent: 'Alice', tasks_completed: 32, avg_duration: 165.2, success_rate: 0.94 },
        { agent: 'Bob', tasks_completed: 28, avg_duration: 183.7, success_rate: 0.89 },
        { agent: 'Charlie', tasks_completed: 15, avg_duration: 210.1, success_rate: 0.87 },
        { agent: 'Dave', tasks_completed: 12, avg_duration: 140.5, success_rate: 0.92 }
      ],
      complexityData: [
        { word_count: 8, complexity_score: 2.0, effort: 'medium', task_id: 'T001' },
        { word_count: 12, complexity_score: 6.5, effort: 'high', task_id: 'T002' },
        { word_count: 4, complexity_score: 0, effort: 'medium', task_id: 'T003' },
        { word_count: 2, complexity_score: 2.5, effort: 'high', task_id: 'T004' },
        { word_count: 10, complexity_score: 4.0, effort: 'high', task_id: 'T005' },
        { word_count: 5, complexity_score: 1.5, effort: 'medium', task_id: 'T006' },
        { word_count: 15, complexity_score: 8.5, effort: 'high', task_id: 'T007' },
        { word_count: 6, complexity_score: 0, effort: 'low', task_id: 'T008' }
      ],
      adjustmentStats: [
        { name: 'Event Adjustments', count: 42 },
        { name: 'Confidence Adjustments', count: 18 },
        { name: 'Category Adjustments', count: 15 },
        { name: 'Deadline Adjustments', count: 12 },
        { name: 'Intent Adjustments', count: 8 }
      ],
      categoryUsage: [
        { name: 'analytical', count: 65 },
        { name: 'comparative', count: 32 },
        { name: 'creative', count: 48 },
        { name: 'complex', count: 35 }
      ]
    };
    
    setData(mockData);
  }, []);
  
  // Prepare data for charts
  const effortDistributionData = Object.entries(data.taskStats.effort_distribution).map(([key, value]) => ({
    name: key.charAt(0).toUpperCase() + key.slice(1),
    value,
    color: EFFORT_COLORS[key]
  }));
  
  const outcomeDistributionData = Object.entries(data.taskStats.outcome_distribution).map(([key, value]) => ({
    name: key.charAt(0).toUpperCase() + key.slice(1),
    value
  }));
  
  const durationByEffortData = Object.entries(data.taskStats.avg_duration_by_effort).map(([key, value]) => ({
    name: key.charAt(0).toUpperCase() + key.slice(1),
    value: Math.round(value),
    color: EFFORT_COLORS[key]
  }));
  
  return (
    <div className="p-4 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Task Factory Dashboard</h1>
      
      {/* Summary metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow">
          <h2 className="text-lg font-semibold mb-2">Tasks Overview</h2>
          <div className="flex justify-between">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Total Tasks</p>
              <p className="text-2xl font-bold">{data.taskStats.total_tasks}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Active</p>
              <p className="text-2xl font-bold text-blue-500">{data.taskStats.active_tasks}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Completed</p>
              <p className="text-2xl font-bold text-green-500">{data.taskStats.completed_tasks}</p>
            </div>
          </div>
        </div>
        
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow">
          <h2 className="text-lg font-semibold mb-2">Effort Distribution</h2>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={effortDistributionData}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={60}
                  paddingAngle={5}
                  dataKey="value"
                  label={({name, percent}) => `${name} ${(percent * 100).toFixed(0)}%`}
                >
                  {effortDistributionData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
        
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow">
          <h2 className="text-lg font-semibold mb-2">Avg Duration (seconds)</h2>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={durationByEffortData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value">
                  {durationByEffortData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}