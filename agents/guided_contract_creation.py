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
        """
        Execute contract creation task with guided workflow.
        
        Args:
            task: The contract creation request or task description
            state: Current execution state
            
        Returns:
            str: Contract draft or creation result
        """
        self.logger.info(f"Guided Contract Creation Assistant received request: {task}")
        
        # Generate contract draft response
        result = f"Acknowledged. I have prepared a draft for the following task: {task}."
        
        # Add to state's drafted contracts
        state.drafted_contracts.append(result)
        
        # Log successful contract drafting
        self.logger.info(f"Contract draft prepared for: {task}")
        
        return result
    def get_name(self):
        return "GuidedContractCreationAssistant"