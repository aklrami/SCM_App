from src.main import db
from datetime import datetime

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    category = db.Column(db.String(50))
    price = db.Column(db.Float, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"), nullable=False)
    date_added = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationship to Supplier. 
    # The backref is handled by the Supplier model (which creates 'supplier_entity' on Product).
    # We define 'supplier' here for direct access from Product instances (e.g., product.supplier).
    supplier = db.relationship("Supplier", foreign_keys=[supplier_id])

    # Relationship for inventory (one-to-one with Product)
    inventory_item = db.relationship("Inventory", backref="product_info", uselist=False, lazy=True)

    def __repr__(self):
        return f"Product(\\\\'{self.name}\\\\\', \\\\\'{self.sku}\\\\\\')"

