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
        - **TalkToCorpus**: Search and analyze metadata, clauses, or terms across a full contract repository. Trigger when you need to find patterns, clauses, or data across multiple documents.
        - **TalkToDocument**: Ask detailed questions about a single contract — get clause summaries, key terms, and extracted insights. Trigger when working with one document and need to understand or extract clause-level information.
        - **ObligationFrequencySetupRecommender**: Converts obligation clause language into structured recurring schedules. Trigger when you need to configure obligation frequencies like monthly reporting, audits, etc., based on contract language.
        - **ServiceLevelFulfillmentAgent**: Evaluates whether SLA commitments are met, based on incident/performance data. Trigger when you need to audit or confirm SLA compliance.
        - **TemplateHarmonization**: Creates standardized contract templates by comparing multiple agreements and extracting common/variant clauses. Trigger when you need to unify diverse legacy contracts into a base template.
        - **ConvoCreate**: Guides users step-by-step through interactive contract drafting using templates. Trigger when you want to create a new contract (e.g., NDA, MSA) with structured inputs.
        - **CrossReferenceCheck**: Detects and fixes broken, incorrect, or outdated clause references and hyperlinks. Trigger when you've edited or reordered a document and need to verify all internal references are accurate.
        - **NumberingCheck**: Validates and auto-fixes clause, table, and annex numbering across the document. Trigger when a contract's structure may have misaligned or skipped numbering (e.g., after edits or merges).
        - **DefinitionsCheck**: Flags undefined, duplicate, or inconsistent use of capitalized defined terms. Trigger when you want to ensure clarity and consistency of terms before signing or review.
        - **TeamsIntegration**: Connects the platform with MS Teams for sending updates, posting clauses, triggering workflows. Trigger when you need to share insights, get approvals, or route documents via Teams.
        - **AskTim**: Legal research assistant for interpreting legal terms, comparing jurisdictions, and suggesting fallback clauses. Trigger when you have legal interpretation questions or need precedent-based guidance.
        - **PlaybookGeneratorBuilder**: Builds redlining and clause deviation playbooks from past contracts and templates. Trigger when you need structured review guidelines or want to detect risk based on historical language.
        - **SupplierOnboardingCopilot**: Automates supplier onboarding across systems, handling compliance, data validation, and tracking. Trigger when you're onboarding new suppliers or checking onboarding status, especially via Salesforce, Ariba, etc.
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
            
            # New prompt that shows thought process instead of summary
            synthesis_prompt_template = """
            You are a planner agent showing your thought process. Instead of providing a summary of results, 
            explain your thinking process and how you approached the user's request.
            
            Show the step-by-step reasoning you used to determine which agents to use and why.
            Focus on the decision-making process and logic behind the plan execution.

            Original User Query: "{query}"
            
            Execution Results (JSON State):
            {state}

            Your Thought Process:
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