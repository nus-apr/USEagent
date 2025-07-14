from dataclasses import dataclass
from typing import List, Union
from pathlib import Path
from loguru import logger

import yaml
import re

@dataclass(frozen=True)
class MicroAgent:
    name: str
    version: str
    agents: List[str]
    triggers: List[str]
    instruction: str

def load_microagent(path: Union[str, Path]) -> MicroAgent:
    if not path:
        raise ValueError("Path is empty or None")
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Path does not point to a file: {path}")
    if not re.fullmatch(r'.+\.microagent\.md', path.name):
        logger.warning(f"[Microagent] Filename does not match expected pattern *.microagent.md: {path.name}")

    content = path.read_text()
    parts = content.split('---')
    if len(parts) < 3:
        raise ValueError("File does not contain a valid YAML header section")
    header = parts[1]
    instruction = '---'.join(parts[2:])
    if not instruction:
        logger.warning(f"[Microagent] File at {path.name} did not contain a instruction")


    data = yaml.safe_load(header)

    required_fields = ['name', 'version', 'agents', 'triggers']
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")

    name = data['name']
    version = data['version']
    agents = data['agents']
    triggers = data['triggers']

    if not name or not name.strip():
        raise ValueError("Name cannot be empty or null")
    if not version or not version.strip():
        raise ValueError("Version cannot be empty or null")
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError("Version must match format X.Y.Z")
    if not agents or not isinstance(agents, list):
        raise ValueError("Agents must be a non-empty list")
    if not triggers or not isinstance(triggers, list):
        raise ValueError("Triggers must be a non-empty list")

    if "all" in [p.lower().strip() for p in data['agents']]:
        agents = []

    if len(agents) > 0:
        logger.info(f"[Microagent] loaded microagent {name}, applicable to {len(agents)} agents")
    if not agents:        
        logger.info(f"[Microagent] loaded microagent {name}, applicable to ALL agents")

    return MicroAgent(name=name, version=version, agents=agents, triggers=triggers, instruction=instruction)
