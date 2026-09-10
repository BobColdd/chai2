import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    db_url = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'chaiyako.db')}")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    FARM_REGION_NAME = "Kericho, Kenya"
    FARM_LAT = -0.3676
    FARM_LON = 35.2836
