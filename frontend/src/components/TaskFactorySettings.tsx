import React, { useState, useEffect } from 'react';
import { 
  Card, 
  CardHeader, 
  CardTitle, 
  CardDescription, 
  CardContent, 
  CardFooter 
} from '@/components/ui/card';
import { 
  Tabs, 
  TabsList, 
  TabsTrigger, 
  TabsContent 
} from '@/components/ui/tabs';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';

type KeywordCategory = {
  enabled: boolean;
  weight: number;
  keywords: string;
};

type KeywordCategories = {
  analytical: KeywordCategory;
  comparative: KeywordCategory;
  creative: KeywordCategory;
  complex: KeywordCategory;
};

const TaskFactorySettings = () => {
  // Default keyword category settings
  const [keywordCategories, setKeywordCategories] = useState<KeywordCategories>({
    analytical: {
      enabled: true,
      weight: 1.0,
      keywords: "analyze, evaluate, assess, research, investigate, study, examine, review, diagnose, audit, survey, inspect"
    },
    comparative: {
      enabled: true,
      weight: 1.5,
      keywords: "compare, contrast, differentiate, versus, pros and cons, trade-off, benchmark, measure against, weigh, rank"
    },
    creative: {
      enabled: true,
      weight: 2.0,
      keywords: "design, create, optimize, improve, innovate, develop, build, construct, craft, devise, formulate, invent"
    },
    complex: {
      enabled: true,
      weight: 2.5,
      keywords: "hypothesize, synthesize, debate, refactor, architect, theorize, model, simulate, predict, extrapolate, integrate, transform, restructure"
    }
  });

  const [thresholdSettings, setThresholdSettings] = useState({
    wordCountBase: {
      high: 50,
      medium: 20
    },
    scalingFactor: {
      high: 5,
      medium: 2
    }
  })

  const [autotuneSettings, setAutotuneSettings] = useState({
    enabled: true,
    analysisThreshold: 100,
    retainHistory: true,
    historyLimit: 1000
  });


  // Handler for threshold settings changes
  const handleCategoryChange = (category: KeywordCategories, field: KeywordCategory, value: any) => {
    setThresholdSettings(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [field]: value
      }
    }));
  };

  // Handler for simple threshold changes
  const handleSimpleThresholdChange = (field, value) => {
    setThresholdSettings(prev => ({
      ...prev,
      [field]: value
    }));
  };

  // Handler for autotune settings changes
  const handleAutotuneChange = (field, value) => {
    setAutotuneSettings(prev => ({
      ...prev,
      [field]: value
    }));
  };

  // Save settings
  const saveSettings = () => {
    // In a real app, this would save to the backend
    console.log('Saving settings:', {
      keywordCategories,
      thresholdSettings,
      autotuneSettings
    });
    
    // Show success message
    alert('Settings saved successfully!');
  };

  // Reset to defaults
  const resetDefaults = () => {
    if (confirm('Are you sure you want to reset all settings to defaults?')) {
      // Reset code would go here in a real application
      alert('Settings reset to defaults');
      window.location.reload();
    }
  };

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <Tabs defaultValue="keywords">
        <div className="flex justify-between items-center mb-4">
          <h1 className="text-2xl font-bold">Task Factory Settings</h1>
          <TabsList>
            <TabsTrigger value="keywords">Keywords</TabsTrigger>
            <TabsTrigger value="thresholds">Thresholds</TabsTrigger>
            <TabsTrigger value="autotune">Auto-tuning</TabsTrigger>
          </TabsList>
        </div>
        
        {/* Keywords Tab */}
        <TabsContent value="keywords">
          <Card>
            <CardHeader>
              <CardTitle>Keyword Categories</CardTitle>
              <CardDescription>
                Configure how different types of keywords affect task complexity scoring
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Accordion type="multiple" defaultValue={["analytical", "comparative", "creative", "complex"]}>
                {Object.entries(keywordCategories).map(([category, settings]) => (
                  <AccordionItem value={category} key={category}>
                    <AccordionTrigger className="capitalize">
                      {category} Keywords 
                      <span className="ml-2 text-sm text-gray-500">
                        (Weight: {settings.weight})
                      </span>
                    </AccordionTrigger>
                    <AccordionContent>
                      <div className="space-y-4">
                        <div className="flex items-center justify-between">
                          <Label htmlFor={`${category}-enabled`}>Enabled</Label>
                          <Switch 
                            id={`${category}-enabled`}
                            checked={settings.enabled}
                            onCheckedChange={(checked) => handleCategoryChange(category, 'enabled', checked)}
                          />
                        </div>
                        
                        <div className="space-y-2">
                          <div className="flex justify-between">
                            <Label htmlFor={`${category}-weight`}>Weight: {settings.weight}</Label>
                          </div>
                          <Slider
                            id={`${category}-weight`}
                            min={0.1}
                            max={5}
                            step={0.1}
                            value={[settings.weight]}
                            onValueChange={(value) => handleCategoryChange(category, 'weight', value[0])}
                          />
                        </div>
                        
                        <div className="space-y-2">
                          <Label htmlFor={`${category}-keywords`}>Keywords (comma separated)</Label>
                          <Input
                            id={`${category}-keywords`}
                            value={settings.keywords}
                            onChange={(e) => handleCategoryChange(category, 'keywords', e.target.value)}
                          />
                        </div>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Thresholds Tab */}
        <TabsContent value="thresholds">
          <Card>
            <CardHeader>
              <CardTitle>Threshold Settings</CardTitle>
              <CardDescription>
                Configure word count thresholds, scaling factors, and other parameters
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <h3 className="text-lg font-medium">Word Count Base Thresholds</h3>
                  
                  <div className="space-y-2">
                    <Label>HIGH Effort Threshold: {thresholdSettings.wordCountBase.high} words</Label>
                    <Slider
                      min={10}
                      max={100}
                      step={1}
                      value={[thresholdSettings.wordCountBase.high]}
                      onValueChange={(value) => handleThresholdChange('wordCountBase', 'high', value[0])}
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label>MEDIUM Effort Threshold: {thresholdSettings.wordCountBase.medium} words</Label>
                    <Slider
                      min={5}
                      max={50}
                      step={1}
                      value={[thresholdSettings.wordCountBase.medium]}
                      onValueChange={(value) => handleThresholdChange('wordCountBase', 'medium', value[0])}
                    />
                  </div>
                </div>
                
                <div className="space-y-4">
                  <h3 className="text-lg font-medium">Scaling Factors</h3>
                  
                  <div className="space-y-2">
                    <Label>HIGH Scaling: {thresholdSettings.scalingFactor.high}</Label>
                    <Slider
                      min={0}
                      max={10}
                      step={0.5}
                      value={[thresholdSettings.scalingFactor.high]}
                      onValueChange={(value) => handleThresholdChange('scalingFactor', 'high', value[0])}
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label>MEDIUM Scaling: {thresholdSettings.scalingFactor.medium}</Label>
                    <Slider
                      min={0}
                      max={5}
                      step={0.5}
                      value={[thresholdSettings.scalingFactor.medium]}
                      onValueChange={(value) => handleThresholdChange('scalingFactor', 'medium', value[0])}
                    />
                  </div>
                </div>
              </div>
              
              <div className="border-t pt-4 space-y-4">
                <h3 className="text-lg font-medium">Other Thresholds</h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label>Confidence Threshold: {thresholdSettings.confidenceThreshold}</Label>
                    <Slider
                      min={0.1}
                      max={0.9}
                      step={0.05}
                      value={[thresholdSettings.confidenceThreshold]}
                      onValueChange={(value) => handleSimpleThresholdChange('confidenceThreshold', value[0])}
                    />
                    <p className="text-sm text-gray-500">
                      Tasks with confidence below this threshold will get bumped up one effort level
                    </p>
                  </div>
                  
                  <div className="space-y-2">
                    <Label>Deadline Pressure Threshold: {thresholdSettings.deadlinePressureThreshold}</Label>
                    <Slider
                      min={0.1}
                      max={0.9}
                      step={0.05}
                      value={[thresholdSettings.deadlinePressureThreshold]}
                      onValueChange={(value) => handleSimpleThresholdChange('deadlinePressureThreshold', value[0])}
                    />
                    <p className="text-sm text-gray-500">
                      Tasks with deadline pressure above this will be bumped to HIGH effort
                    </p>
                  </div>
                </div>
                
                <div className="space-y-2">
                  <Label>Category Overlap Bonus: {thresholdSettings.categoryOverlapBonus}</Label>
                  <Slider
                    min={0}
                    max={2}
                    step={0.1}
                    value={[thresholdSettings.categoryOverlapBonus]}
                    onValueChange={(value) => handleSimpleThresholdChange('categoryOverlapBonus', value[0])}
                  />
                  <p className="text-sm text-gray-500">
                    Bonus applied per additional category when a task spans multiple categories
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Auto-tuning Tab */}
        <TabsContent value="autotune">
          <Card>
            <CardHeader>
              <CardTitle>Auto-Tuning Configuration</CardTitle>
              <CardDescription>
                Configure how the system learns from task outcomes
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-medium">Enable Auto-Tuning</h3>
                  <p className="text-sm text-gray-500">
                    Automatically adjust weights based on task outcomes
                  </p>
                </div>
                <Switch 
                  checked={autotuneSettings.enabled}
                  onCheckedChange={(checked) => handleAutotuneChange('enabled', checked)}
                />
              </div>
              
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Analysis Threshold: {autotuneSettings.analysisThreshold} tasks</Label>
                  <Slider
                    disabled={!autotuneSettings.enabled}
                    min={10}
                    max={500}
                    step={10}
                    value={[autotuneSettings.analysisThreshold]}
                    onValueChange={(value) => handleAutotuneChange('analysisThreshold', value[0])}
                  />
                  <p className="text-sm text-gray-500">
                    Number of tasks to collect before analyzing patterns
                  </p>
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-medium">Retain History</h3>
                    <p className="text-sm text-gray-500">
                      Keep task outcome history after analysis
                    </p>
                  </div>
                  <Switch 
                    disabled={!autotuneSettings.enabled}
                    checked={autotuneSettings.retainHistory}
                    onCheckedChange={(checked) => handleAutotuneChange('retainHistory', checked)}
                  />
                </div>
                
                <div className="space-y-2">
                  <Label>History Limit: {autotuneSettings.historyLimit} tasks</Label>
                  <Slider
                    disabled={!autotuneSettings.enabled || !autotuneSettings.retainHistory}
                    min={100}
                    max={10000}
                    step={100}
                    value={[autotuneSettings.historyLimit]}
                    onValueChange={(value: AutotuneSettings) => handleAutotuneChange('historyLimit', value[0])}
                  />
                  <p className="text-sm text-gray-500">
                    Maximum number of historical tasks to retain
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        <div className="mt-6 flex justify-between">
          <Button variant="outline" onClick={resetDefaults}>
            Reset to Defaults
          </Button>
          <Button onClick={saveSettings}>
            Save Settings
          </Button>
        </div>
      </Tabs>
    </div>
  );
};

export default TaskFactorySettings;