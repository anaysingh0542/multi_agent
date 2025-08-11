import json
import logging
from typing import Dict, Any
from core.base_agent import BaseAgent
from core.state_models import ExecutionState, AgentMetadata

logger = logging.getLogger(__name__)


class MediatorAgent(BaseAgent):
    def _create_default_metadata(self) -> AgentMetadata:
        return AgentMetadata(
            name="MediatorAgent",
            description="Synthesizes multi-agent outputs into comprehensive reports",
            capabilities=["report_synthesis", "aggregation", "formatting"],
            input_requirements=[],
            output_types=["report"],
            dependencies=[],
            version="1.0.0",
        )

    def _execute_task(self, task: str, state: ExecutionState) -> str:
        try:
            params = json.loads(task) if task else {}
        except Exception:
            params = {"raw": task}
        title = params.get("title", "Synthesis Report")
        sla_data = params.get("sla_data")
        obligation_data = params.get("obligation_data")
        report = {
            "title": title,
            "sections": [
                {"heading": "SLA Metrics", "content": sla_data},
                {"heading": "Outstanding Obligations", "content": obligation_data},
            ],
        }
        state.metadata.setdefault("mediator", {})["summary"] = report
        return json.dumps(report)

