"""OpenClaw Mission Control backend application package."""

import sys

if sys.platform == "win32":
    # psycopg async requires SelectorEventLoop, not the default ProactorEventLoop on Windows.
    import asyncio
    import selectors

    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()  # type: ignore[attr-defined]
    )
