from collections.abc import Callable
from functools import wraps

from loguru import logger
from pydantic_ai import Agent, RunContext

from useagent.microagents.microagent import MicroAgent


def alias_for_microagents(name: str):
    """
    Simple decorator that adds the field `agent_id` to an agent, later accessible as `some_agent.agent_id`.
    This decorator allows us to introduce this field to an `init_agent` method, instead of having to extend the Agent class.
    Due to technical constraints on configurations, we need the lazy evaluation that the init_agent allows us for now.
    We intentionally introduce this new fields instead of agent.name to avoid any unkown side effects caused by naming.

    If multiple of these decorators are used, the `outermost` is the expected agent_id.
    """
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


def conditional_microagents_triggers(microagents: list[MicroAgent]):
    """
    This decorator accepts a list of Microagents that will be checked when the agent is prompted.
    If any of the keywords are triggered, the microagent instructions will be appended to the agents existing instructions.
    The decorator expects a agent_id to exist, usually you get it using the alias_for_microagents BEFORE this decorator (i.e., the alias must be the `inner` decorator).
    The matching between agents and the agent_id is case-insensitive.

    In theory, this decorator can be applied multiple times.

    DevNote:
    For most of the program, we always use the same set of microagents loaded from project files.
    This decorator accepts a list still, mostly for testing reasons (to allow cleaner unit tests, that don't need the file system).
    """
    if not microagents:
        logger.warning(
            "[Microagents] conditional_microagents_triggers received an empty microagent list."
        )

    def decorator(init_fn: Callable) -> Callable:
        @wraps(init_fn)
        def wrapper(*args, **kwargs) -> Agent:
            agent = init_fn(*args, **kwargs)

            if not getattr(agent, "agent_id", None) or not agent.agent_id.strip():
                raise ValueError(
                    "Agent must have a non-empty 'agent_id' field. This should exist if you used the @alias_for_microagents decorator."
                )

            relevant = [
                m
                for m in microagents
                if agent.agent_id.lower() in [ag.lower() for ag in m.agents]
            ]  # Case Insensitive Matching

            @agent.instructions
            def conditional_microagent_instructions(ctx: RunContext) -> str:
                prompt = str(ctx.prompt).lower()
                triggered = [
                    m for m in relevant if any(t.lower() in prompt for t in m.triggers)
                ]
                logger.trace(
                    f"[Microagent] {agent.agent_id} triggered {len(triggered)} of its {len(relevant)} Microagents - {[p.name for p in triggered]}"
                )
                return (
                    "\n".join([t.instruction for t in triggered]) if triggered else ""
                )

            return agent

        return wrapper

    return decorator
