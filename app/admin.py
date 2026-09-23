from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user

from app import db
from app.models import Farmer, Farm, PluckingRecord, PruningRecord, Tool, Note, LoginActivity

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view_func):
    """Guards admin routes. Deliberately does NOT use flask_login's
    @login_required, since that redirects to login_manager.login_view
    (the farmer login). Unauthenticated or non-admin visitors are sent
    to admin.login instead, which is never linked from anywhere public."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, "is_admin", False):
            flash("Please log in with an admin account.", "error")
            return redirect(url_for("admin.login"))
        return view_func(*args, **kwargs)
    return wrapped


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated and getattr(current_user, "is_admin", False):
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        farmer = Farmer.query.filter_by(email=email).first()

        password_ok = bool(farmer and farmer.check_password(password))
        success = bool(password_ok and farmer.is_admin)

        if farmer:
            db.session.add(LoginActivity(
                farmer_id=farmer.id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent", "")[:255],
                success=success,
            ))
            db.session.commit()

        if success:
            login_user(farmer)
            return redirect(url_for("admin.dashboard"))

        if password_ok and not farmer.is_admin:
            flash("That account doesn't have admin access.", "error")
        else:
            flash("Invalid email or password.", "error")

    return render_template("admin/login.html")


@admin_bp.route("/logout")
@admin_required
def logout():
    logout_user()
    flash("Admin logged out.", "info")
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@admin_required
def dashboard():
    farmers = (Farmer.query.filter_by(is_admin=False)
               .order_by(Farmer.created_at.desc()).all())

    stats = []
    for f in farmers:
        total_kilos = sum(farm.total_kilos for farm in f.farms)
        last_login = (LoginActivity.query
                      .filter_by(farmer_id=f.id, success=True)
                      .order_by(LoginActivity.login_at.desc())
                      .first())
        stats.append({
            "farmer": f,
            "farm_count": len(f.farms),
            "total_kilos": total_kilos,
            "last_login": last_login.login_at if last_login else None,
        })

    recent_activity = (LoginActivity.query
                        .order_by(LoginActivity.login_at.desc())
                        .limit(10).all())

    week_ago = datetime.utcnow() - timedelta(days=7)

    totals = {
        "farmer_count": len(farmers),
        "farm_count": sum(s["farm_count"] for s in stats),
        "kilos_total": sum(s["total_kilos"] for s in stats),
        "failed_logins_recent": LoginActivity.query.filter_by(success=False).count(),
        "new_this_week": sum(1 for f in farmers if f.created_at and f.created_at >= week_ago),
        "small_scale": sum(1 for f in farmers if f.scale == "small"),
        "large_scale": sum(1 for f in farmers if f.scale == "large"),
        "terms_accepted": sum(1 for f in farmers if f.terms_accepted),
    }

    return render_template("admin/dashboard.html", stats=stats,
                            recent_activity=recent_activity, totals=totals)


@admin_bp.route("/farmers/<int:farmer_id>")
@admin_required
def farmer_detail(farmer_id):
    farmer = Farmer.query.get_or_404(farmer_id)
    farms = Farm.query.filter_by(farmer_id=farmer.id).all()

    plucking = (PluckingRecord.query.join(Farm)
                .filter(Farm.farmer_id == farmer.id)
                .order_by(PluckingRecord.date.desc()).limit(30).all())
    pruning = (PruningRecord.query.join(Farm)
               .filter(Farm.farmer_id == farmer.id)
               .order_by(PruningRecord.date.desc()).limit(10).all())
    tools = Tool.query.filter_by(farmer_id=farmer.id).all()
    notes = (Note.query.filter_by(farmer_id=farmer.id)
             .filter(~Note.title.like("__demo_seed%"))
             .order_by(Note.created_at.desc()).all())
    logins = (LoginActivity.query.filter_by(farmer_id=farmer.id)
              .order_by(LoginActivity.login_at.desc()).limit(20).all())

    return render_template("admin/farmer_detail.html", farmer=farmer, farms=farms,
                            plucking=plucking, pruning=pruning, tools=tools,
                            notes=notes, logins=logins)


@admin_bp.route("/logins")
@admin_required
def logins():
    all_logins = (LoginActivity.query
                  .order_by(LoginActivity.login_at.desc())
                  .limit(200).all())
    return render_template("admin/logins.html", logins=all_logins)
