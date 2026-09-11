"""
Seeds demo data for chai_yako into whatever DATABASE_URL points at
(e.g. Render's External Database URL for your Postgres instance).

Usage:
    Place this file in the chai_yako project root (next to run.py).

    DATABASE_URL="postgres://user:pass@host:port/dbname" python seed_demo_data.py

Creates:
    - Farmer: Jeff Chelule (demo login)
    - 3 Farms:
        Home Farm    (farm_number=ML083)
        Cherire Farm A (farm_number=ML051)
        Cherire Farm B (farm_number=ML083-C)   <- was "ML083" under cherire in the
                                                   source data, renamed to avoid
                                                   colliding with Home's ML083
    - 64 PluckingRecords + 1 weeding Note, dated June 1 - July 31 2026.

Re-running is safe: farmer/farms are looked up by unique fields before
creating, and records are only inserted if this exact demo batch hasn't
been inserted yet (guarded by a marker note).
"""
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))
if not os.environ.get("DATABASE_URL"):
    print("ERROR: set DATABASE_URL to your Postgres external connection string first.")
    print('  e.g. DATABASE_URL="postgres://user:pass@host:port/db" python seed_demo_data.py')
    sys.exit(1)

from app import create_app, db
from app.models import Farmer, Farm, PluckingRecord, Note

DEMO_EMAIL = "jeff.chelule@example.com"
DEMO_PASSWORD = "ChaiYako2026!"
MARKER_TITLE = "__demo_seed_v1__"

# (id, activity, farm_label, code, kilos, notes)
RECORDS = [
    (1, "plucking", "home", "ML083", 13.9, "Plucked by evaline"),
    (2, "plucking", "cherire", "ML083", 8.5, None),
    (3, "plucking", "cherire", "ML051", 26.7, None),
    (4, "plucking", "home", "ML083", 62, None),
    (5, "plucking", "cherire", "ML083", 28.8, None),
    (6, "plucking", "cherire", "ML051", 28.1, None),
    (7, "plucking", "home", "ML083", 13.7, None),
    (8, "plucking", "home", "ML083", 28.7, None),
    (9, "plucking", "home", "ML083", 61.6, None),
    (10, "plucking", "cherire", "ML051", 25, None),
    (11, "plucking", "home", "ML083", 16.3, None),
    (12, "plucking", "cherire", "ML083", 22.4, None),
    (13, "plucking", "cherire", "ML051", 46.4, None),
    (14, "plucking", "cherire", "ML051", 37.5, None),
    (15, "plucking", "cherire", "ML083", 38.2, None),
    (16, "plucking", "home", "ML083", 22.6, None),
    (17, "plucking", "home", "ML083", 5.1, None),
    (19, "plucking", "cherire", "ML083", 5.4, None),
    (20, "plucking", "cherire", "ML051", 10.4, None),
    (21, "plucking", "cherire", "ML051", 12, None),
    (22, "plucking", "cherire", "ML083", 20.6, None),
    (23, "plucking", "cherire", "ML083", 25.6, None),
    (24, "plucking", "cherire", "ML051", 43.1, None),
    (25, "plucking", "cherire", "ML083", 34.6, None),
    (26, "weeding", "cherire", "ML051", None,
     "There has been recent weeding done at cherire,31-8.\nThere is ongoing weeding of kennedy's Tea."),
    (27, "plucking", "home", "ML083", 11.6, None),
    (28, "plucking", "cherire", "ML083", 15.9, None),
    (29, "plucking", "cherire", "ML051", 5.2, None),
    (30, "plucking", "home", "ML083", 42.8, None),
    (31, "plucking", "home", "ML083", 55.9, None),
    (32, "plucking", "cherire", "ML051", 30.2, None),
    (33, "plucking", "home", "ML083", 52.9, None),
    (34, "plucking", "cherire", "ML083", 13.1, None),
    (35, "plucking", "home", "ML083", 3.4, None),
    (36, "plucking", "home", "ML083", 17.1, None),
    (37, "plucking", "home", "ML083", 12.9, None),
    (38, "plucking", "home", "ML083", 13.2, None),
    (39, "plucking", "cherire", "ML051", 15.6, None),
    (40, "plucking", "cherire", "ML083", 11.9, None),
    (41, "plucking", "cherire", "ML051", 12.2, None),
    (42, "plucking", "cherire", "ML083", 11.8, None),
    (43, "plucking", "cherire", "ML051", 5.4, None),
    (44, "plucking", "cherire", "ML051", 11.1, None),
    (45, "plucking", "cherire", "ML051", 29.2, None),
    (46, "plucking", "cherire", "ML051", 11.2, None),
    (47, "plucking", "cherire", "ML051", 6.9, None),
    (48, "plucking", "cherire", "ML083", 29.6, None),
    (49, "plucking", "cherire", "ML051", 39.7, None),
    (50, "plucking", "cherire", "ML083", 11, None),
    (51, "plucking", "cherire", "ML083", 33.2, None),
    (52, "plucking", "cherire", "ML051", 11, None),
    (53, "plucking", "cherire", "ML083", 5.6, None),
    (54, "plucking", "cherire", "ML083", 12, None),
    (55, "plucking", "cherire", "ML083", 8.9, None),
    (56, "plucking", "cherire", "ML083", 7.3, None),
    (57, "plucking", "cherire", "ML083", 17.6, None),
    (58, "plucking", "cherire", "ML083", 7.6, None),
    (59, "plucking", "cherire", "ML083", 9.2, None),
    (60, "plucking", "cherire", "ML051", 8.9, None),
    (61, "plucking", "cherire", "ML083", 9.1, None),
    (62, "plucking", "cherire", "ML083", 6, None),
    (63, "plucking", "cherire", "ML083", 14.6, None),
    (64, "plucking", "cherire", "ML051", 5.8, None),
    (65, "plucking", "cherire", "ML083", 6.5, None),
    (66, "plucking", "cherire", "ML051", 31.5, None),
]

