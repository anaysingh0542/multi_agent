# in agents/playbook_builder.py
import logging
logger = logging.getLogger(__name__)

class PlaybookBuilder:
    def run(self, task: str, state: dict):
        # You can add logic to update the state dictionary here if needed
        result = f"Received {task} and completed playbook building task"
        return result
    def get_name(self):
        return "PlaybookBuilder"
