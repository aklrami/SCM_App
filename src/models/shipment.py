from src.extensions import db
from datetime import datetime

class Shipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey("purchase_order.id"), nullable=False)
    tracking_number = db.Column(db.String(100))
    carrier_details = db.Column(db.String(100))
    estimated_delivery_date = db.Column(db.Date)
    actual_delivery_date = db.Column(db.Date)
    status = db.Column(db.String(50)) # e.g., In Transit, Delivered
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    purchase_order = db.relationship("PurchaseOrder", back_populates="shipments")

    def __repr__(self):
        return f"<Shipment {self.id} for PO {self.purchase_order_id}>"

