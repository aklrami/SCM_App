from src.extensions import db
from datetime import datetime

class PurchaseOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False) # Assuming one product per PO based on dummy data/docs
    quantity = db.Column(db.Integer, nullable=False, default=1) # Added quantity field
    status = db.Column(db.String(50), default="Draft") # e.g., Draft, Submitted, Shipped, Delivered, Cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)
    shipped_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    expected_delivery = db.Column(db.Date)

    # Relationships
    supplier = db.relationship("Supplier", back_populates="purchase_orders")
    product = db.relationship("Product", back_populates="purchase_order_items")
    shipments = db.relationship("Shipment", back_populates="purchase_order") # One PO might have multiple shipments

    def __repr__(self):
        return f"<PurchaseOrder {self.id} Status: {self.status}>"

