# USEAGENT - Microagents

Microagents provide spezialised information to agents if necessary, currently triggered by a keyword match. 
We adopt the concept from [Openhands](https://github.com/All-Hands-AI/OpenHands/tree/main/microagents), with the following changes:

- As of now, we only introduce knowledge micro-agents. 
- microagents can be scoped to individual agents, or to `all` 
- As we use pydantic AI for most agentic work, the micro agents are added as `@agent.instruction`s, and in general implementation is different. 

Each microagent must be called `xxx.microagent.md` to be addressed, and have a valid header. 
The names of the suitable agents must (a) be non-empty, and (b) 

## Other Sources 

- The ssh microagent is directly adopted from OpenHands, with only a change to the header. 