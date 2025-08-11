import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple, Union
import re

from config.config import get_config
from core.state_models import ExecutionState, TaskStatus
from core.base_agent import agent_registry

logger = logging.getLogger(__name__)


class PlanValidationError(Exception):
    pass


class SafeEvaluator:
    """Evaluate simple boolean expressions over state and step outputs safely."""

    def __init__(self, state: ExecutionState, steps_outputs: Dict[str, Any]):
        self.state = state
        self.steps_outputs = steps_outputs

    def get_value(self, path: str) -> Any:
        # Supports state.* and steps.<id>.output[.*]
        if path.startswith("state."):
            return self._get_by_path(self.state, path[len("state."):])
        if path.startswith("steps."):
            # Generic resolver for steps.<id>[.<key>...][.output]
            remainder = path[len("steps."):]
            parts = remainder.split('.') if remainder else []
            if not parts:
                return None
            current = self.steps_outputs.get(parts[0])
            # Walk remaining parts
            for p in parts[1:]:
                if p == 'output':
                    # No-op: we already hold the output value
                    continue
                if isinstance(current, dict):
                    current = current.get(p)
                else:
                    # Cannot traverse deeper
                    return current
            # Attempt to parse JSON-like strings at the leaf
            if isinstance(current, str):
                s = current.strip()
                if (s.startswith('{') and s.endswith('}')) or (s.startswith('[') and s.endswith(']')):
                    try:
                        return json.loads(s)
                    except Exception:
                        return current
            return current
        return None

    @staticmethod
    def _get_by_path(obj: Any, dotted: str) -> Any:
        parts = dotted.split(".") if dotted else []
        cur = obj
        for p in parts:
            if cur is None:
                return None
            if isinstance(cur, dict):
                cur = cur.get(p)
            else:
                # pydantic models or objects
                cur = getattr(cur, p, None)
        return cur

    def length(self, x: Any) -> int:
        try:
            return len(x)
        except Exception:
            return 0

    def eval(self, expr: str) -> bool:
        # Very small expression language: variables are resolved via get_value when written as state.* or steps.*
        # Allow literals, and, or, not, ==, !=, >, >=, <, <=, in, parentheses. No function calls except length().
        # Provide a namespace with length() and a resolver function v(path).
        def v(path: str) -> Any:
            return self.get_value(path)

        safe_globals = {"__builtins__": {}}
        safe_locals = {
            "length": self.length,
            "v": v,
            "state": object(),  # prevent accidental access
            "steps": object(),
        }
        # Replace bare state.* / steps.* with v("path") so Python eval doesn't try attribute access on dummy objects
        tokenized = re.sub(r"\b(state\.[A-Za-z0-9_\.]+|steps\.[A-Za-z0-9_\.]+)\b",
                           lambda m: f"v(\"{m.group(1)}\")", expr)
        try:
            return bool(eval(tokenized, safe_globals, safe_locals))
        except Exception as e:
            logger.warning(f"Condition eval error for '{expr}': {e}")
            return False


