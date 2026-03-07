"""Feishu document context loader."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _resolve_path(raw_path: str) -> Path | None:
    root = _repo_root()
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved


class FeishuDocLoader:
    """Loads context from Feishu document references."""

    async def load(self, ref: str) -> list[dict[str, str]]:
        parsed = urlparse(ref)
        query = parse_qs(parsed.query)
        doc_id = parsed.netloc or parsed.path.lstrip("/")
        path_hint = query.get("path", [f"docs/{doc_id}.md" if doc_id else ""])[0]
        if not path_hint:
            return [{"source": ref, "content": "No doc id or path provided."}]
        resolved = _resolve_path(path_hint)
        if resolved is None:
            return [{"source": ref, "content": f"Rejected doc path outside repository: {path_hint}"}]
        if not resolved.exists() or not resolved.is_file():
            return [{"source": ref, "content": f"Document file not found: {resolved}"}]
        content = resolved.read_text(encoding="utf-8", errors="replace")
        return [{"source": str(resolved), "content": content}]
