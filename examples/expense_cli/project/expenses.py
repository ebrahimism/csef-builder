"""Pilot expense CLI. The monthly report intentionally contains a real defect."""
import argparse
import json
import sqlite3
from datetime import date


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("amount", type=int)
    add.add_argument("category")
    add.add_argument("date")
    report = sub.add_parser("report")
    report.add_argument("month")
    args = parser.parse_args()
    try:
        if args.command == "add":
            if args.amount <= 0 or not args.category.strip():
                raise ValueError("invalid expense")
            date.fromisoformat(args.date)
        elif len(args.month) != 7:
            raise ValueError("invalid month")
        else:
            date.fromisoformat(args.month + "-01")
        with sqlite3.connect(args.db) as con:
            con.execute("CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY, amount INTEGER, category TEXT, day TEXT)")
            if args.command == "add":
                cursor = con.execute("INSERT INTO expenses(amount,category,day) VALUES(?,?,?)", (args.amount, args.category, args.date))
                result = {"id": cursor.lastrowid}
            else:
                # Defect: ignores requested month and collapses all categories.
                total = con.execute("SELECT COALESCE(SUM(amount),0) FROM expenses").fetchone()[0]
                result = {"total": total}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, sqlite3.Error):
        print(json.dumps({"error": "invalid_input"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
