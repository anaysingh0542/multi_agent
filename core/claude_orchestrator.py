"""
Claude-based orchestrator that decomposes complex queries into individual subtasks.
Each agent receives exactly one task and responds with a simple confirmation.
"""
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class ClaudeOrchestrator:
    """
    Claude orchestrator that breaks complex queries into individual agent tasks.
    """
    
    def __init__(self):
        """Initialize with agent capabilities."""
        self.agent_capabilities = {
            "ContractRepositorySearch": "Search and analyze contracts across repository",
            "HighSpeedContractDataExtractor": "Extract specific data from contracts",
            "ObligationRecurrenceRecommender": "Set up recurring obligation schedules",
            "ServiceLevelComplianceEvaluator": "Evaluate SLA compliance",
            "ContractTemplateHarmonizer": "Harmonize contract templates",
            "GuidedContractCreationAssistant": "Create new contracts interactively", 
            "DefinitionsConsistencyChecker": "Check definition consistency",
            "LegalResearchAssistant": "Provide legal research and guidance",
            "PlaybookBuilder": "Build contract review playbooks",
            "SupplierOnboardingCopilot": "Handle supplier onboarding",
            "TeamsCollaborationConnector": "Integrate with Microsoft Teams",
            "HumanAssistant": "Request clarification from user"
        }
    
    def create_execution_plan(self, user_query: str, conversation_history: str = "") -> List[Dict[str, str]]:
        """
        Decompose user query into individual agent tasks.
        Each agent gets exactly one specific task.
        """
        logger.info(f"Decomposing query: {user_query}")
        
        plan = []
        query_lower = user_query.lower()
        
        # Complex contract creation workflow
        if self._needs_contract_creation(query_lower):
            if "legal requirements" in query_lower or "compliance" in query_lower:
                plan.append({
                    "agent": "LegalResearchAssistant", 
                    "task": f"Research legal requirements for: {user_query}"
                })
            
            if "template" in query_lower or "similar contracts" in query_lower:
                plan.append({
                    "agent": "ContractRepositorySearch",
                    "task": f"Find similar contract templates for: {user_query}"
                })
            
            plan.append({
                "agent": "GuidedContractCreationAssistant",
                "task": f"Create contract based on: {user_query}"
            })
            
            plan.append({
                "agent": "DefinitionsConsistencyChecker", 
                "task": f"Validate definitions in created contract"
            })
        
        # Complex compliance audit workflow
        elif self._needs_compliance_audit(query_lower):
            plan.append({
                "agent": "ContractRepositorySearch",
                "task": f"Find all contracts for compliance review: {user_query}"
            })
            
            if "sla" in query_lower:
                plan.append({
                    "agent": "ServiceLevelComplianceEvaluator",
                    "task": f"Evaluate SLA compliance: {user_query}"
                })
            
            if "obligations" in query_lower:
                plan.append({
                    "agent": "ObligationRecurrenceRecommender", 
                    "task": f"Review obligation compliance: {user_query}"
                })
            
            plan.append({
                "agent": "PlaybookBuilder",
                "task": f"Generate compliance report for: {user_query}"
            })
        
        # Contract review workflow
        elif self._needs_contract_review(query_lower):
            plan.append({
                "agent": "HighSpeedContractDataExtractor",
                "task": f"Extract key data from contract: {user_query}"
            })
            
            plan.append({
                "agent": "DefinitionsConsistencyChecker",
                "task": f"Check definition consistency: {user_query}"
            })
        
        # Supplier management workflow  
        elif self._needs_supplier_management(query_lower):
            plan.append({
                "agent": "SupplierOnboardingCopilot",
                "task": f"Handle supplier onboarding: {user_query}"
            })
            
            if "contract" in query_lower:
                plan.append({
                    "agent": "GuidedContractCreationAssistant",
                    "task": f"Create supplier contract: {user_query}"
                })
        
        # Template standardization workflow
        elif self._needs_template_work(query_lower):
            plan.append({
                "agent": "ContractRepositorySearch", 
                "task": f"Find templates to standardize: {user_query}"
            })
            
            plan.append({
                "agent": "ContractTemplateHarmonizer",
                "task": f"Harmonize contract templates: {user_query}"
            })
        
        # Single agent tasks
        else:
            plan.append(self._route_single_task(user_query))
        
        # Default to HumanAssistant if no plan created
        if not plan:
            plan.append({
                "agent": "HumanAssistant",
                "task": f"Need clarification for: {user_query}"
            })
        
        logger.info(f"Created plan with {len(plan)} steps")
        return plan
    
    def _needs_contract_creation(self, query: str) -> bool:
        """Check if query needs complex contract creation."""
        return any(term in query for term in [
            "create contract with", "draft comprehensive", "new agreement with requirements",
            "build contract for", "generate contract with specific"
        ])
    
    def _needs_compliance_audit(self, query: str) -> bool:
        """Check if query needs compliance audit workflow."""
        return any(term in query for term in [
            "compliance audit", "review all contracts for", "audit sla performance",
            "check obligation compliance", "evaluate contract compliance"
        ])
    
    def _needs_contract_review(self, query: str) -> bool:
        """Check if query needs comprehensive contract review."""
        return any(term in query for term in [
            "review contract thoroughly", "analyze contract completely", 
            "comprehensive contract review", "full contract analysis"
        ])
    
    def _needs_supplier_management(self, query: str) -> bool:
        """Check if query needs supplier management workflow."""
        return any(term in query for term in [
            "onboard new supplier", "supplier management", "vendor onboarding with contract"
        ])
    
    def _needs_template_work(self, query: str) -> bool:
        """Check if query needs template standardization."""
        return any(term in query for term in [
            "standardize templates", "harmonize contract templates", "unify contract formats"
        ])
    
    def _route_single_task(self, query: str) -> Dict[str, str]:
        """Route simple queries to single agents."""
        query_lower = query.lower()
        
        if "search" in query_lower or "find contracts" in query_lower:
            return {"agent": "ContractRepositorySearch", "task": query}
        elif "extract data" in query_lower:
            return {"agent": "HighSpeedContractDataExtractor", "task": query}  
        elif "create" in query_lower and "contract" in query_lower:
            return {"agent": "GuidedContractCreationAssistant", "task": query}
        elif "legal research" in query_lower:
            return {"agent": "LegalResearchAssistant", "task": query}
        elif "supplier" in query_lower:
            return {"agent": "SupplierOnboardingCopilot", "task": query}
        elif "sla" in query_lower:
            return {"agent": "ServiceLevelComplianceEvaluator", "task": query}
        elif "obligation" in query_lower:
            return {"agent": "ObligationRecurrenceRecommender", "task": query}
        elif "definition" in query_lower:
            return {"agent": "DefinitionsConsistencyChecker", "task": query}
        elif "playbook" in query_lower:
            return {"agent": "PlaybookBuilder", "task": query}
        elif "teams" in query_lower:
            return {"agent": "TeamsCollaborationConnector", "task": query}
        else:
            return {"agent": "HumanAssistant", "task": query}
    
    def synthesize_response(self, initial_query: str, execution_results: Dict[str, Any]) -> str:
        """
        Generate orchestrator response showing what each agent did.
        """
        agent_results = execution_results.get('agent_results', [])
        
        response_parts = [f"**Claude Orchestrator for:** {initial_query}\n"]
        
        for i, result in enumerate(agent_results, 1):
            agent_name = result.get('agent_name', 'Unknown')
            task = result.get('task_description', 'Unknown task')
            output = result.get('result', 'No output')
            
            response_parts.append(
                f"{i}. {agent_name} received '{task}' and performed task to generate: {output}"
            )
        
        return "\n".join(response_parts)