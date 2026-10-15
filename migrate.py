import asyncio
from app.database import engine, Base

async def migrate():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Migration successful!")

if __name__ == "__main__":
    asyncio.run(migrate())