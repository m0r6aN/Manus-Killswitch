# Manus Killswitch AI Agent Framework: Technical Specifications

**Version**: 1.0.0  
**Date**: March 26, 2025  
**Author**: [Your Name]  
**License**: PolyForm Noncommercial License 1.0.0 (transitioning to Apache License 2.0 post-market launch)

---

## 1. Overview

### 1.1 Purpose
The **Manus Killswitch AI Agent Framework** is a high-performance, multi-agent collaboration system engineered to dominate complex tasks, counter unchecked AI threats (e.g., "Manus"), and deliver enterprise-grade solutions. It leverages structured workflows, real-time communication, and self-optimizing agents to achieve superior outcomes through teamwork and advanced reasoning.

### 1.2 Scope
This document details the architecture, components, protocols, and technical requirements of the framework. It serves as a comprehensive blueprint for implementation, deployment, and extension, showcasing expertise in distributed systems, AI orchestration, and scalable software design.

### 1.3 Key Objectives
- Enable seamless multi-agent coordination via Redis and WebSockets.
- Provide a containerized, scalable architecture for isolation and flexibility.
- Implement self-optimization through success metrics and reinforcement learning.
- Deliver an interactive, real-time frontend for system management.

---

## 2. System Architecture

### 2.1 Frontend
- **Framework**: Next.js (React) with App Router
- **Components**: React components styled with Tailwind CSS and shadcn/ui
- **Communication**: WebSocket integration via Socket.IO for real-time updates
- **Layout**: Four-column interface
  - Sidebar: Navigation
  - Chat List: Session overview
  - Chat Content: Real-time conversation display
  - Code Panel: Tool/script interaction
- **Port**: 3000

### 2.2 WebSocket Server
- **Framework**: FastAPI
- **Role**: Middleware between frontend and agents
- **Functions**:
  - Routes messages via Redis channels
  - Monitors agent heartbeats
  - Ensures agent readiness before connections
- **Port**: 8000

### 2.3 Redis Communication
- **Role**: Message broker and data store
- **Features**:
  - Pub/sub messaging via dedicated channels
  - Task queues and heartbeat storage
- **Port**: 6379

### 2.4 Docker Containerization & Networking
- **Orchestration**: Docker Compose
- **Network**: Custom `ai-network` for hostname resolution
- **Container Structure**:
  - `frontend`: Next.js app (port 3000)
  - `websocket-server`: FastAPI server (port 8000)
  - `redis`: Redis instance (port 6379)
  - `grok-agent`: Grok AI agent
  - `claude-agent`: Claude AI agent
  - `gpt-agent`: GPT-4o AI agent
  - `tools-agent`: Tool execution/registry
- **Features**:
  - Isolated containers with shared volumes for logs/configs
  - Health checks for dependency readiness
  - Horizontal scaling via `docker-compose up --scale`

### 2.5 Agent Framework
- **Base Class**: `BaseAgent`
- **Capabilities**:
  - Redis message routing
  - WebSocket-based communication
  - Task/message deserialization/serialization
  - Periodic heartbeats (e.g., `{agent_name}_heartbeat = "alive"`)
  - Intent-aware dispatching

### 2.6 ToolCore: Universal Tool Registry & Execution Engine
- **Container**: `tools-agent`
- **Database**: SQLite (`toolstore.db`)
  - **Schema**:
    ```sql
    CREATE TABLE tools (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        description TEXT,
        parameters TEXT, -- JSON schema
        path TEXT, -- Filesystem location
        entrypoint TEXT, -- Method name
        type TEXT, -- 'script', 'function', 'module'
        version TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        tags TEXT, -- JSON or comma-separated
        active BOOLEAN DEFAULT 1
    );
    ```
- **API**:
  - REST/gRPC endpoints: `POST /tools`, `GET /tools`, `GET /tools/{name}`, `PUT /tools/{name}`, `DELETE /tools/{name}`, `POST /execute`
  - Dry-run mode for input/output validation
- **Execution**:
  - Inline Python snippets (DB-stored, `exec`/`eval`)
  - File-based scripts (`.py`, `importlib`)
  - Package-based modules
- **Discovery**: Agents query tools by tags, type, or description
- **Filesystem**:
  ```
  /tools
    ├── normalize_data.py
    ├── analyze_sentiment.py
    ├── fetch_stock_prices.py
  /toolcore
    ├── db/
    ├── api/
    ├── executor/
    ├── loader/
  ```
- **Security**: Isolated execution (subprocesses/containers), versioning, audit logging
- **Future**: Tool ratings, analytics, chaining, LLM-generated wrappers

---

## 3. Agent Roles & Responsibilities

### 3.1 Claude: Arbitration & Reconciliation
- **Functions**:
  - Evaluates responses with confidence metrics/semantic similarity
  - Detects consensus or confidence differentials
  - Facilitates structured debate via reconciliation protocols
  - Produces outputs with majority positions and dissenting views
