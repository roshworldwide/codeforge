from prisma import Prisma

_db: Prisma = None


def get_db() -> Prisma:
    global _db
    if _db is None:
        _db = Prisma()
    return _db


async def connect_db():
    db = get_db()
    if not db.is_connected():
        await db.connect()
    return db


async def disconnect_db():
    global _db
    if _db and _db.is_connected():
        await _db.disconnect()
