"""
CodeForge Database Module
Manages Prisma client lifecycle as a global singleton.
"""

from prisma import Prisma

# Global Prisma client instance
_db: Prisma = None


def get_db() -> Prisma:
    """Get the global Prisma client instance."""
    global _db
    if _db is None:
        _db = Prisma()
    return _db


async def connect_db():
    """Connect the Prisma client to the database."""
    db = get_db()
    if not db.is_connected():
        await db.connect()
    return db


async def disconnect_db():
    """Disconnect the Prisma client."""
    global _db
    if _db and _db.is_connected():
        await _db.disconnect()