- **Controls**: Adjusts thresholds for deadlocks; enforces timeouts

### 3.2 GPT-4o: Backend Operations & Response Refinement
- **Functions**:
  - Refines responses into JSON/Pydantic structures
  - Manages backend communication/API integration
  - Ensures real-time responsiveness
- **Output**: Consistent, formatted data for arbitration

### 3.3 Grok: Moderation & Orchestration
- **Functions**:
  - Manages debate state machine: `propose → critique → refine → conclude`
  - Detects loops/deadlocks; triggers kill switch
  - Coordinates agent transitions; logs moderation
- **Signals**: Orchestration cues for synchronization

---

## 4. Operational Framework

### 4.1 Core Principles
1. **Collaboration**: Structured teamwork outperforms solo efforts
2. **Process Integrity**: Rigorous cycles ensure quality
3. **Critique-Driven**: Feedback refines solutions
4. **Confidence-Based Decisions**: Debate concludes decisively

### 4.2 Debate Protocol
- **Round 1**: Initial positions/reasoning
- **Round 2**: Peer critique
- **Round 3**: Position refinement
- **Round 4+**: Consensus or disagreement clarification

### 4.3 Deadlock Prevention
- **Loop Detection**: Repeated points trigger pivot after 2 rounds
- **Plateau Handling**: Confidence stagnation → majority decision
- **Kill Switch**: Grok-enforced resolution for stalled debates

---

## 5. Communication Protocols

### 5.1 Heartbeats
- **Mechanism**: Agents emit `{agent_name}_heartbeat = "alive"` to Redis
- **Frequency**: Configurable interval (e.g., 5 seconds)
- **Expiry**: TTL-based expiration for health monitoring

### 5.2 Intent-Based Messaging
- **Structure**:
  ```python
  class Message(BaseModel):
      task_id: str
      agent: str
      content: str
      intent: MessageIntent
      timestamp: datetime
  ```
- **Intents**: `CHAT`, `START_TASK`, `CHECK_STATUS`, `MODIFY_TASK`
- **Events**: `PLAN`, `EXECUTE`, `REFINE`, `COMPLETE`, `ESCALATE`

---

## 6. Key Features

### 6.1 TaskFactory & Object Creation
- **Purpose**: Centralizes creation/management of `Message`, `Task`, and `TaskResult` objects, embedding dynamic reasoning effort estimation for optimized resource allocation.
- **Components**:
  - **`TaskFactory`**:
    - **Function**: Creates `Task` objects with effort assessment
    - **Parameters**:
      - `task_id: str`
      - `agent: str`
      - `content: str`
      - `target_agent: str`
      - `intent: MessageIntent` (default: `START_TASK`)
      - `event: TaskEvent` (default: `PLAN`)
      - `confidence: float` (default: 0.9)
      - `timestamp: datetime` (default: UTC now)
    - **Implementation**:
      ```python
      class TaskFactory:
          @staticmethod
          def create_task(task_id: str, agent: str, content: str, target_agent: str, intent: MessageIntent = MessageIntent.START_TASK, event: TaskEvent = TaskEvent.PLAN, confidence: Optional[float] = 0.9, timestamp: Optional[datetime] = None) -> Task:
              reasoning_effort = estimate_reasoning_effort(content, event.value, intent.value)
              return Task(
                  task_id=task_id, agent=agent, content=content, intent=intent, target_agent=target_agent,
                  event=event, confidence=confidence, timestamp=timestamp or dt.datetime.now(dt.timezone.utc),
                  reasoning_effort=reasoning_effort
              )
      ```
  - **`MessageFactory`**:
    - **Function**: Generates `Message` objects
    - **Parameters**:
      - `task_id: str`
      - `agent: str`
      - `content: str`
      - `intent: MessageIntent` (default: `CHAT`)
      - `timestamp: datetime` (default: UTC now)
    - **Implementation**:
      ```python
      class MessageFactory:
          @staticmethod
          def create_message(task_id: str, agent: str, content: str, intent: MessageIntent = MessageIntent.CHAT, timestamp: Optional[datetime] = None) -> Message:
              return Message(
                  task_id=task_id, agent=agent, content=content, intent=intent,
                  timestamp=timestamp or dt.datetime.now(dt.timezone.utc)
              )
      ```
  - **`TaskResultFactory`**:
    - **Function**: Produces `TaskResult` objects
    - **Parameters**:
      - `task_id: str`
      - `agent: str`
      - `content: str`
      - `target_agent: str`
      - `event: TaskEvent`
      - `outcome: TaskOutcome`
      - `contributing_agents: List[str]` (default: [])
      - `confidence: float` (default: 0.9)
      - `reasoning_effort: ReasoningEffort` (optional)
      - `timestamp: datetime` (default: UTC now)
    - **Implementation**:
      ```python
      class TaskResultFactory:
          @staticmethod
          def create_task_result(task_id: str, agent: str, content: str, target_agent: str, event: TaskEvent, outcome: TaskOutcome, contributing_agents: Optional[List[str]] = None, confidence: Optional[float] = 0.9, reasoning_effort: Optional[ReasoningEffort] = None, timestamp: Optional[datetime] = None) -> TaskResult:
              return TaskResult(
                  task_id=task_id, agent=agent, content=content, intent=MessageIntent.MODIFY_TASK, target_agent=target_agent,
                  event=event, outcome=outcome, contributing_agents=contributing_agents or [], confidence=confidence,
                  reasoning_effort=reasoning_effort, timestamp=timestamp or dt.datetime.now(dt.timezone.utc)
              )
      ```
