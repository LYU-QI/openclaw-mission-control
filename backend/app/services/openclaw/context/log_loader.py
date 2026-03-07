"""Runtime log/monitoring context loader."""

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


def _tail_text(path: Path, line_count: int) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if line_count <= 0:
        return "\n".join(lines)
    return "\n".join(lines[-line_count:])


class LogLoader:
    """Loads context from log/monitor references."""

    async def load(self, ref: str) -> list[dict[str, str]]:
        parsed = urlparse(ref)
        query = parse_qs(parsed.query)
        raw_path = query.get("path", [parsed.path.lstrip("/")])[0]
        if not raw_path:
            return [{"source": ref, "content": "No log file path provided in ref."}]
        resolved = _resolve_path(raw_path)
        if resolved is None:
            return [{"source": ref, "content": f"Rejected log path outside repository: {raw_path}"}]
        if not resolved.exists() or not resolved.is_file():
            return [{"source": ref, "content": f"Log file not found: {resolved}"}]
        try:
            tail = int(query.get("tail", ["200"])[0])
        except ValueError:
            tail = 200
        content = _tail_text(resolved, tail)
        return [{"source": str(resolved), "content": content}]
