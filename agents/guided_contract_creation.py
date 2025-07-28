import logging
from core.base_agent import BaseAgent
from core.state_models import ExecutionState, AgentMetadata

logger = logging.getLogger(__name__)

class GuidedContractCreationAssistant(BaseAgent):
    """
    Assistant for creating and drafting contracts with guided workflows
    and template-based generation.
    """
    
    def _create_default_metadata(self) -> AgentMetadata:
        """Create default metadata for the Guided Contract Creation Assistant."""
        return AgentMetadata(
            name="GuidedContractCreationAssistant",
            description="Creates and drafts contracts using guided workflows and templates",
            capabilities=[
                "contract_drafting",
                "template_selection",
                "clause_generation",
                "contract_structuring",
                "legal_compliance_checking",
                "workflow_guidance"
            ],
            input_requirements=[
                "contract_type",
                "party_information",
                "contract_terms"
            ],
            output_types=[
                "contract_draft",
                "contract_template",
                "legal_clauses",
                "guidance_recommendations"
            ],
            dependencies=[
                "LegalResearchAssistant"
            ],
            version="1.0.0"
        )
    
    def _execute_task(self, task: str, state: ExecutionState) -> str:
        """Execute contract creation task with mock response."""
        result = f"Received {task} and completed contract creation task"
        return result
    def get_name(self):
        return "GuidedContractCreationAssistant"