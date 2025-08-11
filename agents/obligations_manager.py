import json
import logging
from core.base_agent import BaseAgent
from core.state_models import ExecutionState, AgentMetadata

logger = logging.getLogger(__name__)

class ObligationsManager(BaseAgent):
    def _create_default_metadata(self) -> AgentMetadata:
        return AgentMetadata(
            name="ObligationsManager",
            description="Finds and structures outstanding obligations for suppliers/contracts",
            capabilities=["obligation_search", "obligation_structuring"],
            input_requirements=[],
            output_types=["obligations", "recurrence_schedules"],
            dependencies=[],
            version="1.0.0",
        )

    def _execute_task(self, task: str, state: ExecutionState) -> str:
        try:
            params = json.loads(task) if task else {}
        except Exception:
            params = {"raw": task}
        supplier = params.get("supplier_name") or params.get("query", "")
        result = {
            "supplier": supplier,
            "obligations": [
                {"title": "Monthly compliance report", "due": "Monthly", "status": "Outstanding"},
                {"title": "Quarterly audit", "due": "Quarterly", "status": "Outstanding"},
            ],
        }
        # Update state in a normalized location
        state.metadata.setdefault("obligations", []).append(result)
        return json.dumps(result)

