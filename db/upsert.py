from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


def upsert(conn, table, values, keys):
    """Atomic on both supported databases; requires migrated unique indexes."""
    if conn.dialect.name == 'mysql':
        statement = mysql_insert(table).values(**values)
        statement = statement.on_duplicate_key_update(**{k: statement.inserted[k] for k in values if k not in keys})
    elif conn.dialect.name == 'sqlite':
        statement = sqlite_insert(table).values(**values)
        statement = statement.on_conflict_do_update(index_elements=keys, set_={k: statement.excluded[k] for k in values if k not in keys})
    else:
        raise RuntimeError('Banco não suportado; use MySQL ou SQLite.')
    conn.execute(statement)
