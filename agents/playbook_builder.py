# in agents/playbook_builder.py
import logging
import json
logger = logging.getLogger(__name__)

class PlaybookBuilder:
    def run(self, task: str, state: dict):
        try:
            params = json.loads(task) if isinstance(task, str) else (task or {})
        except Exception:
            params = {"raw": task}
        doc_id = params.get("document_id", "unknown")
        playbook_id = params.get("playbook_id", "default")
        # Stubbed risk findings
        risks = [
            {"clause": "Limitation of Liability", "risk_level": "medium", "issue": "Cap missing explicit exclusions"},
            {"clause": "Payment Terms", "risk_level": "low", "issue": "Net-60; verify allowances"}
        ]
        result = {
            "document_id": doc_id,
            "playbook_id": playbook_id,
            "risks": risks
        }
        return json.dumps(result)
    def get_name(self):
        return "PlaybookBuilder"
