from db.session import engine

def execute_raw_update_query(sql: str, params: tuple = ()) -> None:
    """Выполнение сырого SQL-запроса через курсор (без ORM) для логического удаления."""
    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        cursor.execute(sql, params)
        raw_conn.commit()
        cursor.close()
    finally:
        raw_conn.close()
