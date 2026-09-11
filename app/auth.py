from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import Farmer, Farm, LoginActivity

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        scale = request.form.get("scale", "small")
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        farm_numbers_raw = request.form.get("farm_numbers", "").strip()
        farm_numbers = [f.strip() for f in farm_numbers_raw.split(",") if f.strip()]

        if not full_name or not email or not password:
            flash("Please fill in your name, email and password.", "error")
            return render_template("register.html")

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        if Farmer.query.filter_by(email=email).first():
            flash("An account with that email already exists. Please log in.", "error")
            return render_template("register.html")

        if not farm_numbers:
            flash("Please add at least one farm number.", "error")
            return render_template("register.html")

        farmer = Farmer(full_name=full_name, email=email, phone=phone, scale=scale)
        farmer.set_password(password)
        db.session.add(farmer)
        db.session.flush()

        for fn in farm_numbers:
            db.session.add(Farm(farmer_id=farmer.id, farm_number=fn))

        db.session.commit()
        login_user(farmer)
        flash(f"Karibu, {full_name}! Your farm account is ready.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        farmer = Farmer.query.filter_by(email=email).first()

        success = bool(farmer and farmer.check_password(password))
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
            next_page = request.args.get("next")
            return redirect(next_page or url_for("main.dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.landing"))
