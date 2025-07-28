import logging
from core.base_agent import BaseAgent
from core.state_models import ExecutionState, AgentMetadata

logger = logging.getLogger(__name__)

class HumanAssistant(BaseAgent):
    """
    A placeholder class that the Planner uses to signify that it needs to 
    ask the user for more information. The actual question is generated
    by the Planner itself, and the main app loop handles the conversational turn.
    """
    
    def _create_default_metadata(self) -> AgentMetadata:
        """Create default metadata for the Human Assistant agent."""
        return AgentMetadata(
            name="HumanAssistant",
            description="Facilitates human interaction by formulating questions and collecting user input",
            capabilities=[
                "user_interaction",
                "question_formulation",
                "input_collection",
                "clarification_requests"
            ],
            input_requirements=[
                "question_context"
            ],
            output_types=[
                "user_question",
                "interaction_prompt"
            ],
            dependencies=[],
            version="1.0.0"
        )
    
    def _execute_task(self, task: str, state: ExecutionState) -> str:
        """
        Execute human interaction task by formulating questions for the user.
        
        Args:
            task: The question or interaction prompt to present to the user
            state: Current execution state
            
        Returns:
            str: Formatted question for human interaction
        """
        # In a Streamlit app, this agent doesn't "do" anything except
        # allow the Planner to formulate a question.
        # The question ('task') is returned to the UI by the main app loop.
        result = f"A question was formulated for the human: '{task}'"
        
        # Log the interaction for tracking
        self.logger.info(f"Formulated question for user: {task}")
        
        return result
    def get_name(self):
        return "HumanAssistant"