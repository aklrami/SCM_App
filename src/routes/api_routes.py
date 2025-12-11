from flask import Blueprint, jsonify
from flask_login import login_required
from src.main import db
from src.models.supplier import Supplier
from src.models.product import Product
from src.models.inventory import Inventory
from src.models.order import Order, OrderItem
from sqlalchemy import func

# Placeholder data - in a real app, this would come from database queries
placeholder_overview_data = {
    "total_suppliers": 0,
    "total_products": 0,
    "open_orders": 0,
    "low_stock_items": 0
}

placeholder_fulfillment_data = {
    "labels": ["Jan", "Feb", "Mar", "Apr", "May"],
    "datasets": [{
        "label": "Orders Fulfilled",
        "data": [0, 0, 0, 0, 0],
        "borderColor": "#4CAF50",
        "tension": 0.1
    }]
}

placeholder_turnover_data = {
    "labels": ["Product A", "Product B", "Product C"],
    "datasets": [{
        "label": "Inventory Turnover Rate",
        "data": [0, 0, 0],
        "backgroundColor": ["#FF6384", "#36A2EB", "#FFCE56"]
    }]
}

api_bp = Blueprint("api", __name__, url_prefix="/api")

@api_bp.route("/dashboard/overview", methods=["GET"])
@login_required
def dashboard_overview():
    total_suppliers = Supplier.query.count()
    total_products = Product.query.count()
    open_orders = Order.query.filter(Order.status == "Pending").count() # Assuming 'Pending' means open
    # Using the same logic as in frontend_routes for low_stock_items_count
    low_stock_items = Inventory.query.filter(Inventory.quantity_on_hand <= Inventory.low_stock_threshold, Inventory.quantity_on_hand > 0).count()
    
    overview_data = {
        "total_suppliers": total_suppliers,
        "total_products": total_products,
        "open_orders": open_orders,
        "low_stock_count": low_stock_items # Frontend expects low_stock_count
    }
    return jsonify(overview_data)

@api_bp.route("/analytics/order_fulfillment", methods=["GET"])
@login_required
def order_fulfillment_rate():
    total_orders_considered = Order.query.filter(Order.status.in_(["Shipped", "Delivered", "Processing", "Pending"])).count()
    delivered_orders = Order.query.filter(Order.status == "Delivered").count()
    
    fulfillment_rate_percentage = (delivered_orders / total_orders_considered * 100) if total_orders_considered > 0 else 0
    
    fulfillment_data = {
        "total_orders_considered": total_orders_considered,
        "delivered_orders": delivered_orders,
        "fulfillment_rate_percentage": round(fulfillment_rate_percentage, 2)
    }
    return jsonify(fulfillment_data)

@api_bp.route("/analytics/inventory_turnover", methods=["GET"])
@login_required
def inventory_turnover():
    # Simplified: Calculate total value of current inventory
    # A true turnover rate would require cost of goods sold (COGS) and average inventory over a period.
    # This provides a simple current inventory value instead, as requested by the frontend.
    total_value = db.session.query(func.sum(Product.price * Inventory.quantity_on_hand)) \
        .join(Inventory, Product.id == Inventory.product_id) \
        .scalar()
    
    inventory_value_data = {
        "average_inventory_value_simple": round(total_value, 2) if total_value else 0
    }
    return jsonify(inventory_value_data)

# A simple health check endpoint for the API
@api_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "API is healthy"}), 200

