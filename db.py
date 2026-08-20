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
