// Fully Typed and Cleaned Up TaskFactorySettings.tsx
import React, { useState, useCallback, useMemo } from "react";
import {
    Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter
} from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
    Accordion, AccordionContent, AccordionItem, AccordionTrigger
} from "@/components/ui/accordion";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use

// --- Type Definitions ---
interface KeywordCategory {
    enabled: boolean;
    weight: number;
    keywords: string;
}

interface KeywordCategories {
    analytical: KeywordCategory;
    comparative: KeywordCategory;
    creative: KeywordCategory;
    complex: KeywordCategory;
}

interface ThresholdSettings {
    wordCountBase: { high: number; medium: number; };
    scalingFactor: { high: number; medium: number; };
    confidenceThreshold?: number;
    deadlinePressureThreshold?: number;
    categoryOverlapBonus?: number;
}

interface AutotuneSettings {
    enabled: boolean;
    analysisThreshold: number;
    retainHistory: boolean;
    historyLimit: number;
}

type AllSettings = {
    keywordCategories: KeywordCategories;
    thresholdSettings: ThresholdSettings;
    autotuneSettings: AutotuneSettings;
};

type NestedThresholdKey = "wordCountBase" | "scalingFactor";
type FlatThresholdKey = Exclude<keyof ThresholdSettings, NestedThresholdKey>;
type KeywordCategoryKey = keyof KeywordCategories;

// --- Initial Default State ---
const initialKeywordCategories: KeywordCategories = {
    analytical: { enabled: true, weight: 1.0, keywords: "analyze, evaluate, assess, research, investigate, study, examine, review, diagnose, audit, survey, inspect" },
    comparative: { enabled: true, weight: 1.5, keywords: "compare, contrast, differentiate, versus, pros and cons, trade-off, benchmark, measure against, weigh, rank" },
    creative: { enabled: true, weight: 2.0, keywords: "design, create, optimize, improve, innovate, develop, build, construct, craft, devise, formulate, invent" },
    complex: { enabled: true, weight: 2.5, keywords: "hypothesize, synthesize, debate, refactor, architect, theorize, model, simulate, predict, extrapolate, integrate, transform, restructure" },
};

const initialThresholdSettings: ThresholdSettings = {
    wordCountBase: { high: 50, medium: 20 },
    scalingFactor: { high: 5, medium: 2 },
    confidenceThreshold: 0.5,
    deadlinePressureThreshold: 0.5,
    categoryOverlapBonus: 0.5,
};

const initialAutotuneSettings: AutotuneSettings = {
    enabled: true, analysisThreshold: 100, retainHistory: true, historyLimit: 1000
};

const defaultSettings: AllSettings = {
    keywordCategories: initialKeywordCategories,
    thresholdSettings: initialThresholdSettings,
    autotuneSettings: initialAutotuneSettings,
};

// --- Sub-Component for Keyword Category Settings ---
interface KeywordCategorySettingsProps {
    categoryKey: KeywordCategoryKey;
    settings: KeywordCategory;
    onChange: (
        category: KeywordCategoryKey,
        field: keyof KeywordCategory,
        value: boolean | number | string
    ) => void;
}

