from src.main import db
from datetime import datetime

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    contact_person = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False) # Business email of the supplier entity
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    date_added = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Link to the User who manages this supplier profile
    # This user should have the "supplier" role.
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=True) # unique=True means one user per supplier profile. nullable=True if admin can create supplier profiles not yet assigned to a user.
    user = db.relationship("User", backref=db.backref("supplier_profile", uselist=False, lazy=True))

    products = db.relationship("Product", backref="supplier_entity", lazy=True, foreign_keys="Product.supplier_id") # Clarify FK if Product.supplier_id points here

    def __repr__(self):
           return f'Supplier(name="{self.name}", email="{self.email}", user_username="{self.user.username if self.user else "N/A"}")'
