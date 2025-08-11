import logging
import json
logger = logging.getLogger(__name__)

class ttd_agent:
    def run(self, task: str, state: dict):
        try:
            params = json.loads(task) if isinstance(task, str) else (task or {})
        except Exception:
            params = {"raw": task}
        doc_id = params.get("document_id", "unknown")
        query = params.get("query", "")
        # Stubbed structured output
        result = {
            "document_id": doc_id,
            "query": query,
            "answer": f"Stubbed answer for query against {doc_id}",
        }
        return json.dumps(result)
    def get_name(self):
        return "TalktoDocument"