# code -> (location label, farm_number to store)
FARM_CODE_MAP = {
    ("home", "ML083"): ("Home Farm", "ML083"),
    ("cherire", "ML051"): ("Cherire Farm A", "ML051"),
    ("cherire", "ML083"): ("Cherire Farm B", "ML083-C"),
}

START_DATE = datetime.date(2026, 6, 1)
END_DATE = datetime.date(2026, 7, 31)


def record_dates(n):
    span = (END_DATE - START_DATE).days
    return [START_DATE + datetime.timedelta(days=round(i * span / (n - 1))) for i in range(n)]


def main():
    app = create_app()
    with app.app_context():
        farmer = Farmer.query.filter_by(email=DEMO_EMAIL).first()
        if farmer is None:
            farmer = Farmer(
                full_name="Jeff Chelule",
                email=DEMO_EMAIL,
                phone="+254700000000",
                scale="small",
            )
            farmer.set_password(DEMO_PASSWORD)
            db.session.add(farmer)
            db.session.commit()
            print(f"Created farmer: {farmer.full_name} ({farmer.email})")
        else:
            print(f"Farmer already exists: {farmer.full_name} ({farmer.email})")

        already_seeded = Note.query.filter_by(farmer_id=farmer.id, title=MARKER_TITLE).first()
        if already_seeded:
            print("Demo batch already seeded for this farmer. Nothing to do.")
            return

        farms = {}
        for (location, farm_number) in set(FARM_CODE_MAP.values()):
            farm = Farm.query.filter_by(farmer_id=farmer.id, farm_number=farm_number).first()
            if farm is None:
                farm = Farm(farmer_id=farmer.id, farm_number=farm_number, location=location)
                db.session.add(farm)
                db.session.commit()
                print(f"Created farm: {location} ({farm_number})")
            farms[farm_number] = farm

        dates = record_dates(len(RECORDS))
        plucking_count = 0
        note_count = 0

        for (rid, activity, farm_label, code, kilos, notes), rec_date in zip(RECORDS, dates):
            location, farm_number = FARM_CODE_MAP[(farm_label, code)]
            farm = farms[farm_number]

            if activity == "plucking":
                db.session.add(PluckingRecord(
                    farm_id=farm.id,
                    date=rec_date,
                    kilos=kilos,
                    notes=notes,
                ))
                plucking_count += 1
            elif activity == "weeding":
                db.session.add(Note(
                    farmer_id=farmer.id,
                    farm_id=farm.id,
                    title=f"Weeding - {rec_date.isoformat()}",
                    content=notes,
                    created_at=datetime.datetime.combine(rec_date, datetime.time(9, 0)),
                ))
                note_count += 1

        # Marker note so re-running the script doesn't duplicate data
        db.session.add(Note(
            farmer_id=farmer.id,
            farm_id=None,
            title=MARKER_TITLE,
            content="Marker: demo data batch v1 seeded.",
        ))

        db.session.commit()
        print(f"Inserted {plucking_count} plucking records and {note_count} weeding note(s).")
        print(f"Login as: {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
