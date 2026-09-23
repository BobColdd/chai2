"""
Backfills realistic registration dates (Farmer.created_at) onto the demo
accounts created by seed_demo_data.py and seed_demo_data_v2.py.

Those scripts create farmers with created_at defaulting to "whenever the
script was run", which isn't realistic for a demo admin dashboard. This
script sets sensible, staggered dates instead.

Usage (run from the project root, next to run.py, after batches 1 and 2):
    DATABASE_URL="postgres://user:pass@host:port/dbname" python seed_registration_dates.py

Safe to re-run.
"""
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if not os.environ.get("DATABASE_URL"):
    print("ERROR: set DATABASE_URL to your Postgres external connection string first.")
    print('  e.g. DATABASE_URL="postgres://user:pass@host:port/db" python seed_registration_dates.py')
    sys.exit(1)

from app import create_app, db
from app.models import Farmer

# email -> realistic registration timestamp
REGISTRATION_DATES = {
    "admin@chaiyako.demo":          datetime.datetime(2026, 5, 15, 9, 10),
    "jeff.chelule@example.com":     datetime.datetime(2026, 6, 1, 7, 42),
    "grace.naliaka@example.com":    datetime.datetime(2026, 7, 20, 18, 5),
    "kennedy.rotich@example.com":   datetime.datetime(2026, 8, 5, 12, 27),
}


def main():
    app = create_app()
    with app.app_context():
        updated = 0
        for email, when in REGISTRATION_DATES.items():
            farmer = Farmer.query.filter_by(email=email).first()
            if farmer is None:
                print(f"Skipping {email}: not found (run the earlier seed scripts first).")
                continue
            farmer.created_at = when
            updated += 1
            print(f"Set {farmer.full_name} ({email}) registered {when:%d %b %Y}")
        db.session.commit()
        print(f"\nUpdated {updated} account(s).")


if __name__ == "__main__":
    main()