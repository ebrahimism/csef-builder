"""SQLite persistence with additive, legacy-preserving retry support."""
import sqlite3
from pathlib import Path

import domain


class StorageError(Exception):
    pass


def _ensure_expenses(connection):
    # Never replace, rewrite, or renumber existing expense rows.
    connection.execute(
        'CREATE TABLE IF NOT EXISTS expenses ('
        'id INTEGER PRIMARY KEY, amount INTEGER NOT NULL, '
        'category TEXT NOT NULL, day TEXT NOT NULL)'
    )


def _ensure_retry_keys(connection):
    # A separate table leaves the legacy expenses schema and its rows intact.
    connection.execute(
        'CREATE TABLE IF NOT EXISTS expense_retry_keys ('
        'retry_key TEXT PRIMARY KEY NOT NULL COLLATE BINARY, '
        'expense_id INTEGER NOT NULL REFERENCES expenses(id), '
        'amount INTEGER NOT NULL, category TEXT NOT NULL, day TEXT NOT NULL)'
    )


def add_expense(path, amount, category, day, key=None):
    connection = None
    try:
        connection = sqlite3.connect(path)
        with connection:
            # Serialize key lookup and insertion across competing writers.
            # Schema additions and both inserts commit or roll back together.
            connection.execute('BEGIN IMMEDIATE')
            _ensure_expenses(connection)
            _ensure_retry_keys(connection)
            if key is not None:
                previous = connection.execute(
                    'SELECT expense_id, amount, category, day '
                    'FROM expense_retry_keys WHERE retry_key = ?',
                    (key,),
                ).fetchone()
                if previous is not None:
                    if previous[1:] != (amount, category, day):
                        raise domain.Conflict()
                    return previous[0]
            cursor = connection.execute(
                'INSERT INTO expenses (amount, category, day) VALUES (?, ?, ?)',
                (amount, category, day),
            )
            identifier = cursor.lastrowid
            if key is not None:
                connection.execute(
                    'INSERT INTO expense_retry_keys '
                    '(retry_key, expense_id, amount, category, day) '
                    'VALUES (?, ?, ?, ?, ?)',
                    (key, identifier, amount, category, day),
                )
        return identifier
    except (sqlite3.Error, OSError, ValueError, UnicodeError) as exc:
        raise StorageError() from exc
    finally:
        if connection is not None:
            connection.close()


def report_month(path, month):
    connection = None
    try:
        connection = sqlite3.connect(path)
        with connection:
            _ensure_expenses(connection)
        rows = connection.execute(
            'SELECT category, amount FROM expenses '
            'WHERE substr(day, 1, 7) = ? ORDER BY id',
            (month,),
        )
        totals = {}
        # Python integers avoid SQLite SUM overflow for large monthly totals.
        for category, amount in rows:
            totals[category] = totals.get(category, 0) + amount
        return totals
    except (sqlite3.Error, OSError, ValueError, UnicodeError) as exc:
        raise StorageError() from exc
    finally:
        if connection is not None:
            connection.close()


def export_month(path, month):
    """Read one month without creating a database or modifying its schema."""
    connection = None
    try:
        database = Path(path).resolve()
        connection = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
        connection.execute('BEGIN')
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            ('expenses',),
        ).fetchone()
        if exists is None:
            return []
        rows = connection.execute(
            'SELECT id, amount, category, day FROM expenses '
            'WHERE substr(day, 1, 7) = ? ORDER BY id',
            (month,),
        )
        return [
            {'id': identifier, 'amount': amount, 'category': category, 'date': day}
            for identifier, amount, category, day in rows
        ]
    except (sqlite3.Error, OSError, ValueError, UnicodeError) as exc:
        raise StorageError() from exc
    finally:
        if connection is not None:
            connection.close()