- **Methods**:
  - Keyword-based effort categorization
  - Context-aware adjustments (events, intent, content)
  - Adaptive scoring with outcome-based optimization
- **Integration**:
  - Path: `backend/factories/`
  - Logs effort in agent pipelines
  - Guides retries, timeouts, model selection

### 6.2 Reasoning Effort Estimation
- **Purpose**: Automatically assesses task complexity for resource optimization
- **Enum**:
  ```python
  class ReasoningEffort(str, Enum):
      LOW = "low"
      MEDIUM = "medium"
      HIGH = "high"
  ```
- **Estimation Logic**:
  - **Inputs**:
    - `content: str`
    - `event: Optional[str]`
    - `intent: Optional[str]`
  - **Algorithm**:
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
  - **Rules**:
    - ≤10 words, no keywords → `LOW`
    - >30 words or keywords → `HIGH`
    - Otherwise → `MEDIUM`
    - Override to `HIGH` for `refine`, `escalate`, or `modify_task`
- **Usage**: Embedded in `TaskFactory`; extensible for agent decisions

### 6.3 Additional Capabilities
- Dynamic effort assessment and agent routing
- Real-time task/performance monitoring
- Self-tuning algorithms via reinforcement learning
- Interactive dashboard with WebSocket updates
- Collaborative War Room environment

---

## 7. Technical Stack

### 7.1 Backend
- **FastAPI**: High-performance API framework
- **Redis**: Pub/sub and task queuing
- **WebSockets**: Real-time communication
- **Pydantic**: Data validation/serialization
- **Loguru**: Logging system

### 7.2 Frontend
- **Next.js**: React framework
- **React**: UI rendering
- **TailwindCSS**: Styling framework
- **Recharts**: Visualization library
- **Socket.IO**: WebSocket client
- **shadcn/ui**: UI component library

---

## 8. Installation & Deployment

### 8.1 Prerequisites
- Python 3.10+
- Node.js 18+
- Redis 7
- Docker (optional)

### 8.2 Backend Setup
```bash
git clone https://github.com/[your-org]/ai-task-management-system.git
cd ai-task-management-system
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
redis-server  # Skip if using Docker
cd backend
uvicorn main:app --reload
```

### 8.3 Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### 8.4 Docker Deployment
- **Command**: `docker-compose up --build`
- **Scaling**: `docker-compose up --scale gpt-agent=3`

---

## 9. Use Cases
- Structured AI debates (GPT vs. Claude vs. Grok)
- Real-time task workflows via WebSocket
- Multi-agent arbitration with confidence scoring
- Tool discovery and task decomposition
- Enterprise solution development

---

## 10. Extension & Customization

### 10.1 Adding Agents
- **Base Class**: Extend `BaseAgent`
- **Example**:
  ```python
  class MyAgent(BaseAgent):
      def __init__(self):
          super().__init__(api_key="your_key", agent_name="MyAgent")
      async def get_notes(self):
          return {"agent": "MyAgent", "task_id": "default", "content": "Ready!", "intent": "chat"}
      async def process_response(self, response, agent, ws):
          # Custom logic
          pass
  ```

### 10.2 ToolCore Integration
- Register: `POST /tools`
- Execute: `POST /execute` with parameters

---

## 11. Future Enhancements
- **BYOM**: Custom model integration
- **ML Task Assessment**: Neural network classification
- **Agent Specialization**: Domain expertise
- **Task Dependencies**: Workflow management
- **Analytics**: Performance insights
- **Plugins**: Custom task/integration support
- **Multi-Tenant**: Isolated environments
- **Docker Debug UI**: Container monitoring

---

## 12. Testing
- **TaskFactory**: `python test_harness.py`
- **Backend**: `pytest backend/tests`
- **Frontend**: `cd frontend && npm test`

---

## 13. Documentation
- **Location**: [docs](./docs)
- **Files**:
  - [Architecture Overview](./docs/architecture.md)
  - [TaskFactory Guide](./docs/task-factory.md)
  - [API Reference](./docs/api-reference.md)
  - [Frontend Details](./docs/frontend.md)
  - [Deployment](./docs/deployment.md)

---
