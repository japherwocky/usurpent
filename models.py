"""Persistent account model for USURPENT.

Accounts back registered players. Anonymous guests are not stored here;
see the auth work (#178) for how guest sessions are handled.
"""

import bcrypt
import datetime
import peewee

from db import database


class BaseModel(peewee.Model):
    """Base for all USURPENT models; binds them to the shared database."""

    class Meta:
        database = database


def _utcnow():
    """Naive UTC timestamp used as the default for created_at."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class Account(BaseModel):
    id = peewee.AutoField()
    username = peewee.CharField(unique=True, max_length=32)
    password_hash = peewee.CharField()
    email = peewee.CharField(unique=True, null=True)
    created_at = peewee.DateTimeField(default=_utcnow)
    high_score = peewee.IntegerField(default=0)
    games_played = peewee.IntegerField(default=0)
    total_food = peewee.IntegerField(default=0)

    def set_password(self, raw_password):
        """Hash and store a plaintext password using bcrypt."""
        self.password_hash = bcrypt.hashpw(
            raw_password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, raw_password):
        """Return True if the plaintext password matches the stored hash."""
        if not self.password_hash:
            return False
        return bcrypt.checkpw(
            raw_password.encode("utf-8"), self.password_hash.encode("utf-8")
        )
