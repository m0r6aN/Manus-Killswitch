import uuid
import json
import logging
from pydantic import ValidationError
from models import Message, Task, TaskEvent, TaskOutcome, TaskResult, MessageIntent

# Set up proper logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def getChatSchema():
    try:
        # Correctly instantiate a Message object
        chatMessage = Message(
            task_id="default",
            agent='Commander',
            content="Attention all agents. Please report for duty",
            intent=MessageIntent.CHAT
        )
        
        # Properly call the method and format output
        schema = chatMessage.to_json_schema()
        logger.info(f"Chat Message Schema: {json.dumps(schema, indent=2)}")
        return schema
    except ValidationError as e:
        logger.error(f"Validation error creating chat schema: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error creating chat schema: {e}")
        return None
    
def getTaskSchema():
    try:
        # Correctly instantiate a Task object with proper UUID generation
        taskMessage = Task(
            task_id=str(uuid.uuid4()),
            agent="Grok",
            content="Create a project plan for phase 1",
            intent=MessageIntent.START_TASK,
            target_agent="GPT",
            event=TaskEvent.PLAN,  # This was missing in your original
            confidence=0.1
        )
        
        # Properly call the method and format output
        schema = taskMessage.to_json_schema()
        logger.info(f"Task Message Schema: {json.dumps(schema, indent=2)}")
        return schema
    except ValidationError as e:
        logger.error(f"Validation error creating task schema: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error creating task schema: {e}")
        return None

def getTaskResultSchema():
    try:
        # Add this new function to show TaskResult schema
        taskResult = TaskResult(
            task_id=str(uuid.uuid4()),
            agent="Grok",
            content="Project plan completed",
            intent=MessageIntent.CHAT,
            target_agent="Commander", 
            event=TaskEvent.COMPLETE,
            outcome=TaskOutcome.COMPLETED,  # This import is missing
            contributing_agents=["Grok", "Claude"]
        )
        
        schema = taskResult.to_json_schema()
        logger.info(f"Task Result Schema: {json.dumps(schema, indent=2)}")
        return schema
    except ValidationError as e:
        logger.error(f"Validation error creating task result schema: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error creating task result schema: {e}")
        return None


if __name__ == "__main__":
    logger.info("Generating JSON schemas for message types...")
    getChatSchema()
    getTaskSchema()
    # Uncomment after adding TaskOutcome import
    # getTaskResultSchema()
    logger.info("Schema generation complete")