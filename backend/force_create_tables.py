import asyncio

from sqlmodel import SQLModel

import app.models  # Ensures all models are registered
from app.db.session import async_engine


async def setup():
    async with async_engine.connect() as conn:
        print("Creating ALL SQLModel tables...")
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.commit()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(setup())
