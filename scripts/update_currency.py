#!/usr/bin/env python3
"""Update the store currency in the store_settings table.

Usage:
  python scripts/update_currency.py USD
  python scripts/update_currency.py "€" --position right

This script will import the Flask app factory in `app` and update the
StoreSettings record (creates one if missing). It prints the before/after values.
"""
import argparse
import sys

def parse_args():
    p = argparse.ArgumentParser(description='Update store currency in the DB')
    p.add_argument('currency', help='Currency symbol to set (e.g. $, ¥, USD)')
    p.add_argument('--position', choices=['left', 'right'], help='Currency position (left or right)')
    p.add_argument('--dry-run', action='store_true', help='Show what would change without committing')
    return p.parse_args()


def main():
    args = parse_args()

    # Import app factory and db lazily so script can be executed from repo root
    try:
        from app import create_app, db
        from app.models import StoreSettings
    except Exception as e:
        print('Error importing the application. Make sure you run this from the project root and your venv is active.')
        print('Import error:', e)
        sys.exit(1)

    app = create_app()

    with app.app_context():
        settings = StoreSettings.query.first()
        created = False
        if not settings:
            settings = StoreSettings()
            db.session.add(settings)
            created = True

        before_currency = settings.currency
        before_position = settings.currency_position

        settings.currency = args.currency
        if args.position:
            settings.currency_position = args.position

        print('Before: currency=%s, position=%s' % (before_currency, before_position))
        print('After:  currency=%s, position=%s' % (settings.currency, settings.currency_position))

        if args.dry_run:
            print('Dry-run; no changes committed.')
            # Rollback if we created a new instance during dry-run
            db.session.rollback()
        else:
            db.session.commit()
            if created:
                print('Created new StoreSettings row and saved changes.')
            else:
                print('Updated existing StoreSettings row and saved changes.')


if __name__ == '__main__':
    main()
