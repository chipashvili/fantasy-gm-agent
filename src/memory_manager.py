import os
from datetime import datetime

MEMORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "MEMORY.md")

class MemoryManager:
    def __init__(self):
        # Create file if it doesn't exist
        if not os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, 'w') as f:
                f.write("# Fantasy GM Agent Memory Log\n\n")

    def log_decision(self, action_id: str, approved: bool, context_msg: str = ""):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "APPROVED" if approved else "REJECTED"
        
        entry = f"- **[{timestamp}] {status}**: Action `{action_id}`. {context_msg}\n"
        
        with open(MEMORY_FILE, 'a') as f:
            f.write(entry)

    def get_memory_context(self) -> str:
        try:
            with open(MEMORY_FILE, 'r') as f:
                content = f.read()
                return content
        except Exception:
            return "No memory available."
