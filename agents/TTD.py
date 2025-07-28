import logging
logger = logging.getLogger(__name__)

class ttd_agent:
    def run(self, task: str, state: dict):
        # You can add logic to update the state dictionary here if needed
        result = f"Acknowledged. The Talk to Document agent has processed the task: {task}."
        return result
    def get_name(self):
        return "TalktoDocument"