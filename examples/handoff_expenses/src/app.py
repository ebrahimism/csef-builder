"""Offline expense command line interface."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse
import json

import domain
import storage


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise domain.InvalidInput()


def main(argv=None):
    parser = Parser()
    parser.add_argument('--db', required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    add = commands.add_parser('add')
    add.add_argument('amount')
    add.add_argument('category')
    add.add_argument('date')
    add.add_argument('--key', default=None)
    report = commands.add_parser('report')
    report.add_argument('month')
    export = commands.add_parser('export')
    export.add_argument('month')
    try:
        args = parser.parse_args(argv)
        if not args.db:
            raise domain.InvalidInput()
        if args.command == 'add':
            amount, category, day = domain.validate_expense(
                args.amount, args.category, args.date
            )
            result = {'id': storage.add_expense(
                args.db, amount, category, day, key=args.key
            )}
        elif args.command == 'report':
            month = domain.validate_month(args.month)
            result = storage.report_month(args.db, month)
        else:
            month = domain.validate_month(args.month)
            result = {'records': storage.export_month(args.db, month)}
    except domain.InvalidInput:
        print(json.dumps({'error': 'invalid_input'}))
        return 2
    except domain.Conflict:
        print(json.dumps({'error': 'conflict'}))
        return 2
    except storage.StorageError:
        print(json.dumps({'error': 'storage_error'}))
        return 1
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
