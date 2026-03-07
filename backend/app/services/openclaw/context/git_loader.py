"""Git metadata context loader."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


async def _run_git(args: list[str]) -> str:
    def _run() -> str:
        proc = subprocess.run(  # noqa: S603
            args,
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            check=False,
        )
        output = (proc.stdout or proc.stderr).strip()
        if not output:
            return "No output."
        return output

    return await asyncio.to_thread(_run)


class GitLoader:
    """Loads context from git references."""

    async def load(self, ref: str) -> list[dict[str, str]]:
        parsed = urlparse(ref)
        query = parse_qs(parsed.query)
        target = parsed.netloc or parsed.path.lstrip("/") or "status"
        if target == "status":
            content = await _run_git(["git", "status", "--short"])
            return [{"source": "git://status", "content": content}]
        if target == "log":
            try:
                limit = max(1, min(int(query.get("limit", ["20"])[0]), 200))
            except ValueError:
                limit = 20
            content = await _run_git(["git", "log", "--oneline", f"-n{limit}"])
            return [{"source": f"git://log?limit={limit}", "content": content}]
        if target == "diff":
            base = query.get("base", ["HEAD~1"])[0]
            head = query.get("head", ["HEAD"])[0]
            content = await _run_git(["git", "diff", f"{base}..{head}"])
            return [{"source": f"git://diff?base={base}&head={head}", "content": content}]
        return [{"source": ref, "content": f"Unsupported git context target: {target}"}]
