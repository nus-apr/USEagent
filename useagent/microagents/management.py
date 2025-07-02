from functools import wraps
from pydantic_ai import Agent, RunContext
from pathlib import Path
from typing import List,Callable

import useagent
from useagent.microagents.microagent import MicroAgent, load_microagent
from loguru import logger

def alias_for_microagents(name: str):
    if not name or not name.strip():
        raise ValueError("Alias cannot be None or Empty")

    def decorator(init_fn):
        @wraps(init_fn)
        def wrapper(*args, **kwargs) -> Agent:
            agent = init_fn(*args, **kwargs)
            setattr(agent, "agent_id", name)
            return agent
        return wrapper

    return decorator

def conditional_microagents_triggers(microagents: List[MicroAgent]):
    if not microagents:
        logger.warning("[Microagents] conditional_microagents_triggers received an empty microagent list.")

    def decorator(init_fn: Callable) -> Callable:
        @wraps(init_fn)
        def wrapper(*args, **kwargs) -> Agent:
            agent = init_fn(*args, **kwargs)

            if not getattr(agent, "agent_id", None) or not agent.agent_id.strip():
                raise ValueError("Agent must have a non-empty 'agent_id' field. This should exist if you used the @alias_for_microagents decorator.")
            
            relevant = [m for m in microagents if agent.agent_id in m.agents]

            @agent.instructions
            def conditional_microagent_instructions(ctx: RunContext) -> str:
                prompt = ctx.prompt.lower()
                triggered = [m for m in relevant if any(t.lower() in prompt for t in m.triggers)]
                logger.debug(f"[Microagent] {agent.agent_id} triggered {len(triggered)} of its {len(relevant)} Microagents - {[p.name for p in triggered]}")
                return "\n".join([t.instruction for t in triggered]) if triggered else ""

            #setattr(agent, "triggered_microagents", triggered) #TODO: Can we store this somewhere better?
            return agent
        return wrapper
    return decorator


def _get_project_root() -> Path:
    return Path(useagent.__file__).resolve().parents[1]

def _get_default_microagent_directory() -> Path:
    return _get_project_root() / "microagents"


def load_microagents(dir_path: str) -> List[MicroAgent]:
    results: [MicroAgent] = []
    for path in Path(dir_path).rglob("*.microagent.md"):
        if path.name.count('.') >= 2 and path.name.endswith(".microagent.md"):
            results.append(load_microagent(path))
    return results


# Example: __file__ is /some/path/a/b/c/module.py
# parents[0] = c, [1] = b, [2] = a, [3] = project root

if __name__ == "__main__":
    microagent_dir = _get_default_microagent_directory()
    microagents = load_microagents(microagent_dir)
    print("Found",len(microagents), " Microagents")