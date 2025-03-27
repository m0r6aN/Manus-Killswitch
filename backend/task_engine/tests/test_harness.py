# test_harness.py

from task_factory import TaskFactory
from backend.models.models import TaskEvent, MessageIntent, ReasoningEffort
import json
import matplotlib.pyplot as plt
import pandas as pd
from typing import List, Dict, Any
import random
import time

def visualize_results(tasks_data: List[Dict[str, Any]]):
    """Create visualizations of the task factory results"""
    # Convert to DataFrame for easier analysis
    df = pd.DataFrame(tasks_data)
    
    # Setup the visualization
    plt.figure(figsize=(15, 10))
    
    # Plot 1: Effort distribution
    plt.subplot(2, 2, 1)
    effort_counts = df['effort'].value_counts()
    effort_counts.plot(kind='bar', color=['green', 'orange', 'red'])
    plt.title('Distribution of Reasoning Effort')
    plt.xlabel('Effort Level')
    plt.ylabel('Count')
    
    # Plot 2: Complexity score vs. Word count
    plt.subplot(2, 2, 2)
    plt.scatter(df['word_count'], df['complexity_score'], 
                c=df['effort'].map({'low': 'green', 'medium': 'orange', 'high': 'red'}), 
                s=100, alpha=0.7)
    plt.title('Complexity Score vs. Word Count')
    plt.xlabel('Word Count')
    plt.ylabel('Complexity Score')
    
    # Plot 3: Factors that led to effort level changes
    plt.subplot(2, 2, 3)
    adjustment_types = ['event_adjustment', 'intent_adjustment', 
                        'confidence_adjustment', 'category_adjustment', 'deadline_adjustment']
    adjustment_counts = []
    
    for adj_type in adjustment_types:
        # Count non-null adjustments
        count = sum(1 for task in tasks_data if task.get(adj_type) is not None)
        adjustment_counts.append(count)
    
    plt.bar(adjustment_types, adjustment_counts, color='skyblue')
    plt.title('Factors Leading to Effort Adjustments')
    plt.xlabel('Adjustment Factor')
    plt.ylabel('Count')
    plt.xticks(rotation=45)
    
    # Plot 4: Keyword category distribution
    plt.subplot(2, 2, 4)
    
    # Aggregate keyword counts across all tasks
    category_totals = {'analytical': 0, 'comparative': 0, 'creative': 0, 'complex': 0}
    
    for task in tasks_data:
        for category, count in task.get('category_scores', {}).items():
            if category in category_totals:
                category_totals[category] += count
    
    plt.bar(category_totals.keys(), category_totals.values(), color=['blue', 'purple', 'orange', 'red'])
    plt.title('Keyword Category Distribution')
    plt.xlabel('Category')
    plt.ylabel('Total Occurrences')
    
    plt.tight_layout()
    plt.savefig('task_factory_analysis.png')
    plt.show()

def simulate_execution_time(effort: ReasoningEffort) -> float:
    """Simulate task execution time based on effort level"""
    base_times = {
        "low": 30.0,  # 30 seconds base time for LOW
        "medium": 120.0,  # 2 minutes base time for MEDIUM
        "high": 300.0  # 5 minutes base time for HIGH
    }
    
    # Add some randomness to simulate reality
    base_time = base_times[effort.value]
    variation = random.uniform(0.8, 1.2)  # 20% variance
    
    return base_time * variation

