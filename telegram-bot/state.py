from dataclasses import dataclass
from typing import Any


@dataclass
class GenerateState:
    waiting_file: bool = False
    waiting_schema: bool = False
    file_name: str | None = None
    file_bytes: bytes | None = None


_states: dict[int, GenerateState] = {}


def get_state(chat_id: int) -> GenerateState:
    if chat_id not in _states:
        _states[chat_id] = GenerateState()
    return _states[chat_id]


def reset_state(chat_id: int) -> None:
    _states[chat_id] = GenerateState()


def parse_schema_payload(text: str) -> Any:
    import json

    return json.loads(text)
