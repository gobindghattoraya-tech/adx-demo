"""
Seed script: runs seed_hello_world.sql via asyncpg.
Called from cloudbuild.yaml seed step.
"""
import asyncio
import os
import pathlib

import asyncpg


SEED_SQL = (pathlib.Path(__file__).parent / "seed_hello_world.sql").read_text()


async def seed() -> None:
    conn = await asyncpg.connect(
        host="127.0.0.1",
        port=5432,
        user="postgres",
        password=os.environ["DB_PASSWORD"],
        database="adx_exchange",
    )
    try:
        for stmt in [s.strip() for s in SEED_SQL.split(";") if s.strip()]:
            print(f"  Executing: {stmt[:80]}...")
            try:
                await conn.execute(stmt)
            except asyncpg.exceptions.DuplicateObjectError:
                print("  (constraint already exists — skipping)")
    finally:
        await conn.close()

    print("✓ Seed complete")


asyncio.run(seed())
