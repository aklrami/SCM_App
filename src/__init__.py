from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate # Added Flask-Migrate import
import os

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate() # Initialized Migrate

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "a_very_secret_key_that_should_be_changed")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///site.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db) # Initialized Migrate with app and db

    login_manager.login_view = "frontend.login"
    login_manager.login_message_category = "info"

    from src.models.user import User
    # Ensure all your models are imported here or are discoverable by Flask-Migrate
    # For example, if they are in a models package:
    # from src import models 

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Import and register blueprints
    from src.routes.frontend_routes import frontend_bp
    app.register_blueprint(frontend_bp)

    # The db.create_all() call is often removed or commented out when using Flask-Migrate
    # as migrations will handle the database schema creation and updates.
    # with app.app_context():
    #     db.create_all()

    return app

