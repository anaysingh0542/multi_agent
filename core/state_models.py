"""
Pydantic models for state validation and management.
"""
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    """Enumeration for task execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    FAILED = "failed"


class AgentResult(BaseModel):
    """Model for agent execution results."""
    agent_name: str = Field(..., description="Name of the agent that executed the task")
    task_description: str = Field(..., description="Description of the task performed")
    result: str = Field(..., description="Result message from the agent")
    status: TaskStatus = Field(default=TaskStatus.COMPLETED, description="Execution status")
    execution_time: datetime = Field(default_factory=datetime.now, description="When the task was executed")
    error_message: Optional[str] = Field(None, description="Error message if task failed")
    
    class Config:
        use_enum_values = True


class ExecutionState(BaseModel):
    """Model for tracking execution state across agents."""
    session_id: str = Field(..., description="Unique session identifier")
    original_query: str = Field(..., description="The original user query")
    agent_results: List[AgentResult] = Field(default_factory=list, description="Results from each agent")
    current_step: int = Field(default=0, description="Current execution step")
    total_steps: int = Field(default=0, description="Total number of steps in the plan")
    start_time: datetime = Field(default_factory=datetime.now, description="When execution started")
    end_time: Optional[datetime] = Field(None, description="When execution completed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    # Agent-specific state storage
    onboarding_status: List[str] = Field(default_factory=list)
    legal_findings: List[str] = Field(default_factory=list)
    drafted_contracts: List[str] = Field(default_factory=list)
    playbook_entries: List[str] = Field(default_factory=list)
    teams_messages: List[str] = Field(default_factory=list)
    consistency_reports: List[str] = Field(default_factory=list)
    search_results: List[str] = Field(default_factory=list)
    harmonized_templates: List[str] = Field(default_factory=list)
    compliance_reports: List[str] = Field(default_factory=list)
    recurrence_schedules: List[str] = Field(default_factory=list)
    extracted_data: List[str] = Field(default_factory=list)
    ttd_reports: List[str] = Field(default_factory=list)
    
    @validator('current_step')
    def validate_current_step(cls, v, values):
        """Ensure current step doesn't exceed total steps."""
        total_steps = values.get('total_steps', 0)
        if v > total_steps:
            raise ValueError(f"Current step ({v}) cannot exceed total steps ({total_steps})")
        return v
    
    def add_agent_result(self, agent_name: str, task_description: str, result: str, 
                        status: TaskStatus = TaskStatus.COMPLETED, error_message: Optional[str] = None) -> None:
        """Add a new agent result to the execution state."""
        agent_result = AgentResult(
            agent_name=agent_name,
            task_description=task_description,
            result=result,
            status=status,
            error_message=error_message
        )
        self.agent_results.append(agent_result)
        
        if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            self.current_step += 1
    
    def get_agent_results_by_name(self, agent_name: str) -> List[AgentResult]:
        """Get all results from a specific agent."""
        return [result for result in self.agent_results if result.agent_name == agent_name]
    
    def get_failed_results(self) -> List[AgentResult]:
        """Get all failed agent results."""
        return [result for result in self.agent_results if result.status == TaskStatus.FAILED]
    
    def is_completed(self) -> bool:
        """Check if execution is completed."""
        return self.current_step >= self.total_steps
    
    def mark_completed(self) -> None:
        """Mark execution as completed."""
        if self.end_time is None:
            self.end_time = datetime.now()


class ConversationTurn(BaseModel):
    """Model for a single conversation turn."""
    user_input: str = Field(..., description="User's input message")
    assistant_response: str = Field(..., description="Assistant's response")
    timestamp: datetime = Field(default_factory=datetime.now, description="When the turn occurred")
    execution_state: Optional[ExecutionState] = Field(None, description="Associated execution state")
    
    class Config:
        arbitrary_types_allowed = True


class ConversationMemory(BaseModel):
    """Model for persistent conversation memory."""
    session_id: str = Field(..., description="Unique session identifier")
    turns: List[ConversationTurn] = Field(default_factory=list, description="Conversation history")
    created_at: datetime = Field(default_factory=datetime.now, description="When session was created")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update time")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Session metadata")
    
    def add_turn(self, user_input: str, assistant_response: str, 
                 execution_state: Optional[ExecutionState] = None) -> None:
        """Add a new conversation turn."""
        turn = ConversationTurn(
            user_input=user_input,
            assistant_response=assistant_response,
            execution_state=execution_state
        )
        self.turns.append(turn)
        self.updated_at = datetime.now()
    
    def get_recent_turns(self, n: int = 5) -> List[ConversationTurn]:
        """Get the N most recent conversation turns."""
        return self.turns[-n:] if len(self.turns) >= n else self.turns
    
    def get_context_string(self, max_turns: int = 10) -> str:
        """Get conversation context as a formatted string."""
        recent_turns = self.get_recent_turns(max_turns)
        context_parts = []
        
        for turn in recent_turns:
            context_parts.append(f"User: {turn.user_input}")
            context_parts.append(f"Assistant: {turn.assistant_response}")
        
        return "\n".join(context_parts)
    
    def clear(self) -> None:
        """Clear conversation history."""
        self.turns = []
        self.updated_at = datetime.now()


class AgentMetadata(BaseModel):
    """Model for agent metadata and capabilities."""
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    capabilities: List[str] = Field(default_factory=list, description="List of agent capabilities")
    input_requirements: List[str] = Field(default_factory=list, description="Required inputs")
    output_types: List[str] = Field(default_factory=list, description="Types of outputs produced")
    dependencies: List[str] = Field(default_factory=list, description="Dependencies on other agents")
    version: str = Field(default="1.0.0", description="Agent version")
    
    class Config:
        schema_extra = {
            "example": {
                "name": "SupplierOnboardingCopilot",
                "description": "Orchestrates the end-to-end supplier onboarding process",
                "capabilities": ["supplier_verification", "document_processing", "compliance_checking"],
                "input_requirements": ["supplier_name", "contact_information"],
                "output_types": ["onboarding_status", "verification_results"],
                "dependencies": ["LegalResearchAssistant"],
                "version": "1.0.0"
            }
        }