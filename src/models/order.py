from src.main import db
from datetime import datetime
# Import OrderCategory to establish the relationship
from .order_category import OrderCategory

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False) # Assuming orders are placed by users
    order_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False, default="Pending") # e.g., Pending, Processing, Shipped, Delivered, Cancelled
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    shipping_address = db.Column(db.String(200))
    customer_name = db.Column(db.String(100)) # Example if not linking to user or for guest checkouts
    customer_email = db.Column(db.String(120)) # Example

    # Foreign Key to OrderCategory
    order_category_id = db.Column(db.Integer, db.ForeignKey("order_category.id"), nullable=True) # Allow orders without a category initially or make it False if category is mandatory

    # Relationship to OrderItem
    items = db.relationship("OrderItem", backref="order", lazy=True, cascade="all, delete-orphan")
    # Relationship to User (if orders are linked to users)
    placer = db.relationship("User", backref="orders_placed", lazy=True)

    # Relationship to OrderCategory is defined by backref in OrderCategory model: category

    def __repr__(self):
        return f"Order(\\\'{self.id}\\\'{self.order_category_id}\\\'{self.status}\\\'{self.placer.username if self.placer else 'N/A'}\\\'{self.category.name if self.category else 'N/A'}\\\'{self.total_amount}\\')"

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_purchase = db.Column(db.Float, nullable=False) # Store price at time of order
    status = db.Column(db.String(50), nullable=False, default="Pending") # NEW FIELD: e.g., Pending, Processing, Shipped, Delivered, Cancelled

    # Relationships to Product (to get product details)
    product = db.relationship("Product", backref="order_items_assoc", lazy=True)

    def __repr__(self):
        return f"OrderItem(Order ID: {self.order_id}, Product ID: {self.product_id}, Qty: {self.quantity}, Status: {self.status})"

