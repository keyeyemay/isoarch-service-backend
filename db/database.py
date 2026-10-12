"""Совместимые импорты; реализация разделена по модулям."""
from db.base import Base
from db.session import SessionLocal, engine, get_db
from db.raw_queries import execute_raw_update_query
