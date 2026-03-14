"""Feishu document context loader."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.core.config import settings
from app.services.feishu.client import FeishuClient


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


def _extract_doc_token(raw: str) -> str:
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"}:
        parts = [part for part in parsed.path.split("/") if part]
        for index, part in enumerate(parts):
            if part in {"docx", "docs"} and index + 1 < len(parts):
                return parts[index + 1]
    return parsed.netloc or parsed.path.lstrip("/")


class FeishuDocLoader:
    """Loads context from Feishu document references."""

    async def load(self, ref: str) -> list[dict[str, str]]:
        parsed = urlparse(ref)
        query = parse_qs(parsed.query)
        doc_id = _extract_doc_token(ref)
        path_hint = query.get("path", [f"docs/{doc_id}.md" if doc_id else ""])[0]
        if path_hint:
            resolved = _resolve_path(path_hint)
            if resolved is None:
                return [
                    {"source": ref, "content": f"Rejected doc path outside repository: {path_hint}"}
                ]
            if resolved.exists() and resolved.is_file():
                content = resolved.read_text(encoding="utf-8", errors="replace")
                return [{"source": str(resolved), "content": content}]

        if not doc_id:
            return [{"source": ref, "content": "No doc id or path provided."}]

        if not settings.feishu_app_id.strip() or not settings.feishu_app_secret.strip():
            return [
                {
                    "source": ref,
                    "content": "Feishu app credentials are not configured for remote doc loading.",
                }
            ]

        client = FeishuClient(settings.feishu_app_id, settings.feishu_app_secret)
        response = client.get_doc_raw_content(doc_id)
        data = response.get("data", {})
        content = data.get("content")
        if isinstance(content, str) and content.strip():
            return [{"source": f"feishu-doc:{doc_id}", "content": content}]
        return [
            {
                "source": ref,
                "content": f"Feishu document returned no readable content for {doc_id}.",
            }
        ]
