"""
Abstract base class for all agents in the multi-agent system.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

from .state_models import ExecutionState, AgentMetadata, TaskStatus


logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all agents."""
    
    def __init__(self, metadata: Optional[AgentMetadata] = None):
        """Initialize the base agent with metadata."""
        self.metadata = metadata or self._create_default_metadata()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
    @abstractmethod
    def _create_default_metadata(self) -> AgentMetadata:
        """Create default metadata for the agent. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def _execute_task(self, task: str, state: ExecutionState) -> str:
        """Execute the core task logic. Must be implemented by subclasses."""
        pass
    
    def run(self, task: str, state: Dict[str, Any]) -> str:
        """
        Execute a task with standardized error handling and state management.
        
        Args:
            task: The task description to execute
            state: The execution state (will be converted to ExecutionState if needed)
            
        Returns:
            str: The result message from the agent
        """
        start_time = datetime.now()
        
        try:
            # Input validation
            if not task or not isinstance(task, str):
                raise ValueError("Task must be a non-empty string")
            
            if not isinstance(state, dict):
                raise ValueError("State must be a dictionary")
            
            # Convert legacy dict state to ExecutionState if needed
            if not isinstance(state, ExecutionState):
                execution_state = self._convert_legacy_state(state)
            else:
                execution_state = state
            
            self.logger.info(f"{self.metadata.name} starting task: {task}")
            
            # Validate input requirements
            self._validate_inputs(task, execution_state)
            
            # Execute the core task
            result = self._execute_task(task, execution_state)
            
            # Record successful execution
            execution_state.add_agent_result(
                agent_name=self.metadata.name,
                task_description=task,
                result=result,
                status=TaskStatus.COMPLETED
            )
            
            execution_time = datetime.now() - start_time
            self.logger.info(f"{self.metadata.name} completed task in {execution_time.total_seconds():.2f}s")
            
            return result
            
        except Exception as e:
            error_msg = f"Error in {self.metadata.name}: {e}"
            self.logger.error(error_msg, exc_info=True)
            
            # Record failed execution if we have an ExecutionState
            if 'execution_state' in locals():
                execution_state.add_agent_result(
                    agent_name=self.metadata.name,
                    task_description=task,
                    result=error_msg,
                    status=TaskStatus.FAILED,
                    error_message=str(e)
                )
            
            return error_msg
    
    def _convert_legacy_state(self, state: Dict[str, Any]) -> ExecutionState:
        """Convert legacy dictionary state to ExecutionState model."""
        # Extract or generate session ID
        session_id = state.get('session_id', str(uuid.uuid4()))
        original_query = state.get('original_query', 'Unknown query')
        
        # Create ExecutionState with existing data
        execution_state = ExecutionState(
            session_id=session_id,
            original_query=original_query
        )
        
        # Copy over any existing agent-specific data
        for field_name in execution_state.__fields__:
            if field_name in state and hasattr(execution_state, field_name):
                setattr(execution_state, field_name, state[field_name])
        
        # Update the original state dict to maintain backward compatibility
        state.update(execution_state.dict())
        
        return execution_state
    
    def _validate_inputs(self, task: str, state: ExecutionState) -> None:
        """
        Validate that required inputs are present.
        Can be overridden by subclasses for specific validation.
        """
        if self.metadata.input_requirements:
            missing_requirements = []
            
            for requirement in self.metadata.input_requirements:
                # Check if requirement exists in state metadata or as attribute
                if (requirement not in state.metadata and 
                    not hasattr(state, requirement) and
                    requirement.lower() not in task.lower()):
                    missing_requirements.append(requirement)
            
            if missing_requirements:
                raise ValueError(f"Missing required inputs: {missing_requirements}")
    
    def get_capabilities(self) -> AgentMetadata:
        """Get agent metadata and capabilities."""
        return self.metadata
    
    def get_name(self) -> str:
        """Get agent name."""
        return self.metadata.name
    
    def get_description(self) -> str:
        """Get agent description."""
        return self.metadata.description
    
    def get_version(self) -> str:
        """Get agent version."""
        return self.metadata.version
    
    def __str__(self) -> str:
        """String representation of the agent."""
        return f"{self.metadata.name} v{self.metadata.version}: {self.metadata.description}"
    
    def __repr__(self) -> str:
        """Detailed representation of the agent."""
        return (f"{self.__class__.__name__}("
                f"name='{self.metadata.name}', "
                f"version='{self.metadata.version}')")


class AgentRegistry:
    """Registry for managing agent instances and metadata."""
    
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
    
    def register(self, agent: BaseAgent) -> None:
        """Register an agent instance."""
        self._agents[agent.get_name()] = agent
        logger.info(f"Registered agent: {agent.get_name()}")
    
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Get an agent by name."""
        return self._agents.get(name)
    
    def list_agents(self) -> Dict[str, AgentMetadata]:
        """List all registered agents and their metadata."""
        return {name: agent.get_capabilities() for name, agent in self._agents.items()}
    
    def get_agents_by_capability(self, capability: str) -> Dict[str, BaseAgent]:
        """Get all agents that have a specific capability."""
        matching_agents = {}
        for name, agent in self._agents.items():
            if capability in agent.get_capabilities().capabilities:
                matching_agents[name] = agent
        return matching_agents
    
    def clear(self) -> None:
        """Clear all registered agents."""
        self._agents.clear()
        logger.info("Cleared agent registry")


# Global agent registry instance
agent_registry = AgentRegistry()