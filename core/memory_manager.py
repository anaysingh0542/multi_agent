"""
Persistent conversation memory management.
"""
import json
import os
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
import uuid

from .state_models import ConversationMemory, ConversationTurn, ExecutionState
from config.config import get_config


logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages persistent conversation memory storage and retrieval."""
    
    def __init__(self, storage_path: Optional[str] = None):
        """Initialize memory manager with storage path."""
        self.storage_path = Path(storage_path or self._get_default_storage_path())
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, ConversationMemory] = {}
        
    def _get_default_storage_path(self) -> str:
        """Get default storage path for memory files."""
        try:
            config = get_config()
            base_path = getattr(config, 'memory_storage_path', './data/memory')
        except Exception:
            base_path = './data/memory'
        return base_path
    
    def create_session(self, session_id: Optional[str] = None) -> ConversationMemory:
        """Create a new conversation session."""
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        memory = ConversationMemory(session_id=session_id)
        self._memory_cache[session_id] = memory
        self._save_memory(memory)
        
        logger.info(f"Created new conversation session: {session_id}")
        return memory
    
    def get_session(self, session_id: str) -> Optional[ConversationMemory]:
        """Get an existing conversation session."""
        # Check cache first
        if session_id in self._memory_cache:
            return self._memory_cache[session_id]
        
        # Try to load from disk
        memory = self._load_memory(session_id)
        if memory:
            self._memory_cache[session_id] = memory
        
        return memory
    
    def save_session(self, memory: ConversationMemory) -> None:
        """Save a conversation session."""
        self._memory_cache[memory.session_id] = memory
        self._save_memory(memory)
        logger.debug(f"Saved session: {memory.session_id}")
    
    def add_conversation_turn(self, session_id: str, user_input: str, 
                            assistant_response: str, execution_state: Optional[ExecutionState] = None) -> None:
        """Add a conversation turn to a session."""
        memory = self.get_session(session_id)
        if not memory:
            memory = self.create_session(session_id)
        
        memory.add_turn(user_input, assistant_response, execution_state)
        self.save_session(memory)
        
        logger.debug(f"Added turn to session {session_id}")
    
    def get_conversation_context(self, session_id: str, max_turns: int = 10) -> str:
        """Get conversation context for a session."""
        memory = self.get_session(session_id)
        if not memory:
            return ""
        
        return memory.get_context_string(max_turns)
    
    def list_sessions(self) -> List[str]:
        """List all available session IDs."""
        sessions = []
        
        # Add cached sessions
        sessions.extend(self._memory_cache.keys())
        
        # Add sessions from disk
        if self.storage_path.exists():
            for file_path in self.storage_path.glob("*.json"):
                session_id = file_path.stem
                if session_id not in sessions:
                    sessions.append(session_id)
        
        return sorted(sessions)
    
    def cleanup_old_sessions(self, max_age_days: int = 30) -> int:
        """Clean up old conversation sessions."""
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        cleaned_count = 0
        
        # Clean from cache
        sessions_to_remove = []
        for session_id, memory in self._memory_cache.items():
            if memory.updated_at < cutoff_date:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self._memory_cache[session_id]
            cleaned_count += 1
        
        # Clean from disk
        if self.storage_path.exists():
            for file_path in self.storage_path.glob("*.json"):
                try:
                    # Check file modification time
                    if datetime.fromtimestamp(file_path.stat().st_mtime) < cutoff_date:
                        file_path.unlink()
                        cleaned_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete old session file {file_path}: {e}")
        
        logger.info(f"Cleaned up {cleaned_count} old conversation sessions")
        return cleaned_count
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a specific conversation session."""
        success = True
        
        # Remove from cache
        if session_id in self._memory_cache:
            del self._memory_cache[session_id]
        
        # Remove from disk
        file_path = self.storage_path / f"{session_id}.json"
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Failed to delete session file {file_path}: {e}")
                success = False
        
        if success:
            logger.info(f"Deleted session: {session_id}")
        
        return success
    
    def _save_memory(self, memory: ConversationMemory) -> None:
        """Save memory to disk."""
        file_path = self.storage_path / f"{memory.session_id}.json"
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(memory.dict(), f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save memory to {file_path}: {e}")
    
    def _load_memory(self, session_id: str) -> Optional[ConversationMemory]:
        """Load memory from disk."""
        file_path = self.storage_path / f"{session_id}.json"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert datetime strings back to datetime objects
            memory = ConversationMemory.parse_obj(data)
            return memory
            
        except Exception as e:
            logger.error(f"Failed to load memory from {file_path}: {e}")
            return None
    
    def export_session(self, session_id: str, export_path: str) -> bool:
        """Export a session to a specific file path."""
        memory = self.get_session(session_id)
        if not memory:
            return False
        
        try:
            export_file = Path(export_path)
            export_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(memory.dict(), f, indent=2, default=str)
            
            logger.info(f"Exported session {session_id} to {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export session {session_id}: {e}")
            return False
    
    def import_session(self, import_path: str) -> Optional[ConversationMemory]:
        """Import a session from a file."""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            memory = ConversationMemory.parse_obj(data)
            self._memory_cache[memory.session_id] = memory
            self._save_memory(memory)
            
            logger.info(f"Imported session {memory.session_id} from {import_path}")
            return memory
            
        except Exception as e:
            logger.error(f"Failed to import session from {import_path}: {e}")
            return None


# Global memory manager instance
memory_manager = MemoryManager()


class LangChainMemoryAdapter:
    """Adapter to integrate MemoryManager with LangChain memory interface."""
    
    def __init__(self, session_id: str, memory_manager: MemoryManager = None):
        """Initialize adapter with session ID."""
        self.session_id = session_id
        self.memory_manager = memory_manager or globals()['memory_manager']
        self._ensure_session_exists()
    
    def _ensure_session_exists(self) -> None:
        """Ensure the session exists."""
        if not self.memory_manager.get_session(self.session_id):
            self.memory_manager.create_session(self.session_id)
    
    @property
    def buffer(self) -> str:
        """Get conversation buffer for LangChain compatibility."""
        return self.memory_manager.get_conversation_context(self.session_id)
    
    def save_context(self, inputs: Dict[str, str], outputs: Dict[str, str]) -> None:
        """Save conversation context."""
        user_input = inputs.get('input', str(inputs))
        assistant_response = outputs.get('output', str(outputs))
        
        self.memory_manager.add_conversation_turn(
            self.session_id, user_input, assistant_response
        )
    
    def clear(self) -> None:
        """Clear conversation memory."""
        memory = self.memory_manager.get_session(self.session_id)
        if memory:
            memory.clear()
            self.memory_manager.save_session(memory)