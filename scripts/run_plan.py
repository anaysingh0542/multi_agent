import json
import sys
import os

# Ensure repo root is on sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core.executor import PlanExecutor
from core.state_models import ExecutionState
from core.base_agent import agent_registry

# Register required agents for mapping
from agents.TTD import ttd_agent
from agents.playbook_builder import PlaybookBuilder
from agents.service_level_compliance_evaluator import ServiceLevelComplianceEvaluator
from agents.mediator_agent import MediatorAgent
from agents.obligations_manager import ObligationsManager
from agents.human_assistant import HumanAssistant

# idempotent registrations
agent_registry.register(ttd_agent())
agent_registry.register(PlaybookBuilder())
agent_registry.register(ServiceLevelComplianceEvaluator())
agent_registry.register(MediatorAgent())
agent_registry.register(ObligationsManager())
agent_registry.register(HumanAssistant())


def run_plan(plan_path: str):
    with open(plan_path, 'r') as f:
        plan = json.load(f)
    state = ExecutionState(session_id="manual-test", original_query=f"manual:{plan.get('name','plan')}")
    executor = PlanExecutor(state)
    result = executor.execute(plan)
    print("=== Plan Executed ===")
    print("Final Output:")
    print(result.get("final_output"))
    print("\nStep Outputs:")
    for k, v in result.get("steps", {}).items():
        print(f"- {k}: {str(v)[:200]}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/run_plan.py <path_to_plan.json>")
        sys.exit(1)
    run_plan(sys.argv[1])

