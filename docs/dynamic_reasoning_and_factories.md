# 🧠 Dynamic Reasoning Effort + Task Factory System

## Overview
This system introduces **automated reasoning effort estimation** and centralized **factories** for creating `Message`, `Task`, and `TaskResult` objects within the Manus Killswitch agent network. These tools ensure consistency, reduce boilerplate, and allow agents to intelligently modulate resource usage.

---

## 🎯 Reasoning Effort Estimation

### Enum

```python
class ReasoningEffort(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
```

### Estimation Logic

```python
def estimate_reasoning_effort(content: str, event: Optional[str] = None, intent: Optional[str] = None) -> ReasoningEffort:
    keywords = {"analyze", "evaluate", "optimize", "debate", "compare", "hypothesize", "refactor"}
    word_count = len(content.split())
    has_keywords = any(kw in content.lower() for kw in keywords)

    if word_count <= 10 and not has_keywords:
        effort = ReasoningEffort.LOW
    elif word_count > 30 or has_keywords:
        effort = ReasoningEffort.HIGH
    else:
        effort = ReasoningEffort.MEDIUM

    if event in {"refine", "escalate"} or intent == "modify_task":
        effort = ReasoningEffort.HIGH

    return effort
```

---

## 🏭 Factories

### ✅ `TaskFactory`

```python
class TaskFactory:
    @staticmethod
    def create_task(
        task_id: str,
        agent: str,
        content: str,
        target_agent: str,
        intent: MessageIntent = MessageIntent.START_TASK,
        event: TaskEvent = TaskEvent.PLAN,
        confidence: Optional[float] = 0.9,
        timestamp: Optional[datetime] = None
    ) -> Task:
        reasoning_effort = estimate_reasoning_effort(content, event.value, intent.value)
        return Task(
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
```

---

### 💬 `MessageFactory`

```python
class MessageFactory:
    @staticmethod
    def create_message(
        task_id: str,
        agent: str,
        content: str,
        intent: MessageIntent = MessageIntent.CHAT,
        timestamp: Optional[datetime] = None
    ) -> Message:
        return Message(
            task_id=task_id,
            agent=agent,
            content=content,
            intent=intent,
            timestamp=timestamp or dt.datetime.now(dt.timezone.utc)
        )
```

---

### 🧾 `TaskResultFactory`

```python
class TaskResultFactory:
    @staticmethod
    def create_task_result(
        task_id: str,
        agent: str,
        content: str,
        target_agent: str,
        event: TaskEvent,
        outcome: TaskOutcome,
        contributing_agents: Optional[List[str]] = None,
        confidence: Optional[float] = 0.9,
        reasoning_effort: Optional[ReasoningEffort] = None,
        timestamp: Optional[datetime] = None
    ) -> TaskResult:
        return TaskResult(
            task_id=task_id,
            agent=agent,
            content=content,
            intent=MessageIntent.MODIFY_TASK,
            target_agent=target_agent,
            event=event,
            outcome=outcome,
            contributing_agents=contributing_agents or [],
            confidence=confidence,
            reasoning_effort=reasoning_effort,
            timestamp=timestamp or dt.datetime.now(dt.timezone.utc)
        )
```

---

## 🧩 Integration Tips

- Drop factories into `backend/factories/`
- Estimate effort at task creation time
- Log reasoning effort in agent response pipelines
- Use reasoning effort to guide retry logic, timeouts, or model selection

---

**Built by beasts. For beasts. 🐺**