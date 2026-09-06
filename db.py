"""Database connection and schema bootstrap for USURPENT.

Uses Peewee over SQLite. Call init_db() once at process start, before any
model access, to bind the database file and create tables.
"""

import peewee

import config


database = peewee.SqliteDatabase(config.DATABASE_PATH)


def init_db():
    """Connect and create tables if they do not yet exist.

    Safe to call more than once (e.g. in tests): it reuses an already
    open connection and skips tables that are already present.
    """
    from models import Account  # local import avoids an import cycle

    database.connect(reuse_if_open=True)
    database.create_tables([Account], safe=True)
    _migrate()


def _migrate():
    """Add columns that postdate a table's creation.

    create_tables only builds what is missing; it never touches a table that
    exists, so a column added after first deploy would silently not exist and
    every write to it would fail. SQLite makes the check cheap: ask the table
    what columns it has, ALTER when one is absent. Ordered list of
    (table, column, ddl) so future columns append here.
    """
    migrations = [
        ("account", "banked_score",
         "ALTER TABLE account ADD COLUMN banked_score INTEGER DEFAULT 0"),
    ]
    for table, column, ddl in migrations:
        cursor = database.execute_sql(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        if column not in existing:
            database.execute_sql(ddl)
