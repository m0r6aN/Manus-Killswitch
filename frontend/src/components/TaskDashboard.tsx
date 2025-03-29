import React, { useState, useEffect } from 'react';
import { 
  Card, 
  CardHeader, 
  CardTitle, 
  CardDescription, 
  CardContent, 
  CardFooter 
} from '@/components/ui/card';
import { MessageIntent, Task, TaskEvent } from '@/types/models';
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent
} from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, ScatterChart, Scatter, ZAxis
} from 'recharts';

// Constants for styling
const COLORS = {
  low: '#4CAF50',     // Green
  medium: '#FF9800',  // Orange
  high: '#F44336',    // Red
  primary: '#0088FE', // Blue
  secondary: '#00C49F', // Teal
};

const TaskDashboard = () => {
  // State to store task data and statistics
  const [taskData, setTaskData] = useState({
    activeTasks: [] as (Task & {diagnostics: any})[],
    completedTasks: [] as (Task & {diagnostics: any, completed_at: string, duration: number})[],
    metrics: {
      total: 0,
      active: 0,
      completed: 0,
      effortDistribution: { low: 0, medium: 0, high: 0 },
      successRate: 0,
      avgDuration: 0
    },
    analyticsData: {
      effortOverTime: [] as { date: string; low: number; medium: number; high: number }[],
      categoryScores: [],
      adjustmentFactors: []
    }
  });

  // Mock function to fetch task data - replace with actual API call
  const fetchTaskData = async () => {
    // This would be an API call in a real application
    // For demo, we're using mock data that mimics TaskFactory output
    
    // Mock data for demonstration
    const mockData: {
      activeTasks: (Task & {diagnostics: any, reasoning_effort: string, reasoning_strategy: string})[],
      completedTasks: (Task & {diagnostics: any, reasoning_effort: string, reasoning_strategy: string, completed_at: string, duration: number, outcome: string})[],
      metrics: any,
    } = {
      activeTasks: [
        {
          task_id: 'task_123abc',
          content: 'Design a new algorithm for optimizing the neural network architecture',
          target_agent: 'Claude',
          reasoning_effort: 'high',
          reasoning_strategy: 'chain-of-draft',
          event: TaskEvent.PLAN,
          created_at: new Date(Date.now() - 1800000).toISOString(),
          agent: 'System',
          intent: MessageIntent.OPTIMIZE,
          timestamp: new Date(Date.now() - 1800000).toISOString(),
          diagnostics: {
            complexity_score: 4.5,
            word_count: 11,
            category_scores: {
              creative: 1,
              complex: 1,
              analytical: 0
            },
            event_adjustment: "Increased to HIGH due to complexity"
          }
        },
        {
          task_id: 'task_456def',
          content: 'Compare the performance of the two models',
          target_agent: 'GPT',
          reasoning_effort: 'medium',
          reasoning_strategy: 'chain-of-thought',
          event: TaskEvent.EXECUTE,
          created_at: new Date(Date.now() - 600000).toISOString(),
          agent: 'System',
          intent: MessageIntent.ANALYZE,
          timestamp: new Date(Date.now() - 600000).toISOString(),
          diagnostics: {
            complexity_score: 1.5,
            word_count: 9,
            category_scores: {
              comparative: 1,
              analytical: 0
            }
          }
        },
        {
          task_id: 'task_789ghi',
          content: 'Send the response to the user',
          target_agent: 'Grok',
          reasoning_effort: 'low',
          reasoning_strategy: 'direct_answer',
          event: TaskEvent.EXECUTE,
          created_at: new Date(Date.now() - 300000).toISOString(),
          agent: 'System',
          intent: MessageIntent.RESPOND,
          timestamp: new Date(Date.now() - 300000).toISOString(),
          diagnostics: {
            complexity_score: 0,
            word_count: 6,
            category_scores: {}
          }
        }
      ],
      completedTasks: [
        {
          task_id: 'task_101jkl',
          content: 'Analyze the data and synthesize the findings into a comprehensive report',
          target_agent: 'Claude',
          reasoning_effort: 'high',
          reasoning_strategy: 'chain-of-draft',
          event: TaskEvent.COMPLETE,
          created_at: new Date(Date.now() - 7200000).toISOString(),
          completed_at: new Date(Date.now() - 5400000).toISOString(),
          duration: 1800, // seconds
          outcome: 'success',
          agent: 'System',
          intent: MessageIntent.ANALYZE,
          timestamp: new Date(Date.now() - 7200000).toISOString(),
          diagnostics: {
            complexity_score: 3.5,
            word_count: 13,
            category_scores: {
              analytical: 1,
              complex: 1
            },
            category_adjustment: "Bumped to HIGH due to presence of complex keywords"
          }
        },
        {
          task_id: 'task_202mno',
          content: 'Review the document',
          target_agent: 'GPT',
          reasoning_effort: 'low',
          reasoning_strategy: 'direct_answer',
          event: TaskEvent.COMPLETE,
          created_at: new Date(Date.now() - 5400000).toISOString(),
          completed_at: new Date(Date.now() - 5100000).toISOString(),
          duration: 300, // seconds
          outcome: 'success',
          agent: 'System',
          intent: MessageIntent.REVIEW,
          timestamp: new Date(Date.now() - 5400000).toISOString(),
          diagnostics: {
            complexity_score: 0,
            word_count: 3,
            category_scores: {
              analytical: 0
            }
          }
        }
      ],
      metrics: {
        total: 5,
        active: 3,
        completed: 2,
        effortDistribution: { low: 2, medium: 1, high: 2 },
        successRate: 100,
        avgDuration: 1050 // seconds
      }
    };

    // Generate analytics data based on mock task data
    const effortOverTime = [
      { date: '2023-01-01', low: 5, medium: 2, high: 1 },
      { date: '2023-01-02', low: 3, medium: 4, high: 2 },
      { date: '2023-01-03', low: 4, medium: 3, high: 3 },
      { date: '2023-01-04', low: 2, medium: 5, high: 4 },
      { date: '2023-01-05', low: 3, medium: 2, high: 5 },
    ];

    const categoryScores = [
      { name: 'analytical', value: 12 },
      { name: 'comparative', value: 8 },
      { name: 'creative', value: 15 },
      { name: 'complex', value: 10 },
    ];

    const adjustmentFactors = [
      { name: 'Category', value: 20 },
      { name: 'Event', value: 15 },
      { name: 'Confidence', value: 8 },
      { name: 'Deadline', value: 5 },
      { name: 'Intent', value: 12 },
    ];

    // Set all the data
    setTaskData({
      ...mockData,
      analyticsData: {
        effortOverTime,
        categoryScores,
        adjustmentFactors
      }
    });
  };

  // Fetch data on component mount
  useEffect(() => {
    fetchTaskData();
    // In a real app, you might want to set up a polling interval
    // const intervalId = setInterval(fetchTaskData, 10000);
    // return () => clearInterval(intervalId);
  }, []);

  // Format the effort distribution data for the pie chart
  const effortDistributionData = Object.entries(taskData.metrics.effortDistribution).map(([key, value]) => ({
    name: key.charAt(0).toUpperCase() + key.slice(1),
    value: value,
    color: COLORS[key as keyof typeof COLORS]
  }));

  // Prepare scatter data for complexity vs. word count
  const complexityScatterData = [
    ...taskData.activeTasks,
    ...taskData.completedTasks
  ].map(task => ({
    id: task.task_id,
    word_count: task.diagnostics.word_count,
    complexity_score: task.diagnostics.complexity_score,
    effort: task.reasoning_effort,
    content: task.content.length > 30 ? task.content.substring(0, 30) + '...' : task.content
  }));

  // Calculate category data for bar chart
  const categoryTotals = taskData.analyticsData.categoryScores;

  // Prepare adjustment factors data for bar chart
  const adjustmentFactorsData = taskData.analyticsData.adjustmentFactors;

  return (
    <div className="p-4 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Task Management Dashboard</h1>
      
      <Tabs defaultValue="overview">
        <TabsList className="mb-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="tasks">Active Tasks</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
        </TabsList>
        
        <TabsContent value="overview">
          {/* Summary Statistics Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-xl">Tasks</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex justify-between items-center">
                  <div className="text-2xl font-bold">{taskData.metrics.total}</div>
                  <div className="flex gap-2">
                    <Badge variant="outline" className="bg-blue-100 dark:bg-blue-900">
                      Active: {taskData.metrics.active}
                    </Badge>
                    <Badge variant="outline" className="bg-green-100 dark:bg-green-900">
                      Completed: {taskData.metrics.completed}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-xl">Reasoning Effort</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-32">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={effortDistributionData}
                        cx="50%"
                        cy="50%"
                        innerRadius={30}
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
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-xl">Performance</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span>Success Rate</span>
                    <span className="font-bold text-green-600">{taskData.metrics.successRate}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Avg. Duration</span>
                    <span className="font-bold">{(taskData.metrics.avgDuration / 60).toFixed(1)} min</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
          
          {/* Complexity vs Word Count Chart */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle>Task Complexity Analysis</CardTitle>
              <CardDescription>Word count vs. complexity score with effort level</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart
                    margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis 
                      type="number" 
                      dataKey="word_count" 
                      name="Word Count"
                      label="Word Count"
                    />
                    <YAxis 
                      type="number" 
                      dataKey="complexity_score" 
                      name="Complexity Score" 
                      label={{ value: "Complexity Score", angle: -90, position: "insideLeft" }}
                    />
                    <ZAxis range={[60, 60]} />
                    <Tooltip 
                      cursor={{ strokeDasharray: '3 3' }}
                      formatter={(value, name) => [value, name]}
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="bg-white dark:bg-gray-800 p-2 border rounded shadow">
                              <p className="text-sm">{data.content}</p>
                              <p className="text-xs">Word Count: {data.word_count}</p>
                              <p className="text-xs">Complexity: {data.complexity_score.toFixed(1)}</p>
                              <p className="text-xs">Effort: {data.effort.toUpperCase()}</p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Legend />
                    <Scatter 
                      name="Low Effort" 
                      data={complexityScatterData.filter(d => d.effort === 'low')} 
                      fill={COLORS.low}
                    />
                    <Scatter 
                      name="Medium Effort" 
                      data={complexityScatterData.filter(d => d.effort === 'medium')} 
                      fill={COLORS.medium}
                    />
                    <Scatter 
                      name="High Effort" 
                      data={complexityScatterData.filter(d => d.effort === 'high')} 
                      fill={COLORS.high}
                    />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
          
          {/* Recent Tasks Preview */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Tasks</CardTitle>
              <CardDescription>Latest tasks with their reasoning effort assessment</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {taskData.activeTasks.slice(0, 3).map(task => (
                  <div key={task.task_id} className="border rounded-md p-3">
                    <div className="flex justify-between items-start">
                      <div className="font-medium">{task.content}</div>
                      <Badge
                        className={`
                          ${task.reasoning_effort === 'low' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100' : ''}
                          ${task.reasoning_effort === 'medium' ? 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-100' : ''}
                          ${task.reasoning_effort === 'high' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100' : ''}
                        `}
                      >
                        {task.reasoning_effort?.toUpperCase()} Effort
                      </Badge>
                    </div>
                    <div className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                      <span>Target: {task.target_agent}</span>
                      <span className="mx-2">•</span>
                      <span>Strategy: {task.reasoning_strategy}</span>
                      <span className="mx-2">•</span>
                      <span>Complexity: {task.diagnostics.complexity_score.toFixed(1)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
            <CardFooter>
              <Button variant="outline" className="w-full">View All Tasks</Button>
            </CardFooter>
          </Card>
        </TabsContent>
        
        <TabsContent value="tasks">
          <div className="mb-4 flex justify-between items-center">
            <h2 className="text-xl font-semibold">Active Tasks</h2>
            <div className="flex gap-2">
              <Badge variant="outline" className="bg-green-100 dark:bg-green-900">
                Low: {taskData.metrics.effortDistribution.low}
              </Badge>
              <Badge variant="outline" className="bg-orange-100 dark:bg-orange-900">
                Medium: {taskData.metrics.effortDistribution.medium}
              </Badge>
              <Badge variant="outline" className="bg-red-100 dark:bg-red-900">
                High: {taskData.metrics.effortDistribution.high}
              </Badge>
            </div>
          </div>
          
          <div className="space-y-4">
            {taskData.activeTasks.map(task => (
              <Card key={task.task_id}>
                <CardHeader className="pb-2">
                  <div className="flex justify-between">
                    <CardTitle className="text-lg">{task.content}</CardTitle>
                    <Badge
                      className={`
                        ${task.reasoning_effort === 'low' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100' : ''}
                        ${task.reasoning_effort === 'medium' ? 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-100' : ''}
                        ${task.reasoning_effort === 'high' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100' : ''}
                      `}
                    >
                      {task.reasoning_effort?.toUpperCase()} Effort
                    </Badge>
                  </div>
                  <CardDescription>
                    Target: {task.target_agent} • Event: {task.event} • Strategy: {task.reasoning_strategy}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-sm space-y-2">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <div className="font-medium">Complexity Score</div>
                        <div>{task.diagnostics.complexity_score.toFixed(1)}</div>
                      </div>
                      <div>
                        <div className="font-medium">Word Count</div>
                        <div>{task.diagnostics.word_count}</div>
                      </div>
                    </div>
                    
                    {Object.keys(task.diagnostics.category_scores).length > 0 && (
                      <div>
                        <div className="font-medium mt-2">Category Scores</div>
                        <div className="flex gap-2 mt-1 flex-wrap">
                          {Object.entries(task.diagnostics.category_scores).map(([category, score]) => 
                            (score as number) > 0 && (
                              <Badge key={category} variant="outline">
                                {category}: {score as number}
                              </Badge>
                            )
                          )}
                        </div>
                      </div>
                    )}
                    
                    {task.diagnostics.event_adjustment && (
                      <div>
                        <div className="font-medium mt-2">Adjustments</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          {task.diagnostics.event_adjustment}
                        </div>
                      </div>
                    )}
                  </div>
                </CardContent>
                <CardFooter className="pt-0">
                  <Button size="sm" variant="outline">View Details</Button>
                </CardFooter>
              </Card>
            ))}
          </div>
        </TabsContent>
        
        <TabsContent value="analytics">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            {/* Category Distribution */}
            <Card>
              <CardHeader>
                <CardTitle>Category Distribution</CardTitle>
                <CardDescription>Keyword categories that trigger reasoning complexity</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={categoryTotals}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="value" name="Frequency" fill={COLORS.primary} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Adjustment Factors */}
            <Card>
              <CardHeader>
                <CardTitle>Adjustment Factors</CardTitle>
                <CardDescription>Factors that modify base reasoning effort</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={adjustmentFactorsData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="value" name="Frequency" fill={COLORS.secondary} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Effort Over Time */}
          <Card>
            <CardHeader>
              <CardTitle>Reasoning Effort Over Time</CardTitle>
              <CardDescription>Distribution of task effort levels over time</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={taskData.analyticsData.effortOverTime}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line 
                      type="monotone" 
                      dataKey="low" 
                      name="Low Effort" 
                      stroke={COLORS.low} 
                      strokeWidth={2} 
                    />
                    <Line 
                      type="monotone" 
                      dataKey="medium" 
                      name="Medium Effort" 
                      stroke={COLORS.medium} 
                      strokeWidth={2} 
                    />
                    <Line 
                      type="monotone" 
                      dataKey="high" 
                      name="High Effort" 
                      stroke={COLORS.high} 
                      strokeWidth={2} 
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
            <CardFooter>
              <div className="text-sm text-gray-500 dark:text-gray-400">
                The system automatically adjusts complexity thresholds and category weights based on actual task performance.
              </div>
            </CardFooter>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default TaskDashboard;