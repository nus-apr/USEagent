from functools import wraps
from pydantic_ai import Agent

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
