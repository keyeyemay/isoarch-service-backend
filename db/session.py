from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from core.config import DATABASE_URL

engine = create_engine(DATABASE_URL, echo=False)

if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    with SessionLocal() as db:
        yield db
