"""SQLite expense CLI with persistent monthly category reports."""
import argparse
import json
import sqlite3
from datetime import date


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("amount")
    add.add_argument("category")
    add.add_argument("date")
    report = sub.add_parser("report")
    report.add_argument("month")
    args = parser.parse_args()
    try:
        if args.command == "add":
            amount = int(args.amount)
            if amount <= 0 or not args.category.strip():
                raise ValueError("invalid expense")
            parsed_date = date.fromisoformat(args.date)
            if parsed_date.isoformat() != args.date:
                raise ValueError("invalid date")
        else:
            if len(args.month) != 7:
                raise ValueError("invalid month")
            parsed_month = date.fromisoformat(args.month + "-01")
            if parsed_month.isoformat()[:7] != args.month:
                raise ValueError("invalid month")
        with sqlite3.connect(args.db) as con:
            con.execute("CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY, amount INTEGER, category TEXT, day TEXT)")
            if args.command == "add":
                cursor = con.execute(
                    "INSERT INTO expenses(amount,category,day) VALUES(?,?,?)",
                    (amount, args.category, args.date),
                )
                result = {"id": cursor.lastrowid}
            else:
                rows = con.execute(
                    "SELECT category, SUM(amount) FROM expenses "
                    "WHERE substr(day, 1, 7) = ? GROUP BY category",
                    (args.month,),
                )
                result = dict(rows)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OverflowError, sqlite3.Error):
        print(json.dumps({"error": "invalid_input"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
