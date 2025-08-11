import json
import logging
from core.base_agent import BaseAgent
from core.state_models import ExecutionState, AgentMetadata

logger = logging.getLogger(__name__)

class ReviewDecisionAgent(BaseAgent):
    def _create_default_metadata(self) -> AgentMetadata:
        return AgentMetadata(
            name="ReviewDecisionAgent",
            description="Simulates human-in-the-loop review decisions for testing loops.",
            capabilities=["review_decision"],
            input_requirements=["question_context"],
            output_types=["review_status"],
            dependencies=[],
            version="1.0.0",
        )

    def _execute_task(self, task: str, state: ExecutionState) -> str:
        try:
            params = json.loads(task) if task else {}
        except Exception:
            params = {"raw": task}
        prev = params.get("previous_review_status") or state.metadata.get("review_status")
        # Toggle logic for simulation: if previously "Changes Required", approve; otherwise request changes once
        if prev == "Changes Required" or prev is None:
            new_status = "Approved"
        else:
            new_status = "Changes Required"
        state.metadata["review_status"] = new_status
        return json.dumps({"review_status": new_status})

