from pathlib import Path
from alembic import command
from alembic.config import Config
from db.session import engine


def upgrade_database(bind=engine):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with bind.connect() as connection:
        sqlite = bind.dialect.name == "sqlite"
        # SQLite batch alterations rebuild tables; FK checks resume afterwards.
        if sqlite:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        try:
            with connection.begin():
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
                if sqlite and connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
                    raise RuntimeError("Migration found invalid foreign keys")
        finally:
            if sqlite:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()
