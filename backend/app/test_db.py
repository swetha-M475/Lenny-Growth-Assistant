import asyncio
import sys
from app.config import settings
from app.database import engine, Base
from sqlalchemy import text

async def test():
    print("Database URL:", settings.database_url)
    print("Trying to connect to PostgreSQL...")
    try:
        async with engine.connect() as conn:
            print("Connected successfully!")
            print("Testing pgvector availability...")
            res = await conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector';"))
            row = res.fetchone()
            if row:
                print("pgvector extension is installed in this database!")
            else:
                print("pgvector extension is NOT installed in this database yet.")
    except Exception as e:
        print("Could not connect to PostgreSQL/Supabase. Error details:", e)
        print("\nNote: This is expected if the DATABASE_URL in .env has not been updated with your real credentials.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test())
