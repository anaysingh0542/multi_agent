import streamlit as st
import os
from langchain.memory import ConversationBufferMemory
from langchain_core.chat_history import InMemoryChatMessageHistory
from core.memory_manager import LangChainMemoryAdapter
from core.base_agent import agent_registry
from typing import Dict, Any
import logging

# Import the PlannerAgent instead of the orchestrator
from agents.planner_agent import PlannerAgent
from agents.supplier_onboarding_copilot import SupplierOnboardingCopilot
from agents.human_assistant import HumanAssistant
from agents.guided_contract_creation import GuidedContractCreationAssistant
from agents.legal_research_assistant import LegalResearchAssistant
from agents.playbook_builder import PlaybookBuilder
from agents.TTD import ttd_agent
from agents.teams_collaboration_connector import TeamsCollaborationConnector
from agents.definitions_consistency_checker import DefinitionsConsistencyChecker
from agents.contract_repository_search import ContractRepositorySearch
from agents.obligation_recurrence_recommender import ObligationRecurrenceRecommender
from agents.high_speed_contract_data_extractor import HighSpeedContractDataExtractor
from agents.contract_template_harmonizer import ContractTemplateHarmonizer
from agents.service_level_compliance_evaluator import ServiceLevelComplianceEvaluator

logger = logging.getLogger(__name__)


# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Multi-Agent Co-Pilot", layout="wide")
st.title("Multi-Agent Co-Pilot 🤖")

# --- AGENT INITIALIZATION ---
@st.cache_resource
def initialize_agents() -> tuple[PlannerAgent, Dict[str, Any]]:
    """Initialize all agents with proper error handling."""
    try:
        # Use the PlannerAgent
        planner = PlannerAgent()
        
        # Create agent instances and register them
        agents = [
            SupplierOnboardingCopilot(),
            HumanAssistant(),
            GuidedContractCreationAssistant(),
            LegalResearchAssistant(),
            PlaybookBuilder(),
            ttd_agent(),
            TeamsCollaborationConnector(),
            DefinitionsConsistencyChecker(),
            ContractRepositorySearch(),
            ObligationRecurrenceRecommender(),
            HighSpeedContractDataExtractor(),
            ContractTemplateHarmonizer(),
            ServiceLevelComplianceEvaluator(),
        ]
        
        # Register agents and create map
        agent_map = {}
        for agent in agents:
            # The get_name method is called on the agent instance
            agent_name = agent.get_name() 
            agent_registry.register(agent)
            agent_map[agent_name] = agent

        return planner, agent_map
    except Exception as e:
        logger.error(f"Failed to initialize agents: {e}")
        st.error(f"Failed to initialize agents: {e}")
        st.stop()

planner, agent_map = initialize_agents()

# --- SESSION STATE MANAGEMENT ---
# Initialize session ID and persistent memory
if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = str(uuid.uuid4())

if "memory" not in st.session_state:
    # Use persistent memory adapter
    st.session_state.memory = LangChainMemoryAdapter(st.session_state.session_id)

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! How can I help you today?"}]

if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None

# --- SIDEBAR FOR CONTROLS ---
with st.sidebar:
    st.header("Controls")
    
    # Button to start a new chat session
    if st.button("New Chat"):
        # Create new session
        import uuid
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.memory = LangChainMemoryAdapter(st.session_state.session_id)
        st.session_state.messages = [{"role": "assistant", "content": "New session started. How can I help?"}]
        st.session_state.uploaded_file = None
        st.rerun()

    st.header("File Upload")
    # File uploader widget
    uploaded_file = st.file_uploader("Upload a document for the agents to use...", type=['pdf', 'docx', 'txt'])
    if uploaded_file:
        st.session_state.uploaded_file = {"name": uploaded_file.name, "type": uploaded_file.type}
        st.success(f"File '{uploaded_file.name}' uploaded successfully!")
        # For this version, we only use the file's name as context.
        # A more advanced version would parse the content: uploaded_file.getvalue()

# --- CHAT DISPLAY ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- CHAT INPUT & EXECUTION LOGIC ---
if prompt := st.chat_input("Create an MSA for..."):
    # Add user message to state and display it
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Add context about the uploaded file to the prompt if it exists
    prompt_with_context = prompt
    if st.session_state.uploaded_file:
        file_name = st.session_state.uploaded_file["name"]
        prompt_with_context = f"{prompt}\n\n(Context: I have uploaded a file named '{file_name}' that can be used by the agents.)"
        # Clear the file from state after it's been mentioned, so it's not reused accidentally
        st.session_state.uploaded_file = None

    # --- AGENT EXECUTION ---
    with st.chat_message("assistant"):
        with st.spinner("The Co-Pilot is thinking..."):
            try:
                # Prepend an instruction to the planner to assume it has access to systems
                system_instruction = (
                    "Proceed with executing the request directly. You only need to simulate route the intent to the correct agent. No other task needs to be performed by you or any other agent."
                )
                prompt_with_instruction = f"{system_instruction}\n\nUser query: {prompt_with_context}"
                
                # 1. PlannerAgent creates a plan using the augmented prompt
                plan = planner.get_plan(prompt_with_instruction, st.session_state.memory)

                if not plan:
                    st.error("I'm sorry, I couldn't devise a plan for that request.")
                    st.stop()

                if plan and plan[0].get('agent') == 'HumanAssistant':
                    # This block will now be less likely to be triggered for access requests
                    question = plan[0].get('task')
                    st.markdown(question)
                    st.session_state.messages.append({"role": "assistant", "content": question})
                    st.session_state.memory.save_context({"input": prompt}, {"output": question})
                else:
                    execution_state = {"original_query": prompt}
                    thought_process = ""
                    
                    # Execute each step in the plan
                    for i, step in enumerate(plan):
                        agent_name = step.get("agent")
                        task_description = step.get("task")
                        
                        thought_process += f"\n[Step {i+1}/{len(plan)}] Executing: {agent_name} -> '{task_description}'\n"
                        target_agent = agent_map.get(agent_name)
                        
                        if not target_agent:
                            warning_msg = f"Skipping step: Unknown agent '{agent_name}' in the plan."
                            logger.warning(warning_msg)
                            thought_process += f"    ↳ Warning: {warning_msg}\n"
                            continue

                        try:
                            # The run method is called on the agent instance
                            result = target_agent.run(task=task_description, state=execution_state)
                            thought_process += f"    ↳ Result: {result}\n"
                        except Exception as e:
                            error_msg = f"Error executing {agent_name}: {e}"
                            logger.error(error_msg)
                            thought_process += f"    ↳ Error: {error_msg}\n"
                    
                    # Filter out the warnings from the thought process for the final response
                    final_response_lines = []
                    for line in thought_process.strip().split('\n'):
                        if "↳ Warning:" not in line:
                            final_response_lines.append(line)
                    final_response = "\n".join(final_response_lines)

                    with st.expander("Show thought process"):
                        st.markdown(f"```markdown\n{thought_process.strip()}\n```")
                    st.markdown(final_response)
                    st.session_state.messages.append({"role": "assistant", "content": final_response})
                    st.session_state.memory.save_context({"input": prompt}, {"output": final_response})
                    
            except Exception as e:
                error_msg = f"An error occurred during execution: {e}"
                logger.error(error_msg, exc_info=True)
                st.error(error_msg)