const KeywordCategorySettings: React.FC<KeywordCategorySettingsProps> = React.memo(({
    categoryKey, settings, onChange
}) => {
    const handleSwitchChange = useCallback((checked: boolean) => {
        onChange(categoryKey, "enabled", checked);
    }, [onChange, categoryKey]);

    const handleSliderChange = useCallback((value: number[]) => {
        onChange(categoryKey, "weight", value[0]);
    }, [onChange, categoryKey]);

    const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        onChange(categoryKey, "keywords", e.target.value);
    }, [onChange, categoryKey]);

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <Label htmlFor={`${categoryKey}-enabled`}>Enabled</Label>
                <Switch
                    id={`${categoryKey}-enabled`}
                    checked={settings.enabled}
                    onCheckedChange={handleSwitchChange}
                    aria-labelledby={`${categoryKey}-label`}
                />
            </div>

            <div className="space-y-2">
                <div className="flex justify-between">
                    <Label htmlFor={`${categoryKey}-weight`}>Weight: {settings.weight.toFixed(1)}</Label>
                </div>
                <Slider
                    id={`${categoryKey}-weight`}
                    min={0.1} max={5} step={0.1}
                    value={[settings.weight]}
                    onValueChange={handleSliderChange}
                    disabled={!settings.enabled}
                    aria-label={`${categoryKey} weight`}
                />
            </div>

            <div className="space-y-2">
                <Label htmlFor={`${categoryKey}-keywords`}>Keywords (comma separated)</Label>
                <Input
                    id={`${categoryKey}-keywords`}
                    value={settings.keywords}
                    onChange={handleInputChange}
                    disabled={!settings.enabled}
                    placeholder="e.g., analyze, evaluate, compare"
                />
                 {/* TODO: Add keyword validation (e.g., ensure comma separation) */}
            </div>
        </div>
    );
});
KeywordCategorySettings.displayName = 'KeywordCategorySettings'; // For React DevTools

