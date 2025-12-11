# Flask App Initializations
from flask import Flask, render_template, Response
from markupsafe import Markup
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate 
import os
import traceback 

from flask_wtf.csrf import CSRFProtect

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect() 

login_manager.login_view = "frontend.login"
login_manager.login_message_category = "info"

def nl2br(value):
    return Markup(str(value).replace('\n', '<br>\n'))

# User model will be imported later, after db and login_manager are initialized within create_app context

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Configuration
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev_secret_key_123!@#")
    app.config["WTF_CSRF_ENABLED"] = True # Explicitly ensure CSRF is enabled
    db_path = os.path.join(app.instance_path, "site.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", f"sqlite:///{db_path}")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["PROPAGATE_EXCEPTIONS"] = True 

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass 

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Import User model here, after db and login_manager are initialized and tied to app
    from .models.user import User

    # User loader callback - defined here to avoid circular import
    @login_manager.user_loader
    def load_user(user_id):
        if user_id is not None and user_id.isdigit():
            return User.query.get(int(user_id))
        return None

    from .routes.frontend_routes import frontend_bp
    from .routes.order_processing_api import order_processing_bp
    from .routes.supplier_collaboration_api import supplier_collaboration_bp
    from .routes.visibility_api import visibility_bp
    from .routes.api_routes import api_bp

    app.register_blueprint(frontend_bp, url_prefix="/")
    app.register_blueprint(order_processing_bp, url_prefix="/api/orders")
    app.register_blueprint(supplier_collaboration_bp, url_prefix="/api/suppliers")
    app.register_blueprint(visibility_bp, url_prefix="/api/visibility")
    app.register_blueprint(api_bp)

    # Register custom Jinja filters
    app.jinja_env.filters["nl2br"] = nl2br
    with app.app_context():
        # Ensure all models are imported if not already done for migrate/db operations
        from .models import supplier, product, inventory, order 
        pass

    @app.context_processor
    def inject_current_year():
        from datetime import datetime
        return dict(current_year=datetime.utcnow().year)

    @app.errorhandler(500)
    def internal_server_error_handler(e):
        original_error_str = str(e)
        original_traceback_str = traceback.format_exc()
        app.logger.error(f"Internal Server Error: {original_error_str}\n{original_traceback_str}")
        
        try:
            return render_template("500_debug.html", error=original_error_str, traceback=original_traceback_str), 500
        except Exception as template_render_error:
            template_error_traceback_str = traceback.format_exc()
            app.logger.error(f"Error rendering 500_debug.html: {template_render_error}\n{template_error_traceback_str}")
            plain_text_error = (
                f"INTERNAL SERVER ERROR - DEBUG MODE\n\n"
                f"Original Error: {original_error_str}\n\n"
                f"Original Traceback:\n{original_traceback_str}\n\n"
                f"Additionally, an error occurred while trying to render the 500_debug.html page:\n"
                f"Template Rendering Error: {str(template_render_error)}\n\n"
                f"Template Rendering Traceback:\n{template_error_traceback_str}"
            )
            return Response(plain_text_error, mimetype="text/plain", status=500)


    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0")

