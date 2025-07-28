import logging
import pandas as pd
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain.memory import ConversationBufferMemory
from langchain.chains import LLMChain
from typing import List, Dict, Any
from config.config import get_config

logger = logging.getLogger(__name__)

class PlannerAgent:
    def __init__(self, agent_knowledge_path: str = None):
        """Initialize PlannerAgent with error handling and configuration."""
        try:
            config = get_config()
            
            # Use config path if not provided
            knowledge_path = agent_knowledge_path or config.agent_knowledge_path
            
            if not knowledge_path:
                raise ValueError("Agent knowledge path cannot be empty")
            
            self.agent_knowledge = pd.read_excel(knowledge_path).to_json(orient='records')
            self.llm = ChatOpenAI(
                model=config.openai_model, 
                temperature=config.openai_temperature,
                api_key=config.openai_api_key
            )
        except Exception as e:
            logger.error(f"Failed to initialize PlannerAgent: {e}")
            raise

        # The prompt now includes a placeholder for 'history'
        prompt_template_str = """
        You are a master planner and project manager for a contract management system. Your job is to act as a helpful assistant that manages specialized agents.
        Analyze the user's latest query, taking into account the entire conversation history. Create a step-by-step plan in a JSON array format.

        **CRITICAL RULE:** If a request is incomplete, ambiguous, requires a subjective decision, or refers to documents that have not been provided, your absolute FIRST step must be to use the 'HumanAssistant'.

        **AVAILABLE AGENTS:**
        - **SupplierOnboardingCopilot**: Orchestrates the end-to-end supplier onboarding process.
        - **PlaybookBuilder**: Builds reusable playbooks from contracts for risk analysis. Requires documents as input.
        - **LegalResearchAssistant**: Answers specific, factual questions about law, clauses, and jurisdictions. IT CANNOT PROVIDE BUSINESS ADVICE.
        - **TeamsCollaborationConnector**: Sends messages, files, and summaries to Microsoft Teams channels.
        - **DefinitionsConsistencyChecker**: Scans a single document for conflicting or undefined terms.
        - **ContractRepositorySearch**: Finds contracts in the repository based on metadata, text, or other criteria.
        - **GuidedContractCreationAssistant**: Drafts new contracts like NDAs or MSAs, and requires key details like counterparty names and dates.
        - **ContractTemplateHarmonizer**: Merges multiple documents into a single, standardized template. Requires documents as input.
        - **ServiceLevelComplianceEvaluator**: Calculates SLA performance using incident data from a specific contract.
        - **ObligationRecurrenceRecommender**: Suggests schedules for recurring obligations. Requires the exact clause text.
        - **HighSpeedContractDataExtractor**: Performs rapid, bulk data extraction from one or more documents.
        - **HumanAssistant**: Asks you, the user, for clarification, missing information, a decision, or for documents/clauses.

        ---
        <Examples from your previous prompt can be kept here if desired>
        ---
        **Example: Vague Legal Change**
        User Query: "A new data privacy law just passed. Check our contracts."
        Your JSON Plan:
        [
            {{
                "agent": "HumanAssistant",
                "task": "I can check for compliance with the new law. What is the name or key provision of the new data privacy law you are concerned about?"
            }}
        ]

        **Conversation History:**
        {history}

        **User Query:** {input}
        
        Return ONLY the JSON array of the plan.
        """

        prompt = PromptTemplate(input_variables=["history", "input"], template=prompt_template_str)
        
        # We build the conversational chain directly inside the agent
        self.planner_chain = LLMChain(
            llm=self.llm,
            prompt=prompt,
            verbose=False,
            output_parser=JsonOutputParser()
        )

    def get_plan(self, user_query: str, memory: ConversationBufferMemory) -> List[Dict[str, Any]]:
        """Generate a plan with enhanced error handling and validation."""
        logger.info("Planner is creating a multi-step plan with memory...")
        try:
            if not user_query or not isinstance(user_query, str):
                raise ValueError("User query must be a non-empty string")
            
            if not memory:
                raise ValueError("Memory object cannot be None")
            
            # The chain now takes the query and the entire memory object
            response = self.planner_chain.invoke({"input": user_query, "history": memory.buffer})
            plan = response['text']
            
            # Validate plan structure
            if not isinstance(plan, list):
                logger.warning("Plan is not a list, attempting to parse as single step")
                plan = [{"agent": "HumanAssistant", "task": "I couldn't create a proper plan. Please rephrase your request."}]
            
            logger.info(f"Planner created plan: {plan}")
            return plan
            
        except Exception as e:
            logger.error(f"Failed to create or parse plan: {e}")
            return [{"agent": "HumanAssistant", "task": f"Error creating plan: {e}"}]

    def synthesize_final_response(self, initial_query: str, final_state: Dict[str, Any]) -> str:
        """Synthesize final response with error handling."""
        logger.info("Planner is synthesizing the final response...")
        
        try:
            if not initial_query or not isinstance(initial_query, str):
                raise ValueError("Initial query must be a non-empty string")
            
            if not isinstance(final_state, dict):
                raise ValueError("Final state must be a dictionary")
            
            # New prompt that explicitly asks for a list of agents
            synthesis_prompt_template = """
            You are a manager reporting on a completed task. 
            Your response must be a simple, factual summary of the actions taken.
            
            Start your summary with a clear, bulleted list of all the specialized agents that were used to handle the request.
            Then, provide a brief narrative of what was accomplished.

            Original User Query: "{query}"
            
            Execution Results (JSON State):
            {state}

            Your Summary:
            """
            
            synthesis_chain = (
                PromptTemplate.from_template(synthesis_prompt_template)
                | self.llm
                | StrOutputParser()
            )
            
            final_response = synthesis_chain.invoke({
                "query": initial_query,
                "state": str(final_state)
            })
            
            logger.info(f"Planner synthesized response: {final_response}")
            return final_response
            
        except Exception as e:
            error_msg = f"Error synthesizing response: {e}"
            logger.error(error_msg)
            return error_msg