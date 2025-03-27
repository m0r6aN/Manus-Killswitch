# task_factory.py

from backend.models.models import Task, TaskEvent, MessageIntent, ReasoningEffort
from enum import Enum
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import datetime as dt
import re
from collections import Counter

class TaskFactory:
    # Version tracking
    VERSION = "1.0.0"
    
    # Outcome tracking for future model improvement
    outcome_history = []
    
    # Keyword categories with their respective weights
    KEYWORD_WEIGHTS = {
        "analytical": {
            "keywords": {"analyze", "evaluate", "assess", "research", "investigate", "study", 
                        "examine", "review", "diagnose", "audit", "survey", "inspect"},
            "weight": 1.0
        },
        "comparative": {
            "keywords": {"compare", "contrast", "differentiate", "versus", "pros and cons", 
                        "trade-off", "benchmark", "measure against", "weigh", "rank"},
            "weight": 1.5
        },
        "creative": {
            "keywords": {"design", "create", "optimize", "improve", "innovate", "develop",
                        "build", "construct", "craft", "devise", "formulate", "invent"},
            "weight": 2.0
        },
        "complex": {
            "keywords": {"hypothesize", "synthesize", "debate", "refactor", "architect",
                        "theorize", "model", "simulate", "predict", "extrapolate", 
                        "integrate", "transform", "restructure"},
            "weight": 2.5
        }
    }
    
    # Task events categorized by typical reasoning effort
    EVENT_EFFORT_MAP = {
        "high": {"refine", "escalate", "analyze", "evaluate", "compare", "refactor"},
        "medium": {"plan", "execute"},
        "low": {"complete"}
    }
    
    # Base thresholds for word count
    WORD_COUNT_THRESHOLDS = {
        "base": {
            "high": 50,
            "medium": 20
        },
        # How much to reduce threshold per point of complexity score
        "scaling_factor": {
            "high": 5,
            "medium": 2
        }
    }
    
    @staticmethod
    def count_keyword_occurrences(content: str, keywords: set) -> int:
        """Count all occurrences of each keyword in the content."""
        content_lower = content.lower()
        count = 0
        
        # Handle multi-word keywords
        for keyword in keywords:
            if " " in keyword:
                count += content_lower.count(keyword)
            else:
                # For single-word keywords, ensure we match whole words
                count += len(re.findall(r'\b' + re.escape(keyword) + r'\b', content_lower))
                
        return count
    
    @staticmethod
    def calculate_complexity_score(content: str) -> Tuple[float, Dict[str, int]]:
        """Calculate complexity score based on keyword categories with detailed breakdown."""
        scores_by_category = {}
        total_score = 0.0
        
        for category, data in TaskFactory.KEYWORD_WEIGHTS.items():
            category_count = TaskFactory.count_keyword_occurrences(content, data["keywords"])
            category_score = category_count * data["weight"]
            
            scores_by_category[category] = category_count
            total_score += category_score
        
        # Apply category overlap penalty - if task spans multiple domains, it's likely more complex
        active_categories = sum(1 for count in scores_by_category.values() if count > 0)
        if active_categories > 2:
            overlap_bonus = 0.5 * (active_categories - 2)
            total_score += overlap_bonus
            scores_by_category["overlap_bonus"] = overlap_bonus
            
        return total_score, scores_by_category
    
    @staticmethod
    def estimate_reasoning_effort(
        content: str, 
        event: Optional[str] = None, 
        intent: Optional[str] = None,
        confidence: Optional[float] = None
    ) -> Tuple[ReasoningEffort, Dict[str, any]]:
        """
        Estimate the reasoning effort required for a task based on multiple factors.
        Returns the effort level and a diagnostic object explaining the decision.
        """
        diagnostics = {
            "word_count": 0,
            "complexity_score": 0.0,
            "category_scores": {},
            "base_effort": None,
            "event_adjustment": None,
            "intent_adjustment": None,
            "confidence_adjustment": None,
            "final_effort": None
        }
        
        # Calculate complexity score and get diagnostic data
        complexity_score, category_scores = TaskFactory.calculate_complexity_score(content)
        word_count = len(content.split())
        
        diagnostics["word_count"] = word_count
        diagnostics["complexity_score"] = complexity_score
        diagnostics["category_scores"] = category_scores
        
        # Calculate dynamic thresholds based on complexity
        high_threshold = max(10, TaskFactory.WORD_COUNT_THRESHOLDS["base"]["high"] - 
                            (complexity_score * TaskFactory.WORD_COUNT_THRESHOLDS["scaling_factor"]["high"]))
        medium_threshold = max(5, TaskFactory.WORD_COUNT_THRESHOLDS["base"]["medium"] - 
                            (complexity_score * TaskFactory.WORD_COUNT_THRESHOLDS["scaling_factor"]["medium"]))
        
        # Determine base effort from content complexity and length
        if complexity_score >= 3 or word_count > high_threshold:
            base_effort = ReasoningEffort.HIGH
        elif complexity_score >= 1 or word_count > medium_threshold:
            base_effort = ReasoningEffort.MEDIUM
        else:
            base_effort = ReasoningEffort.LOW
            
        diagnostics["base_effort"] = base_effort.value
        diagnostics["thresholds"] = {
            "high": high_threshold,
            "medium": medium_threshold
        }
        
        # Final effort starts with base effort
        final_effort = base_effort
        
        # Event-based adjustment
        if event:
            for effort_level, events in TaskFactory.EVENT_EFFORT_MAP.items():
                if event in events:
                    event_effort = ReasoningEffort(effort_level)
                    if event_effort.value == "high":
                        final_effort = ReasoningEffort.HIGH
                        diagnostics["event_adjustment"] = f"Increased to HIGH due to {event} event"
                    elif event_effort.value == "medium" and final_effort == ReasoningEffort.LOW:
                        final_effort = ReasoningEffort.MEDIUM
                        diagnostics["event_adjustment"] = f"Increased to MEDIUM due to {event} event"
                    break
        
        # Intent-based adjustment
        if intent == "modify_task":
            if final_effort != ReasoningEffort.HIGH:
                final_effort = ReasoningEffort.HIGH
                diagnostics["intent_adjustment"] = "Increased to HIGH due to modify_task intent"
        
        # Confidence-based adjustment
        if confidence is not None and confidence < 0.7:
            if final_effort == ReasoningEffort.LOW:
                final_effort = ReasoningEffort.MEDIUM
                diagnostics["confidence_adjustment"] = f"Increased to MEDIUM due to low confidence ({confidence})"
            elif final_effort == ReasoningEffort.MEDIUM:
                final_effort = ReasoningEffort.HIGH
                diagnostics["confidence_adjustment"] = f"Increased to HIGH due to low confidence ({confidence})"
                
        # Edge case guardrail: Complex keywords should never result in LOW effort
        complex_count = diagnostics["category_scores"].get("complex", 0)
        if complex_count > 0 and final_effort == ReasoningEffort.LOW:
            final_effort = ReasoningEffort.MEDIUM
            diagnostics["category_adjustment"] = "Bumped to MEDIUM due to presence of complex keywords"
                
        diagnostics["final_effort"] = final_effort.value
        
        return final_effort, diagnostics
    
    @classmethod
    def record_task_outcome(cls, task_id: str, diagnostics: Dict, actual_duration: float, 
                           success: bool, feedback: Optional[str] = None) -> None:
        """
        Record the outcome of a task for future model refinement.
        
        Parameters:
        - task_id: The ID of the completed task
        - diagnostics: The diagnostic data returned when creating the task
        - actual_duration: How long the task took to complete (seconds)
        - success: Whether the task completed successfully
        - feedback: Optional feedback about the task difficulty
        """
        outcome_data = {
            "task_id": task_id,
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "diagnostics": diagnostics,
            "actual_duration": actual_duration,
            "success": success,
            "feedback": feedback
        }
        
        cls.outcome_history.append(outcome_data)
        
        # If we have a lot of data, we could periodically analyze and adjust weights
        if len(cls.outcome_history) >= 100:
            cls._analyze_outcomes()
    
    @classmethod
    def _analyze_outcomes(cls) -> None:
        """Analyze recorded outcomes to potentially refine the model."""
        # This would be implemented to analyze outcomes and adjust weights
        # For now, we'll just keep it as a placeholder
        print(f"Analyzing {len(cls.outcome_history)} task outcomes for model refinement")
        
        # Reset history after analysis (or keep a rolling window)
        cls.outcome_history = cls.outcome_history[-100:]
    
    @classmethod
    def create_task(
        cls,
        task_id: str,
        agent: str,
        content: str,
        target_agent: str,
        intent: MessageIntent = MessageIntent.START_TASK,
        event: TaskEvent = TaskEvent.PLAN,
        confidence: Optional[float] = 0.9,
        timestamp: Optional[datetime] = None,
        priority: Optional[int] = None,
        deadline_pressure: Optional[float] = None
    ) -> Tuple[Task, Dict]:
        """
        Create a Task object with dynamically estimated reasoning effort.
        Returns both the Task and diagnostic information about the reasoning effort estimation.
        
        Parameters:
        - task_id: Unique identifier for the task
        - agent: The agent creating the task
        - content: The task description
        - target_agent: The agent who will perform the task
        - intent: The message intent
        - event: The task event type
        - confidence: Confidence level in this task (0.0-1.0)
        - timestamp: When the task was created (default: now)
        - priority: Optional priority level (higher = more important)
        - deadline_pressure: Optional value indicating time pressure (0.0-1.0)
        """
        # Add context factors to diagnostics for comprehensive tracking
        context_factors = {
            "priority": priority,
            "deadline_pressure": deadline_pressure
        }
        
        reasoning_effort, diagnostics = cls.estimate_reasoning_effort(
            content, 
            event.value, 
            intent.value,
            confidence
        )
        
        # Add context factors to diagnostics
        diagnostics["context_factors"] = context_factors
        
        # Consider deadline pressure in effort estimation
        if deadline_pressure is not None and deadline_pressure > 0.8:
            # High deadline pressure can increase effort level
            if reasoning_effort != ReasoningEffort.HIGH:
                prev_effort = reasoning_effort
                reasoning_effort = ReasoningEffort.HIGH
                diagnostics["deadline_adjustment"] = f"Increased from {prev_effort.value} to HIGH due to high deadline pressure ({deadline_pressure})"
        
        task = Task(
            task_id=task_id,
            agent=agent,
            content=content,
            intent=intent,
            target_agent=target_agent,
            event=event,
            confidence=confidence,
            timestamp=timestamp or dt.datetime.now(dt.timezone.utc),
            reasoning_effort=reasoning_effort
        )
        
        # Store diagnostics with version info for future reference
        diagnostics["model_version"] = cls.VERSION
        
        return task, diagnostics