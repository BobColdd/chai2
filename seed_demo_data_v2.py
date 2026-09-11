"""
chai_yako demo data — batch 2.

Requires the model changes described alongside this script:
    - Farmer.is_admin (app/models.py)
    - LoginActivity model (app/models.py)

Usage (run from the project root, next to run.py):
    DATABASE_URL="postgres://user:pass@host:port/dbname" python seed_demo_data_v2.py

What it does, in order:
    1. Patches the existing `farmers` table with an `is_admin` column
       (ALTER TABLE ... ADD COLUMN IF NOT EXISTS — safe to re-run).
    2. Creates the `login_activities` table if it doesn't exist yet.
    3. Adds ~30 synthetic August 2026 records for Jeff Chelule (continuing
       batch 1's three farms), plus 2 pruning records for variety.
    4. Creates 2 more demo farmers with their own farms and August records:
         - Grace Naliaka (small scale)
         - Kennedy Rotich (large scale)
    5. Creates 1 admin account: Wanjiru Admin (is_admin=True, no farms).
    6. Seeds a handful of LoginActivity rows (including one failed attempt)
       for every account, spread across mid-Aug to early-Sep 2026.

NOTE: August numbers for Jeff and all data for Grace/Kennedy are
synthetic — you didn't supply real figures for these, so they're
generated for demo/UI purposes only, not real farm records.

Re-running is safe: guarded by a marker Note per farmer, same pattern as
batch 1.
"""
import os
import sys
import random
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if not os.environ.get("DATABASE_URL"):
    print("ERROR: set DATABASE_URL to your Postgres external connection string first.")
    print('  e.g. DATABASE_URL="postgres://user:pass@host:port/db" python seed_demo_data_v2.py')
    sys.exit(1)

from sqlalchemy import text
from app import create_app, db
from app.models import Farmer, Farm, PluckingRecord, PruningRecord, Note, LoginActivity

random.seed(42)

MARKER_V2 = "__demo_seed_v2__"
AUG_START = datetime.date(2026, 8, 1)
AUG_END = datetime.date(2026, 8, 31)


def patch_schema():
    db.session.execute(text(
        "ALTER TABLE farmers ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE"
    ))
    db.session.commit()
    db.create_all()  # creates login_activities if missing; no-op on existing tables


def get_or_create_farmer(full_name, email, phone, scale, password, is_admin=False):
    farmer = Farmer.query.filter_by(email=email).first()
    if farmer is None:
        farmer = Farmer(full_name=full_name, email=email, phone=phone, scale=scale, is_admin=is_admin)
        farmer.set_password(password)
        db.session.add(farmer)
        db.session.commit()
        print(f"Created farmer: {full_name} ({email}){' [admin]' if is_admin else ''}")
    return farmer


def get_or_create_farm(farmer_id, farm_number, location):
    farm = Farm.query.filter_by(farmer_id=farmer_id, farm_number=farm_number).first()
    if farm is None:
        farm = Farm(farmer_id=farmer_id, farm_number=farm_number, location=location)
        db.session.add(farm)
        db.session.commit()
        print(f"  Created farm: {location} ({farm_number})")
    return farm


def already_seeded(farmer_id):
    return Note.query.filter_by(farmer_id=farmer_id, title=MARKER_V2).first() is not None


def mark_seeded(farmer_id):
    db.session.add(Note(farmer_id=farmer_id, farm_id=None, title=MARKER_V2,
                         content="Marker: demo data batch v2 seeded."))


def gen_plucking(farms, start, end, n, low, high):
    """farms: list of Farm objects to pick from. Returns list of (date, farm, kilos)."""
    span = (end - start).days
    dates = sorted(start + datetime.timedelta(days=random.randint(0, span)) for _ in range(n))
    return [(d, random.choice(farms), round(random.uniform(low, high), 1)) for d in dates]


