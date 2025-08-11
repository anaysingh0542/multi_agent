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
from agents.mediator_agent import MediatorAgent
from agents.obligations_manager import ObligationsManager
from core.executor import PlanExecutor

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
        ] + [
            MediatorAgent(),
            ObligationsManager(),
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
                    
                    # If planner returned the new high-level plan with a root/type, use the executor
                    if isinstance(plan, dict) and plan.get("root"):
                        from core.state_models import ExecutionState
                        exec_state = ExecutionState(session_id=st.session_state.session_id, original_query=prompt)
                        executor = PlanExecutor(exec_state)
                        try:
                            exec_result = executor.execute(plan)
                            thought_process += f"\n[Executor] Ran high-level plan with result keys: {list(exec_result.keys())}\n"
                            final_response = str(exec_result.get("final_output"))
                            trace = exec_result.get("trace", [])
                            with st.expander("Show execution trace"):
                                # Group by step id
                                grouped = {}
                                for ev in trace:
                                    sid = ev.get("id", ev.get("root_id", "_meta"))
                                    grouped.setdefault(sid, []).append(ev)
                                for sid, events in grouped.items():
                                    st.markdown(f"Step: {sid}")
                                    for ev in events:
                                        st.code(str(ev))
                                    st.markdown("---")

                            # Check for HITL event and offer prompt to continue
                            hitl_events = [ev for ev in trace if ev.get("event") == "hitl"]
                            if hitl_events:
                                st.warning("Additional input is required to continue.")
                                st.write(hitl_events[0].get("message", ""))

                                # Persist plan and exec_state for re-run after user input
                                st.session_state.pending_plan = plan
                                st.session_state.pending_state = exec_state.dict()

                                def set_dotted(d, dotted_key, value):
                                    parts = dotted_key.split('.') if dotted_key else []
                                    cur = d
                                    for p in parts[:-1]:
                                        if p not in cur or not isinstance(cur[p], dict):
                                            cur[p] = {}
                                        cur = cur[p]
                                    cur[parts[-1]] = value

                                with st.form("hitl_form"):
                                    key_path = st.text_input("State key to set (dotted)", value="metadata.review_status")
                                    val = st.text_input("Value")
                                    submitted = st.form_submit_button("Apply and re-run")
                                    if submitted:
                                        # Update stored state and re-run
                                        state_dict = st.session_state.pending_state
                                        set_dotted(state_dict, key_path, val)
                                        from core.state_models import ExecutionState as ES
                                        new_state = ES(**state_dict)
                                        new_executor = PlanExecutor(new_state)
                                        new_result = new_executor.execute(st.session_state.pending_plan)
                                        new_trace = new_result.get("trace", [])
                                        with st.expander("Show execution trace (after HITL)"):
                                            grouped2 = {}
                                            for ev in new_trace:
                                                sid = ev.get("id", ev.get("root_id", "_meta"))
                                                grouped2.setdefault(sid, []).append(ev)
                                            for sid, events in grouped2.items():
                                                st.markdown(f"Step: {sid}")
                                                for ev in events:
                                                    st.code(str(ev))
                                                st.markdown("---")
                                        new_final = str(new_result.get("final_output"))
                                        st.markdown(new_final)
                                        st.session_state.messages.append({"role": "assistant", "content": new_final})
                                        st.session_state.memory.save_context({"input": prompt}, {"output": new_final})
                            else:
                                st.markdown(final_response)
                                st.session_state.messages.append({"role": "assistant", "content": final_response})
                                st.session_state.memory.save_context({"input": prompt}, {"output": final_response})
                            st.stop()
                        except Exception as e:
                            error_msg = f"Executor error: {e}"
                            logger.error(error_msg)
                            st.error(error_msg)
                            st.stop()

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
