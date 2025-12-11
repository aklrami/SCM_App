from flask_login import UserMixin
from datetime import datetime
from src.main import db # Assuming db is initialized in main

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    image_file = db.Column(db.String(20), nullable=False, default="default.jpg")
    password_hash = db.Column(db.String(128), nullable=False)
    # Updated role to include 'supplier'. Enum or a separate Role table might be better for larger apps.
    role = db.Column(db.String(20), nullable=False, default="user")  # Roles: "user", "admin", "supplier"
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    date_created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships - example, assuming a supplier might be linked to a User account
    # If a User *is* a Supplier, this might be handled by role. 
    # If a User *manages* a Supplier entity, a relationship might be needed here or on Supplier model.
    # For now, role="supplier" will gate access to supplier-specific actions.
    # supplier_profile = db.relationship('Supplier', backref='user_account', uselist=False, lazy=True) # Example if linking User to a Supplier record

    def __repr__(self):
        return f"User('{self.username}', '{self.email}', '{self.role}', Active: {self.is_active})"

    # Helper properties for role checks (optional, but can make templates/routes cleaner)
    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_supplier(self):
        return self.role == "supplier"

    @property
    def is_general_user(self):
        return self.role == "user"

