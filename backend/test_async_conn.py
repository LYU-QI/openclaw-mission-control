import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from psycopg import AsyncConnection

async def test():
    conn = await AsyncConnection.connect(
        "postgresql://postgres:postgres@localhost:5432/mission_control"
    )
    print("Async connected!")
    await conn.close()

asyncio.run(test())
