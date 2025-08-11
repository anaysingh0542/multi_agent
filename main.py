import os
import logging
from dotenv import load_dotenv
from typing import Dict, Any, Optional

# We will create this logging config file again
from config.logging_config import setup_logging

from agents.planner_agent import PlannerAgent
from agents.supplier_onboarding_copilot import SupplierOnboardingCopilot
from agents.legal_research_assistant import LegalResearchAssistant
from agents.guided_contract_creation import GuidedContractCreationAssistant

setup_logging()
logger = logging.getLogger("main")

def main() -> None:
    """Main function with error handling and type safety."""
    try:
        load_dotenv()
        
        if not os.getenv("OPENAI_API_KEY"):
            logger.error("FATAL: OPENAI_API_KEY environment variable not set! Please create a .env file.")
            return

        logger.info("Initializing agents...")

        planner = PlannerAgent(agent_knowledge_path="./data/agent_routing_knowledge.xlsx")
        supplier_agent = SupplierOnboardingCopilot()
        legal_agent = LegalResearchAssistant()
        contract_agent = GuidedContractCreationAssistant()

        # Register additional agents for executor-based flows
        from agents.mediator_agent import MediatorAgent
        from agents.obligations_manager import ObligationsManager
        from core.base_agent import agent_registry
        from agents.TTD import ttd_agent
        from agents.playbook_builder import PlaybookBuilder
        from agents.service_level_compliance_evaluator import ServiceLevelComplianceEvaluator
        agent_registry.register(MediatorAgent())
        agent_registry.register(ObligationsManager())
        agent_registry.register(ttd_agent())
        agent_registry.register(PlaybookBuilder())
        agent_registry.register(ServiceLevelComplianceEvaluator())

        agent_map: Dict[str, Any] = {
            "SupplierOnboardingCopilot": supplier_agent,
            "LegalResearchAssistant": legal_agent,
            "GuidedContractCreationAssistant": contract_agent,
        }

        logger.info("Multi-Agent Co-Pilot is ready. Type 'exit' to quit.")
        
        while True:
            try:
                user_query = input("You: ")
                if user_query.lower() == 'exit':
                    logger.info("Exiting...")
                    break

                if not user_query.strip():
                    print("Co-Pilot: Please enter a valid query.")
                    continue

                # Note: This would need to be updated to match PlannerAgent interface
                # For now, creating a minimal memory object
                from langchain.memory import ConversationBufferMemory
                from langchain_core.chat_history import InMemoryChatMessageHistory
                memory = ConversationBufferMemory(chat_memory=InMemoryChatMessageHistory(), return_messages=True)
                
                plan = planner.get_plan(user_query, memory)
                if not plan:
                    print("Co-Pilot: I'm sorry, I couldn't devise a plan for that request.")
                    continue
                
                execution_state: Dict[str, Any] = {"original_query": user_query}

                # If planner returns high-level plan with root/type, use executor
                if isinstance(plan, dict) and plan.get("root"):
                    from core.state_models import ExecutionState
                    from core.executor import PlanExecutor
                    exec_state = ExecutionState(session_id="cli-session", original_query=user_query)
                    executor = PlanExecutor(exec_state)
                    try:
                        exec_result = executor.execute(plan)
                        print(f"\n[Executor] Result: {exec_result.get('final_output')}")
                        continue
                    except Exception as e:
                        logger.error(f"Executor error: {e}")
                        print(f"Executor error: {e}")
                        continue
                
                for i, step in enumerate(plan):
                    agent_name = step.get("agent")
                    task_description = step.get("task")
                    
                    print(f"\n[Step {i+1}/{len(plan)}] Executing: {agent_name} -> '{task_description}'")
                    target_agent = agent_map.get(agent_name)
                    
                    if not target_agent:
                        logger.warning(f"Skipping step: Unknown agent '{agent_name}' in the plan.")
                        continue

                    try:
                        result = target_agent.run(task=task_description, state=execution_state)
                        print(f"   ↳ Result: {result}")
                    except Exception as e:
                        logger.error(f"Error executing {agent_name}: {e}")
                        print(f"   ↳ Error: {e}")

                print("\n--------------------------------")
                final_summary = planner.synthesize_final_response(
                    initial_query=user_query,
                    final_state=execution_state
                )
                print(f"Co-Pilot: {final_summary}")
                print("--------------------------------")

            except KeyboardInterrupt:
                logger.info("Interrupted by user, exiting...")
                break
            except Exception as e:
                logger.error(f"An unexpected error occurred: {e}", exc_info=True)
                print("Co-Pilot: An error occurred. Please check the logs.")
                
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}", exc_info=True)
        print(f"Failed to start application: {e}")

if __name__ == "__main__":
    main()