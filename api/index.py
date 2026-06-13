"""Vercel serverless entry point for FastAPI."""

import sys
from pathlib import Path

# Ensure project root is on path for `backend.*` imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.main import app  # noqa: E402