class TemplateResolver:
    TEMPLATE_RE = re.compile(r"\{\{\s*([^}]+)\s*\}\}")

    def __init__(self, state: ExecutionState, steps_outputs: Dict[str, Any]):
        self.evaluator = SafeEvaluator(state, steps_outputs)

    def render(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._render_str(value)
        if isinstance(value, dict):
            return {k: self.render(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.render(v) for v in value]
        return value

    def _render_str(self, s: str) -> Any:
        # If the entire string is a single template, return the raw value (preserve type)
        m_full = re.fullmatch(r"\{\{\s*([^}]+)\s*\}\}", s)
        if m_full:
            path = m_full.group(1)
            return self.evaluator.get_value(path)
        # Otherwise, perform string substitution
        def repl(m):
            path = m.group(1)
            val = self.evaluator.get_value(path)
            try:
                return json.dumps(val) if isinstance(val, (dict, list)) else str(val)
            except Exception:
                return str(val)
        return self.TEMPLATE_RE.sub(repl, s)


class PlanExecutor:
    def __init__(self, state: ExecutionState):
        cfg = get_config()
        self.state = state
        self.max_workers = cfg.executor_max_workers
        self.max_iters = cfg.executor_max_iters
        self.global_step_cap = cfg.executor_global_step_cap
        self.steps_outputs: Dict[str, Any] = {}
        self.last_output_hash: Optional[str] = None
        self.total_steps_executed = 0
        # execution trace for UI/diagnostics
        self.trace: List[Dict[str, Any]] = []

    def execute(self, plan: Dict[str, Any]) -e Dict[str, Any]:
        root = plan.get("root") or {}
        if not root:
            raise PlanValidationError("Plan missing root")
        self._validate_ids_unique(root)
        self.trace.append({"event": "start_plan", "root_id": root.get("id")})
        result = self._run_node(root)
        self.trace.append({"event": "end_plan", "root_id": root.get("id")})
        return {"final_output": result, "steps": self.steps_outputs, "trace": self.trace}

    def _validate_ids_unique(self, node: Dict[str, Any], seen: Optional[set] = None):
        if seen is None:
            seen = set()
        node_id = node.get("id")
        if node_id:
            if node_id in seen:
                raise PlanValidationError(f"Duplicate step id: {node_id}")
            seen.add(node_id)
        for child in node.get("tasks", []) or []:
            self._validate_ids_unique(child, seen)
    def _run_node(self, node: Dict[str, Any]) -> Any:
        if self.total_steps_executed >= self.global_step_cap:
            raise RuntimeError("Global step cap exceeded")
        # Loop handling (inferred via presence of 'loop')
        if isinstance(node.get("loop"), dict):
            self.trace.append({"event": "loop_enter", "id": node.get("id")})
            res = self._run_loop(node)
            self.trace.append({"event": "loop_exit", "id": node.get("id")})
            return res
        # Branch handling (inferred via presence of 'branch' or 'branch_key')
        if isinstance(node.get("branch"), dict) or node.get("branch_key"):
            self.trace.append({"event": "branch_enter", "id": node.get("id")})
            res = self._run_branch(node)
            self.trace.append({"event": "branch_exit", "id": node.get("id")})
            return res
        ntype = node.get("type")
        if ntype == "sequential":
            return self._run_sequential(node)
        if ntype == "parallel":
            return self._run_parallel(node)
        if ntype == "agent_call":
            return self._run_agent(node)
        # Unknown node type, no-op
        return None

    def _run_sequential(self, node: Dict[str, Any]) -> Any:
        res = None
        for child in node.get("tasks", []) or []:
            res = self._run_node(child)
        return res

    def _run_parallel(self, node: Dict[str, Any]) -> Dict[str, Any]:
        tasks = node.get("tasks", []) or []
        results: Dict[str, Any] = {}
        self.trace.append({"event": "parallel_start", "id": node.get("id"), "children": [t.get("id") for t in tasks]})
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = {ex.submit(self._run_node, child): child for child in tasks}
            for fut in as_completed(futures):
                child = futures[fut]
                cid = child.get("id") or "anon"
                try:
                    results[cid] = fut.result()
                except Exception as e:
                    # Route to HumanAssistant and stop
                    self._route_to_human_and_stop(f"Parallel step '{cid}' failed: {e}")
                    raise
        # Record an aggregate output for the parallel block if it has an id
        if node.get("id"):
            self.steps_outputs[node["id"]] = results
        self.trace.append({"event": "parallel_end", "id": node.get("id")})
        return results

    def _run_agent(self, node: Dict[str, Any]) -> Any:
        self.total_steps_executed += 1
        step_id = node.get("id") or f"step_{self.total_steps_executed}"
        agent_id = node.get("agent_id")
        params = node.get("parameters", {})
        resolved_params = TemplateResolver(self.state, self.steps_outputs).render(params)

        # Map agent_id -
        agent = self._resolve_agent(agent_id)
        if agent is None:
            self._route_to_human_and_stop(f"Unknown agent_id '{agent_id}' at step '{step_id}'")
            raise RuntimeError(f"Unknown agent: {agent_id}")

        self.trace.append({"event": "agent_start", "id": step_id, "agent_id": agent_id, "params": resolved_params})
        try:
            result = agent.run(task=json.dumps(resolved_params), state=self.state.dict())
        except Exception as e:
            self._route_to_human_and_stop(f"Agent '{agent_id}' failed at step '{step_id}': {e}")
            raise

        # Store outputs
        self.steps_outputs[step_id] = result
        self.trace.append({"event": "agent_end", "id": step_id, "agent_id": agent_id})
        # Update normalized container
        self.state.metadata["last_step"] = {
            "agent": agent_id,
            "result": result,
            "parsed": None,
            "vars_set": [],
        }
        return result

    def _resolve_agent(self, agent_id: str):
        # Map high-level ids to registered names
        mapping = {
            "talk_to_document": "TalktoDocument",
            "playbook_generator": "PlaybookBuilder",
            "service_level_agent": "ServiceLevelComplianceEvaluator",
            "obligations_manager": "ObligationsManager",
            "report_synthesizer": "MediatorAgent",
            "human_assistant": "HumanAssistant",
        }
        target_name = mapping.get(agent_id)
        if not target_name:
            return None
        return agent_registry.get_agent(target_name)

    def _route_to_human_and_stop(self, message: str):
        logger.error(message)
        # Record error into state and add an agent result
        self.state.add_agent_result(
            agent_name="HumanAssistant",
            task_description=message,
            result=message,
            status=TaskStatus.FAILED,
            error_message=message,
        )
        # Add trace event for HITL routing
        self.trace.append({"event": "hitl", "message": message})

    def _run_branch(self, node: Dict[str, Any]) -> Any:
        """Execute a conditional branch.
        Supports either:
          - explicit branch: node['branch'] = {'cases': [{'when': expr, 'tasks': [...]}, ...], 'else': [...]}
          - key-based branch: node['branch_key'] with node['cases'] = {value: tasks}
        """
        step_id = node.get("id")
        branch_spec = node.get("branch")
        evaluator = SafeEvaluator(self.state, self.steps_outputs)

        selected_tasks = None

        if isinstance(branch_spec, dict) and isinstance(branch_spec.get("cases"), list):
            matches = []
            for case in branch_spec.get("cases", []):
                expr = case.get("when")
                if expr is None:
                    continue
                try:
                    if evaluator.eval(expr):
                        matches.append(case)
                except Exception:
                    continue
            if len(matches) == 1:
                selected_tasks = matches[0].get("tasks", [])
                self.trace.append({"event": "branch_select", "id": step_id, "mode": "explicit", "when": matches[0].get("when")})
            elif len(matches) == 0:
                selected_tasks = branch_spec.get("else") or []
                if not selected_tasks:
                    self._route_to_human_and_stop(f"Branch '{step_id or ''}' ambiguous: no condition matched and no else provided")
                    return None
            else:
                self._route_to_human_and_stop(f"Branch '{step_id or ''}' ambiguous: multiple conditions matched")
                return None
        else:
            # Key-based
            key = node.get("branch_key")
            cases = node.get("cases") or {}
            if not key or not isinstance(cases, dict):
                self._route_to_human_and_stop(f"Branch '{step_id or ''}' invalid specification")
                return None
            val = evaluator.get_value(key if key.startswith("state.") or key.startswith("steps.") else f"state.{key}")
            if val in cases:
                selected_tasks = cases[val]
                self.trace.append({"event": "branch_select", "id": step_id, "mode": "key", "value": val})
            elif "else" in cases:
                selected_tasks = cases["else"]
                self.trace.append({"event": "branch_select", "id": step_id, "mode": "key", "value": "else"})
            else:
                self._route_to_human_and_stop(f"Branch '{step_id or ''}' has no matching case for value '{val}' and no else")
                return None

        # Execute selected tasks sequentially by default
        res = None
        for child in selected_tasks or []:
            res = self._run_node(child)
        if step_id:
            self.steps_outputs[step_id] = res
        return res

    def _run_loop(self, node: Dict[str, Any]) -> Any:
        """Execute a loop with optional do-while semantics.
        node['loop'] = { 'condition': expr, 'do_while': bool, 'max_iters': int }
        Body is node['tasks'].
        HITL on identical outputs or ambiguous evaluations.
        """
        loop_cfg = node.get("loop", {})
        do_while = bool(loop_cfg.get("do_while", False))
        max_iters = int(loop_cfg.get("max_iters", self.max_iters))
        condition = loop_cfg.get("condition")
        step_id = node.get("id")
        evaluator = SafeEvaluator(self.state, self.steps_outputs)

        last_serialized = None
        result = None
        iters = 0

        def serialize(x: Any) -> str:
            try:
                return json.dumps(x, sort_keys=True)
            except Exception:
                return str(x)

        iter_index = 0
        while True:
            self.trace.append({"event": "loop_iter_start", "id": step_id, "iter": iter_index})
            if not do_while:
                # Pre-check condition
                if condition is not None and not evaluator.eval(condition):
                    break
            # Execute body
            result = None
            for child in node.get("tasks", []) or []:
                result = self._run_node(child)

            # identical-output short-circuit
            ser = serialize(result)
            if last_serialized is not None and ser == last_serialized:
                self.trace.append({"event": "loop_iter_identical", "id": step_id, "iter": iter_index})
                self._route_to_human_and_stop(f"Loop '{step_id or ''}' detected identical outputs across iterations; halting for HITL")
                break
            last_serialized = ser

            iters += 1
            iter_index += 1
            if iters >= max_iters:
                self.trace.append({"event": "loop_max_iters", "id": step_id, "iter": iter_index})
                break

            if do_while:
                # Post-check condition
                if condition is not None and not evaluator.eval(condition):
                    self.trace.append({"event": "loop_condition_false", "id": step_id, "iter": iter_index, "phase": "post"})
                    break
                else:
                    self.trace.append({"event": "loop_condition_true", "id": step_id, "iter": iter_index, "phase": "post"})
            else:
                # pre-check was true, record it
                self.trace.append({"event": "loop_condition_true", "id": step_id, "iter": iter_index, "phase": "pre"})

        if step_id:
            self.steps_outputs[step_id] = result
        return result