def run_test_harness():
    """Run the test harness for the Task Factory"""
    test_tasks = [
        {
            "task_id": "T001",
            "agent": "Alice",
            "content": "Analyze the data and review findings",
            "target_agent": "Bob",
            "event": TaskEvent.ANALYZE,
            "confidence": 0.9,
            "deadline_pressure": 0.5
        },
        {
            "task_id": "T002",
            "agent": "Bob",
            "content": "Design a new system to optimize workflows and refactor the old one",
            "target_agent": "Charlie",
            "event": TaskEvent.PLAN,
            "confidence": 0.6,
            "deadline_pressure": 0.9
        },
        {
            "task_id": "T003",
            "agent": "Charlie",
            "content": "Execute this simple step",
            "target_agent": "Alice",
            "event": TaskEvent.EXECUTE,
            "confidence": 0.95
        },
        {
            "task_id": "T004",
            "agent": "Dave",
            "content": "Refactor now",
            "target_agent": "Eve",
            "event": TaskEvent.REFACTOR,
            "confidence": 0.8
        },
        {
            "task_id": "T005",
            "agent": "Alice",
            "content": "Compare approaches A and B, then synthesize a new solution",
            "target_agent": "Bob",
            "event": TaskEvent.COMPARE,
            "confidence": 0.7
        },
        {
            "task_id": "T006",
            "agent": "Bob",
            "content": "Run a quick benchmark test",
            "target_agent": "Charlie",
            "event": TaskEvent.EXECUTE,
            "confidence": 0.95,
            "deadline_pressure": 0.3
        },
        {
            "task_id": "T007",
            "agent": "Charlie",
            "content": "Analyze the data, redesign the architecture, optimize the performance, and refactor the legacy code",
            "target_agent": "Alice",
            "event": TaskEvent.PLAN,
            "confidence": 0.5,
            "deadline_pressure": 0.8
        },
        {
            "task_id": "T008",
            "agent": "Dave",
            "content": "Can you check on this?",
            "target_agent": "Eve",
            "event": TaskEvent.CHECK_STATUS,
            "intent": MessageIntent.CHECK_STATUS,
            "confidence": 0.9
        }
    ]

    results = []
    
    print("=" * 80)
    print("TASK FACTORY TEST HARNESS")
    print("=" * 80)

    for i, task_data in enumerate(test_tasks):
        print(f"\nTEST CASE {i+1}/{len(test_tasks)}")
        print("-" * 40)
        print(f"Content: \"{task_data['content']}\"")
        print(f"Agent: {task_data['agent']} → {task_data['target_agent']}")
        print(f"Event: {task_data['event'].value}")
        
        start_time = time.time()
        task, diagnostics = TaskFactory.create_task(**task_data)
        processing_time = time.time() - start_time
        
        print(f"\nRESULTS:")
        print(f"⚡ Reasoning Effort: {task.reasoning_effort.value.upper()}")
        print(f"📊 Complexity Score: {diagnostics['complexity_score']:.2f}")
        print(f"📝 Word Count: {diagnostics['word_count']}")
        
        # Show category breakdowns
        print("\nCategory Scores:")
        for category, score in diagnostics['category_scores'].items():
            if score > 0:
                print(f"  - {category}: {score}")
                
        # Show adjustments
        adjustments = []
        for key in diagnostics:
            if key.endswith('_adjustment') and diagnostics[key] is not None:
                adjustments.append(diagnostics[key])
                
        if adjustments:
            print("\nAdjustments:")
            for adj in adjustments:
                print(f"  - {adj}")
                
        # Simulate task execution
        simulated_time = simulate_execution_time(task.reasoning_effort)
        
        # Record the outcome
        TaskFactory.record_task_outcome(
            task_id=task.task_id,
            diagnostics=diagnostics,
            actual_duration=simulated_time,
            success=random.random() > 0.1,  # 90% success rate
            feedback="Task difficulty was appropriate" if random.random() > 0.3 else "Task was more difficult than expected"
        )
        
        # Store for visualization
        task_result = {
            'task_id': task.task_id,
            'content': task.content,
            'effort': task.reasoning_effort.value,
            'complexity_score': diagnostics['complexity_score'],
            'word_count': diagnostics['word_count'],
            'category_scores': diagnostics['category_scores'],
            'event': task_data['event'].value,
            'execution_time': simulated_time
        }
        
        # Add any adjustments
        for key in diagnostics:
            if key.endswith('_adjustment'):
                task_result[key] = diagnostics[key]
                
        results.append(task_result)
        
        print(f"\nExecution stats:")
        print(f"  - Processing time: {processing_time*1000:.2f}ms")
        print(f"  - Simulated execution: {simulated_time:.2f}s")
        
    print("\n" + "=" * 80)
    print(f"Completed {len(test_tasks)} test cases")
    print(f"Stored {len(TaskFactory.outcome_history)} outcomes for future tuning")
    
    # Visualize the results
    visualize_results(results)
    
    return results

if __name__ == "__main__":
    results = run_test_harness()
    print("\nSaving diagnostics to task_factory_results.json")
    with open("task_factory_results.json", "w") as f:
        json.dump(results, f, indent=2)