// --- Main Component ---
const TaskFactorySettings: React.FC = () => {
    const [keywordCategories, setKeywordCategories] = useState<KeywordCategories>(defaultSettings.keywordCategories);
    const [thresholdSettings, setThresholdSettings] = useState<ThresholdSettings>(defaultSettings.thresholdSettings);
    const [autotuneSettings, setAutotuneSettings] = useState<AutotuneSettings>(defaultSettings.autotuneSettings);
    const { toast } = useToast();

    // --- State Update Handlers (Memoized) ---
    const handleCategoryChange = useCallback((
        category: keyof KeywordCategories,
        field: keyof KeywordCategory,
        value: boolean | number | string
    ) => {
        setKeywordCategories((prev) => ({
            ...prev,
            [category]: { ...prev[category], [field]: value },
        }));
    }, []);

    const handleThresholdChange = useCallback((
        section: NestedThresholdKey,
        field: keyof (typeof thresholdSettings)[typeof section],
        value: number
    ) => {
        setThresholdSettings((prev) => ({
            ...prev,
            [section]: { ...(prev[section] as Record<string, number>), [field]: value, },
        }));
    }, []);

    const handleSimpleThresholdChange = useCallback((field: FlatThresholdKey, value: number) => {
        setThresholdSettings((prev) => ({ ...prev, [field]: value }));
    }, []);

    const handleAutotuneChange = useCallback((field: keyof AutotuneSettings, value: boolean | number) => {
        setAutotuneSettings((prev) => ({ ...prev, [field]: value }));
    }, []);

    // --- Actions ---
    const saveSettings = useCallback(async () => {
         const currentSettings: AllSettings = { keywordCategories, thresholdSettings, autotuneSettings };
         console.log("Saving settings:", currentSettings);

        // Placeholder for API call
        try {
            // const response = await fetch('/api/settings/task-factory', {
            //     method: 'POST',
            //     headers: { 'Content-Type': 'application/json' },
            //     body: JSON.stringify(currentSettings),
            // });
            // if (!response.ok) {
            //     throw new Error('Failed to save settings');
            // }
            // const result = await response.json();
            // console.log("Save successful:", result);

             // Simulate API call delay
             await new Promise(resolve => setTimeout(resolve, 500));

             toast({
                 title: "Settings Saved",
                 description: "Task factory configuration updated successfully.",
             });
        } catch (error) {
             console.error("Error saving settings:", error);
             toast({
                 variant: "destructive",
                 title: "Save Failed",
                 description: error instanceof Error ? error.message : "Could not save settings.",
             });
        }
         // TODO: Implement actual API call to persist settings.
         // TODO: Add validation before attempting to save.
     }, [keywordCategories, thresholdSettings, autotuneSettings, toast]);

    const resetDefaults = useCallback(() => {
        // Use window.confirm for simplicity, consider a custom modal dialog for better UX
        if (window.confirm("Are you sure you want to reset all settings to defaults? Unsaved changes will be lost.")) {
             setKeywordCategories(defaultSettings.keywordCategories);
             setThresholdSettings(defaultSettings.thresholdSettings);
             setAutotuneSettings(defaultSettings.autotuneSettings);
             toast({
                 title: "Settings Reset",
                 description: "All settings reverted to their default values.",
             });
        }
    }, [toast]); // Include toast

     // Memoize category keys to prevent re-renders of the accordion map
     const categoryKeys = useMemo(() => Object.keys(keywordCategories) as KeywordCategoryKey[], [keywordCategories]);


    return (
        <div className="p-4 md:p-6 lg:p-8 max-w-4xl mx-auto">
            <Tabs defaultValue="keywords" className="space-y-6">
                <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4 mb-4">
                    <h1 className="text-2xl font-semibold text-foreground">Task Factory Settings</h1>
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
                            <CardDescription>Configure how keyword types affect task complexity scoring.</CardDescription>
                        </CardHeader>
                        <CardContent>
                             {/* TODO: Consider adding a way to add/remove categories dynamically */}
                            <Accordion type="multiple" defaultValue={categoryKeys} className="w-full">
                                {categoryKeys.map((category) => (
                                    <AccordionItem value={category} key={category}>
                                        <AccordionTrigger id={`${category}-label`} className="capitalize text-base hover:no-underline">
                                             {category}
                                             <span className="ml-auto pl-4 text-sm font-normal text-muted-foreground">
                                                 (Weight: {keywordCategories[category].weight.toFixed(1)})
                                             </span>
                                         </AccordionTrigger>
                                        <AccordionContent>
                                             <KeywordCategorySettings
                                                 categoryKey={category}
                                                 settings={keywordCategories[category]}
                                                 onChange={handleCategoryChange}
                                             />
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
                            <CardDescription>Configure word count thresholds, scaling factors, and other parameters.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-8">
                             {/* Word Count & Scaling */}
                             <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
                                <div className="space-y-4 border-b md:border-b-0 md:border-r md:pr-8 pb-4 md:pb-0">
                                    <h3 className="text-base font-semibold mb-3">Word Count Base Thresholds</h3>
                                    <div className="space-y-2">
                                        <Label>HIGH Effort Threshold: {thresholdSettings.wordCountBase.high} words</Label>
                                        <Slider min={10} max={100} step={1} value={[thresholdSettings.wordCountBase.high]} onValueChange={v => handleThresholdChange("wordCountBase", "high", v[0])} />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>MEDIUM Effort Threshold: {thresholdSettings.wordCountBase.medium} words</Label>
                                        <Slider min={5} max={50} step={1} value={[thresholdSettings.wordCountBase.medium]} onValueChange={v => handleThresholdChange("wordCountBase", "medium", v[0])} />
                                    </div>
                                </div>
                                <div className="space-y-4">
                                    <h3 className="text-base font-semibold mb-3">Scaling Factors</h3>
                                    <div className="space-y-2">
                                        <Label>HIGH Scaling Factor: {thresholdSettings.scalingFactor.high.toFixed(1)}</Label>
                                        <Slider min={0} max={10} step={0.5} value={[thresholdSettings.scalingFactor.high]} onValueChange={v => handleThresholdChange("scalingFactor", "high", v[0])} />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>MEDIUM Scaling Factor: {thresholdSettings.scalingFactor.medium.toFixed(1)}</Label>
                                        <Slider min={0} max={5} step={0.5} value={[thresholdSettings.scalingFactor.medium]} onValueChange={v => handleThresholdChange("scalingFactor", "medium", v[0])} />
                                    </div>
                                </div>
                            </div>

                             {/* Other Thresholds */}
                            <div className="pt-6 border-t space-y-6">
                                <h3 className="text-base font-semibold">Other Thresholds</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
                                    <div className="space-y-2">
                                        <Label>Confidence Threshold: {(thresholdSettings.confidenceThreshold ?? 0).toFixed(2)}</Label>
                                        <Slider min={0.1} max={0.9} step={0.05} value={[thresholdSettings.confidenceThreshold ?? 0]} onValueChange={v => handleSimpleThresholdChange("confidenceThreshold", v[0])} />
                                        <p className="text-xs text-muted-foreground">Tasks below this confidence get bumped up one effort level.</p>
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Deadline Pressure Threshold: {(thresholdSettings.deadlinePressureThreshold ?? 0).toFixed(2)}</Label>
                                        <Slider min={0.1} max={0.9} step={0.05} value={[thresholdSettings.deadlinePressureThreshold ?? 0]} onValueChange={v => handleSimpleThresholdChange("deadlinePressureThreshold", v[0])} />
                                        <p className="text-xs text-muted-foreground">Tasks above this deadline pressure are bumped to HIGH effort.</p>
                                    </div>
                                </div>
                                <div className="space-y-2">
                                     <Label>Category Overlap Bonus: {(thresholdSettings.categoryOverlapBonus ?? 0).toFixed(1)}</Label>
                                     <Slider min={0} max={2} step={0.1} value={[thresholdSettings.categoryOverlapBonus ?? 0]} onValueChange={v => handleSimpleThresholdChange("categoryOverlapBonus", v[0])} />
                                     <p className="text-xs text-muted-foreground">Bonus applied per additional category when a task spans multiple.</p>
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
                            <CardDescription>Configure how the system learns from task outcomes to adjust weights.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-8">
                            <div className="flex items-center justify-between pb-4 border-b">
                                <div>
                                    <h3 className="text-base font-semibold">Enable Auto-Tuning</h3>
                                    <p className="text-sm text-muted-foreground">Automatically adjust category weights based on task outcomes.</p>
                                </div>
                                <Switch checked={autotuneSettings.enabled} onCheckedChange={c => handleAutotuneChange("enabled", c)} />
                            </div>

                            <div className={`space-y-6 ${!autotuneSettings.enabled ? 'opacity-50 pointer-events-none' : ''}`}>
                                <div className="space-y-2">
                                     <Label>Analysis Threshold: {autotuneSettings.analysisThreshold} tasks</Label>
                                     <Slider disabled={!autotuneSettings.enabled} min={10} max={500} step={10} value={[autotuneSettings.analysisThreshold]} onValueChange={v => handleAutotuneChange("analysisThreshold", v[0])} />
                                     <p className="text-xs text-muted-foreground">Number of completed tasks needed before analyzing patterns and tuning weights.</p>
                                </div>
                                <div className="flex items-center justify-between">
                                     <div>
                                         <h3 className="text-sm font-medium">Retain Task History</h3>
                                         <p className="text-xs text-muted-foreground">Keep analyzed task outcome history after tuning.</p>
                                     </div>
                                     <Switch disabled={!autotuneSettings.enabled} checked={autotuneSettings.retainHistory} onCheckedChange={c => handleAutotuneChange("retainHistory", c)} />
                                 </div>
                                 <div className="space-y-2">
                                     <Label>History Limit: {autotuneSettings.historyLimit} tasks</Label>
                                     <Slider disabled={!autotuneSettings.enabled || !autotuneSettings.retainHistory} min={100} max={10000} step={100} value={[autotuneSettings.historyLimit]} onValueChange={v => handleAutotuneChange("historyLimit", v[0])} />
                                     <p className="text-xs text-muted-foreground">Maximum number of historical tasks to retain if history is enabled.</p>
                                 </div>
                             </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Action Buttons Footer */}
                <div className="mt-8 flex justify-between items-center">
                    <Button variant="outline" onClick={resetDefaults}>Reset to Defaults</Button>
                    <Button onClick={saveSettings}>Save Settings</Button>
                </div>
            </Tabs>
        </div>
    );
};

export default TaskFactorySettings;