from src.main import db
from datetime import datetime

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, unique=True) # One-to-one with Product
    quantity_on_hand = db.Column(db.Integer, nullable=False, default=0)
    reorder_level = db.Column(db.Integer, default=10) # Changed from low_stock_threshold and added
    location = db.Column(db.String(100), nullable=True) # Added location
    last_updated = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = db.relationship("Product", backref=db.backref("inventory_record", uselist=False))

    def __repr__(self):
        return f"Inventory(Product ID: {self.product_id}, Qty: {self.quantity_on_hand}, Reorder: {self.reorder_level}, Location: {self.location})"


