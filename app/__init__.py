from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access your farm dashboard."
login_manager.login_message_category = "info"

migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    migrate.init_app(app, db)
    db.init_app(app)
    login_manager.init_app(app)

    from app.models import Farmer

    @login_manager.user_loader
    def load_user(user_id):
        return Farmer.query.get(int(user_id))

    from app.auth import auth_bp
    from app.main import main_bp
    from app.news import news_bp
    from app.chatbot import chatbot_bp
    from app.admin import admin_bp
    from app.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    with app.app_context():
        db.create_all()

    return app
