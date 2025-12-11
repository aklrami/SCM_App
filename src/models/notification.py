from src.extensions import db
from datetime import datetime

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer) # Assuming notifications are user-specific, adjust if needed
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50)) # e.g., Alert, Information, Warning
    related_entity_type = db.Column(db.String(50)) # e.g., PurchaseOrder, Inventory
    related_entity_id = db.Column(db.Integer)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Notification {self.id} Type: {self.type}>"

