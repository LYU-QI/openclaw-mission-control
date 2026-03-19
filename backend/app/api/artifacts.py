"""Artifacts API for serving generated files."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(prefix="/artifacts", tags=["artifacts"])

# Base directory for artifacts - store in project artifacts folder
ARTIFACTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "artifacts")
)

# Ensure artifacts directory exists
os.makedirs(ARTIFACTS_DIR, exist_ok=True)


@router.get("/{file_path:path}")
async def serve_artifact(file_path: str):
    """Serve an artifact file (e.g., HTML, images, markdown, python)."""
    # Security: prevent directory traversal
    safe_path = Path(ARTIFACTS_DIR) / file_path
    safe_path = safe_path.resolve()

    # Ensure the file is within the artifacts directory
    if not str(safe_path).startswith(str(Path(ARTIFACTS_DIR).resolve())):
        return {"error": "Invalid path"}

    if not safe_path.exists():
        return {"error": "File not found"}

    return FileResponse(safe_path)


@router.get("")
async def list_artifacts():
    """List all artifact files."""
    files = []
    for root, _, filenames in os.walk(ARTIFACTS_DIR):
        for filename in filenames:
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, ARTIFACTS_DIR)
            files.append({
                "name": filename,
                "path": rel_path,
                "url": f"/api/v1/artifacts/{rel_path}",
            })
    return {"files": files, "count": len(files)}
