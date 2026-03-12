"""Feishu group context loader."""

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


class FeishuGroupLoader:
    """Loads context from Feishu group references."""

    async def load(self, ref: str) -> list[dict[str, str]]:
        parsed = urlparse(ref)
        query = parse_qs(parsed.query)
        group_id = query.get("chat_id", [""])[0] or parsed.path.strip("/") or parsed.netloc
        path_hint = query.get("path", [f"docs/feishu/groups/{group_id}.md" if group_id else ""])[0]
        if path_hint:
            resolved = _resolve_path(path_hint)
            if resolved and resolved.exists() and resolved.is_file():
                content = resolved.read_text(encoding="utf-8", errors="replace")
                return [{"source": str(resolved), "content": content}]

        if group_id and settings.feishu_app_id.strip() and settings.feishu_app_secret.strip():
            client = FeishuClient(settings.feishu_app_id, settings.feishu_app_secret)
            response = client.list_chat_messages(group_id)
            items = response.get("data", {}).get("items", [])
            lines: list[str] = []
            for item in items:
                sender = item.get("sender", {}).get("sender_id", {}).get("open_id") or "unknown-sender"
                body = item.get("body", {})
                content = body.get("content", "")
                if not isinstance(content, str):
                    continue
                lines.append(f"{sender}: {content}")
            if lines:
                return [{"source": f"feishu-group:{group_id}", "content": "\n".join(lines)}]

        group_label = group_id or "unknown-group"
        return [
            {
                "source": ref,
                "content": (
                    f"Feishu group context reference resolved for '{group_label}', "
                    "but no local transcript file was found."
                ),
            }
        ]