def seed_login_activity(farmer, n=5):
    span_start = datetime.date(2026, 8, 15)
    span_end = datetime.date(2026, 9, 9)  # yesterday, relative to "today" 2026-09-10
    span = (span_end - span_start).days
    for i in range(n):
        day = span_start + datetime.timedelta(days=random.randint(0, span))
        hour, minute = random.randint(6, 20), random.randint(0, 59)
        ts = datetime.datetime.combine(day, datetime.time(hour, minute))
        success = not (i == 0)  # first entry per farmer is a failed attempt, for realism
        db.session.add(LoginActivity(
            farmer_id=farmer.id,
            login_at=ts,
            ip_address=f"41.90.{random.randint(1,254)}.{random.randint(1,254)}",
            user_agent="Mozilla/5.0 (Linux; Android 13; demo) Chrome/126.0",
            success=success,
        ))


def main():
    app = create_app()
    with app.app_context():
        patch_schema()

        # --- Jeff Chelule: August continuation on his existing 3 farms ---
        jeff = Farmer.query.filter_by(email="jeff.chelule@example.com").first()
        if jeff is None:
            print("Jeff Chelule not found — run seed_demo_data.py (batch 1) first.")
            sys.exit(1)

        if already_seeded(jeff.id):
            print("Jeff already has batch-2 data. Skipping his August records.")
        else:
            jeff_farms = Farm.query.filter_by(farmer_id=jeff.id).all()
            for d, farm, kilos in gen_plucking(jeff_farms, AUG_START, AUG_END, 30, 4, 62):
                db.session.add(PluckingRecord(farm_id=farm.id, date=d, kilos=kilos))
            # a couple of pruning records for variety
            home = next(f for f in jeff_farms if f.farm_number == "ML083")
            cherireA = next(f for f in jeff_farms if f.farm_number == "ML051")
            db.session.add(PruningRecord(farm_id=home.id, date=datetime.date(2026, 8, 10),
                                          bushes_pruned=120, prune_type="light", notes="Routine light pruning."))
            db.session.add(PruningRecord(farm_id=cherireA.id, date=datetime.date(2026, 8, 22),
                                          bushes_pruned=80, prune_type="medium", notes="Medium prune after heavy plucking."))
            mark_seeded(jeff.id)
            print("Added Jeff's August data (30 plucking + 2 pruning records).")

        # --- Grace Naliaka: new small-scale demo farmer ---
        grace = get_or_create_farmer("Grace Naliaka", "grace.naliaka@example.com",
                                      "+254711000000", "small", "ChaiYako2026!")
        if not already_seeded(grace.id):
            g_farm = get_or_create_farm(grace.id, "GN012", "Naliaka Farm")
            for d, farm, kilos in gen_plucking([g_farm], AUG_START, AUG_END, 14, 5, 35):
                db.session.add(PluckingRecord(farm_id=farm.id, date=d, kilos=kilos))
            mark_seeded(grace.id)
            print("Added Grace's August data (14 plucking records).")

        # --- Kennedy Rotich: new large-scale demo farmer ---
        kennedy = get_or_create_farmer("Kennedy Rotich", "kennedy.rotich@example.com",
                                        "+254722000000", "large", "ChaiYako2026!")
        if not already_seeded(kennedy.id):
            k_farm1 = get_or_create_farm(kennedy.id, "KR201", "Rotich Upper Farm")
            k_farm2 = get_or_create_farm(kennedy.id, "KR202", "Rotich Lower Farm")
            for d, farm, kilos in gen_plucking([k_farm1, k_farm2], AUG_START, AUG_END, 24, 20, 90):
                db.session.add(PluckingRecord(farm_id=farm.id, date=d, kilos=kilos))
            mark_seeded(kennedy.id)
            print("Added Kennedy's August data (24 plucking records across 2 farms).")

        # --- Admin account ---
        admin = get_or_create_farmer("Wanjiru Admin", "admin@chaiyako.demo",
                                      "+254733000000", "small", "ChaiYakoAdmin2026!", is_admin=True)

        db.session.commit()

        # --- Login activity for everyone ---
        for farmer in (jeff, grace, kennedy, admin):
            seed_login_activity(farmer)
        db.session.commit()
        print("Seeded login activity history for all 4 accounts.")

        print("\nDemo logins:")
        print(f"  Admin:   {admin.email} / ChaiYakoAdmin2026!")
        print(f"  Jeff:    jeff.chelule@example.com / ChaiYako2026!")
        print(f"  Grace:   grace.naliaka@example.com / ChaiYako2026!")
        print(f"  Kennedy: kennedy.rotich@example.com / ChaiYako2026!")


if __name__ == "__main__":
    main()
