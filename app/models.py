from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class Farmer(UserMixin, db.Model):
    __tablename__ = "farmers"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30))
    password_hash = db.Column(db.String(255), nullable=False)
    scale = db.Column(db.String(20), default="small")  # small_scale / large_scale
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    farms = db.relationship("Farm", backref="owner", lazy=True, cascade="all, delete-orphan")
    tools = db.relationship("Tool", backref="owner", lazy=True, cascade="all, delete-orphan")
    notes = db.relationship("Note", backref="owner", lazy=True, cascade="all, delete-orphan")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def total_bushes(self):
        return sum(f.approx_bushes or 0 for f in self.farms)


class Farm(db.Model):
    __tablename__ = "farms"

    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey("farmers.id"), nullable=False)
    farm_number = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(150))
    approx_bushes = db.Column(db.Integer, default=0)
    acreage = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    plucking_records = db.relationship("PluckingRecord", backref="farm", lazy=True, cascade="all, delete-orphan")
    pruning_records = db.relationship("PruningRecord", backref="farm", lazy=True, cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint("farmer_id", "farm_number", name="uq_farmer_farm_number"),)

    @property
    def total_kilos(self):
        return sum(r.kilos for r in self.plucking_records) or 0


class PluckingRecord(db.Model):
    __tablename__ = "plucking_records"

    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey("farms.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    kilos = db.Column(db.Float, nullable=False)
    pluckers_count = db.Column(db.Integer)
    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PruningRecord(db.Model):
    __tablename__ = "pruning_records"

    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey("farms.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    bushes_pruned = db.Column(db.Integer, nullable=False)
    prune_type = db.Column(db.String(50))
    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Tool(db.Model):
    __tablename__ = "tools"

    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey("farmers.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    cost = db.Column(db.Float)
    purchase_date = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(30), default="good")  # good / needs_repair / damaged / lost
    notes = db.Column(db.String(300))


class Note(db.Model):
    __tablename__ = "notes"

    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey("farmers.id"), nullable=False)
    farm_id = db.Column(db.Integer, db.ForeignKey("farms.id"), nullable=True)
    title = db.Column(db.String(150))
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class LoginActivity(db.Model):
    __tablename__ = "login_activities"

    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey("farmers.id"), nullable=False)
    login_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    success = db.Column(db.Boolean, default=True, nullable=False)

    farmer = db.relationship("Farmer", backref="login_activities")
