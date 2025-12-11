from src.extensions import db
from datetime import datetime

# Separate file for supplier interaction models for better organization

class SupplierMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"), nullable=False)
    message_content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.Column(db.String(50)) # e.g., Order Inquiry, Performance Feedback

    # Relationship
    supplier = db.relationship("Supplier", back_populates="messages")

    def __repr__(self):
        return f"<SupplierMessage {self.id} for Supplier {self.supplier_id}>"

class SupplierReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False) # e.g., 1-5 stars
    feedback_text = db.Column(db.Text)
    review_date = db.Column(db.DateTime, default=datetime.utcnow)
    # Could add dimensions like delivery_timeliness_rating, quality_rating etc.

    # Relationship
    supplier = db.relationship("Supplier", back_populates="reviews")

    def __repr__(self):
        return f"<SupplierReview {self.id} for Supplier {self.supplier_id}>"

