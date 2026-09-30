from alembic import context
from sqlalchemy import create_engine
from core.config import DATABASE_URL
from db.base import Base
import models

config = context.config
if context.is_offline_mode():
    raise RuntimeError("This migration inspects the existing schema; use an online connection")
else:
    connection = config.attributes.get("connection")
    engine = None
    if connection is None:
        engine = create_engine(DATABASE_URL)
        connection = engine.connect()
    try:
        context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
    finally:
        if engine is not None:
            connection.close()
            engine.dispose()
