from datetime import datetime, timedelta, timezone
from importlib import import_module
from typing import Callable

from google.adk.agents.readonly_context import ReadonlyContext


INSTRUCTION_ATTR = "INSTRUCTION"
KST = timezone(timedelta(hours=9))


def load_instruction(module_path: str) -> str:
    module = import_module(f"agents.instructions.{module_path}")
    instruction = getattr(module, INSTRUCTION_ATTR)
    return instruction.strip()


def _current_time_block() -> str:
    now = datetime.now(KST)
    return (
        "## Current datetime (authoritative — never guess the date)\n"
        f"- Now (Asia/Seoul, KST UTC+09:00): {now:%Y-%m-%d %H:%M:%S} ({now:%A})\n"
        f"- Today is {now:%Y-%m-%d}. Resolve every relative date/time "
        "('오늘', '내일', '이번 주', '다음 주', 'N일 뒤') against this value."
    )


def load_instruction_provider(
    module_path: str,
) -> Callable[[ReadonlyContext], str]:
    base = load_instruction(module_path)

    def provider(_: ReadonlyContext) -> str:
        return f"{_current_time_block()}\n\n{base}"

    return provider
