"""Store and retrieve company context for cold email personalization."""

from pathlib import Path

CONTEXT_PATH = Path(__file__).resolve().parent.parent.parent / "company_context.txt"


def save_company_context(text: str) -> None:
    CONTEXT_PATH.write_text(text, encoding="utf-8")


def get_company_context() -> str | None:
    if not CONTEXT_PATH.exists():
        return None
    content = CONTEXT_PATH.read_text(encoding="utf-8").strip()
    return content if content else None
