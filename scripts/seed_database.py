from __future__ import annotations

import asyncio
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import get_engine, get_session_factory  # noqa: E402
from app.services.seed_service import seed_frozen_profiles  # noqa: E402


def verify_frozen_dataset() -> None:
    result = subprocess.run(
        [sys.executable, str(REPOSITORY_ROOT / "scripts" / "freeze_dataset.py"), "--check"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("dataset freeze verification failed")


async def run() -> int:
    verify_frozen_dataset()
    try:
        async with get_session_factory()() as session:
            async with session.begin():
                report = await seed_frozen_profiles(session, REPOSITORY_ROOT)
        print(
            "Seed PASS: "
            f"candidates inserted={report.candidates_inserted}, unchanged={report.candidates_unchanged}; "
            f"jobs inserted={report.jobs_inserted}, unchanged={report.jobs_unchanged}."
        )
        return 0
    finally:
        await get_engine().dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
