"""
Gateway Database
asyncpg connection pool + raw SQL queries for the users table.
"""
import asyncpg
from app.Config import config


pool: asyncpg.Pool = None


async def init_db():
    """Create connection pool and ensure tables exist."""
    global pool
    pool = await asyncpg.create_pool(
        config.DATABASE_URL,
        min_size=config.DB_POOL_MIN,
        max_size=config.DB_POOL_MAX,
    )

    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                api_key VARCHAR(255) UNIQUE,
                plan VARCHAR(50) DEFAULT 'free',
                quota_minutes INTEGER DEFAULT 60,
                used_minutes FLOAT DEFAULT 0,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)


async def close_db():
    """Close the connection pool."""
    global pool
    if pool:
        await pool.close()


# =============================================================================
# User queries
# =============================================================================

async def create_user(email: str, password_hash: str, api_key: str) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (email, password_hash, api_key)
            VALUES ($1, $2, $3)
            RETURNING id, email, api_key, plan, quota_minutes, used_minutes, created_at
            """,
            email, password_hash, api_key,
        )
        return dict(row)


async def get_user_by_email(email: str) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE email = $1 AND is_active = true",
            email,
        )
        return dict(row) if row else None


async def get_user_by_id(user_id: int) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1 AND is_active = true",
            user_id,
        )
        return dict(row) if row else None


async def get_user_by_api_key(api_key: str) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE api_key = $1 AND is_active = true",
            api_key,
        )
        return dict(row) if row else None


async def update_used_minutes(user_id: int, minutes: float):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET used_minutes = used_minutes + $1, updated_at = NOW()
            WHERE id = $2
            """,
            minutes, user_id,
        )


async def check_quota(user_id: int) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT quota_minutes, used_minutes FROM users WHERE id = $1",
            user_id,
        )
        if not row:
            return {"has_quota": False, "remaining": 0}
        remaining = row["quota_minutes"] - row["used_minutes"]
        return {
            "has_quota": remaining > 0,
            "remaining": max(0, remaining),
            "quota": row["quota_minutes"],
            "used": row["used_minutes"],
        }