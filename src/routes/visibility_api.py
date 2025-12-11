from flask import Blueprint, jsonify, request
from src.extensions import db
from src.models.supplier import Supplier
from src.models.product import Product
from src.models.inventory import Inventory
from src.models.purchase_order import PurchaseOrder
from sqlalchemy import func, case

visibility_bp = Blueprint("supply_chain_visibility_api", __name__, url_prefix="/api")

# --- Dashboard & Analytics ---

@visibility_bp.route("/dashboard/overview", methods=["GET"])
def get_dashboard_overview():
    """Get overview data for the dashboard."""
    try:
        total_suppliers = db.session.query(func.count(Supplier.id)).scalar()
        total_products = db.session.query(func.count(Product.id)).scalar()

        # Count open orders (not Delivered or Cancelled)
        open_orders = db.session.query(func.count(PurchaseOrder.id))\
            .filter(PurchaseOrder.status.notin_(["Delivered", "Cancelled"]))\
            .scalar()

        # Count low stock items (available < reorder_point)
        low_stock_count = db.session.query(func.count(Inventory.id))\
            .join(Product, Inventory.product_id == Product.id)\
            .filter(Inventory.available_quantity < Product.reorder_point)\
            .scalar()

        return jsonify({
            "total_suppliers": total_suppliers or 0,
            "total_products": total_products or 0,
            "open_orders": open_orders or 0,
            "low_stock_count": low_stock_count or 0
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@visibility_bp.route("/analytics/inventory_turnover", methods=["GET"])
def get_inventory_turnover():
    """Get inventory turnover analytics (placeholder)."""
    # Placeholder: Real calculation requires sales data over a period
    try:
        # Example: Calculate average inventory value (simplified)
        avg_inventory_value = db.session.query(func.sum(Inventory.available_quantity * Product.price))\
            .join(Product, Inventory.product_id == Product.id)\
            .scalar()

        return jsonify({
            "message": "Inventory turnover calculation requires sales data (not implemented in this scope).",
            "average_inventory_value_simple": avg_inventory_value or 0
            # "inventory_turnover_ratio": calculated_ratio
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@visibility_bp.route("/analytics/order_fulfillment", methods=["GET"])
def get_order_fulfillment():
    """Get order fulfillment analytics (placeholder)."""
    # Placeholder: Real calculation requires tracking fulfillment times
    try:
        # Example: Calculate fulfillment rate (Delivered / Total non-draft/cancelled)
        total_relevant_orders = db.session.query(func.count(PurchaseOrder.id))\
            .filter(PurchaseOrder.status.notin_(["Draft", "Cancelled"]))\
            .scalar()
        delivered_orders = db.session.query(func.count(PurchaseOrder.id))\
            .filter(PurchaseOrder.status == "Delivered")\
            .scalar()

        fulfillment_rate = (delivered_orders / total_relevant_orders * 100) if total_relevant_orders else 0

        # Example: Average fulfillment time (simplified - using created_at to delivered_at)
        # This requires delivered_at to be populated accurately
        avg_time_query = db.session.query(func.avg(func.julianday(PurchaseOrder.delivered_at) - func.julianday(PurchaseOrder.created_at)))\
            .filter(PurchaseOrder.status == "Delivered", PurchaseOrder.delivered_at.isnot(None), PurchaseOrder.created_at.isnot(None))\
            .scalar()
        avg_fulfillment_days = avg_time_query if avg_time_query else None

        return jsonify({
            "message": "Order fulfillment analytics based on available data.",
            "total_orders_considered": total_relevant_orders or 0,
            "delivered_orders": delivered_orders or 0,
            "fulfillment_rate_percentage": round(fulfillment_rate, 2),
            "average_fulfillment_days_approx": avg_fulfillment_days
        })
    except Exception as e:
        # Specific handling for SQLite date functions if needed
        if "julianday" in str(e).lower():
             return jsonify({"error": "Date difference calculation might not be fully supported or data is missing (e.g., delivered_at).", "details": str(e)}), 500
        return jsonify({"error": str(e)}), 500

# --- Product CRUD ---

@visibility_bp.route("/products", methods=["GET"])
def get_products():
    """Get a list of all products."""
    try:
        products = Product.query.options(db.joinedload(Product.supplier)).all() # Eager load supplier info
        return jsonify([p.to_dict(include_supplier=True) for p in products])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@visibility_bp.route("/products", methods=["POST"])
def add_product():
    """Add a new product."""
    data = request.get_json()
    if not data or not data.get("name") or data.get("price") is None or data.get("supplier_id") is None:
        return jsonify({"error": "Missing required fields: name, price, supplier_id"}), 400

    try:
        # Check if supplier exists
        supplier = Supplier.query.get(data["supplier_id"])
        if not supplier:
            # Corrected f-string with single quotes
            return jsonify({"error": f"Supplier with ID {data['supplier_id']} not found."}), 404

        new_product = Product(
            name=data["name"],
            description=data.get("description"),
            price=data["price"],
            supplier_id=data["supplier_id"],
            sku=data.get("sku"),
            category=data.get("category"),
            reorder_point=data.get("reorder_point", 10) # Default reorder point
        )
        db.session.add(new_product)
        db.session.flush() # Flush to get the new product ID

        # Create initial inventory record for the new product
        initial_inventory = Inventory(
            product_id=new_product.id,
            available_quantity=data.get("initial_quantity", 0), # Allow setting initial quantity
            reserved_quantity=0
        )
        db.session.add(initial_inventory)

        db.session.commit()
        return jsonify({"message": "Product added successfully", "product": new_product.to_dict(include_supplier=True)}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@visibility_bp.route("/products/<int:product_id>", methods=["GET"])
def get_product(product_id):
    """Get details for a specific product."""
    product = Product.query.options(db.joinedload(Product.supplier)).get_or_404(product_id)
    return jsonify(product.to_dict(include_supplier=True))

@visibility_bp.route("/products/<int:product_id>", methods=["PUT"])
def update_product(product_id):
    """Update an existing product."""
    product = Product.query.get_or_404(product_id)
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided for update"}), 400

    try:
        if "name" in data: product.name = data["name"]
        if "description" in data: product.description = data["description"]
        if "price" in data: product.price = data["price"]
        if "supplier_id" in data:
            # Check if new supplier exists
            supplier = Supplier.query.get(data["supplier_id"])
            if not supplier:
                # Corrected f-string with single quotes
                return jsonify({"error": f"Supplier with ID {data['supplier_id']} not found."}), 404
            product.supplier_id = data["supplier_id"]
        if "sku" in data: product.sku = data["sku"]
        if "category" in data: product.category = data["category"]
        if "reorder_point" in data: product.reorder_point = data["reorder_point"]

        db.session.commit()
        # Eager load supplier for the response
        updated_product = Product.query.options(db.joinedload(Product.supplier)).get(product_id)
        return jsonify({"message": "Product updated successfully", "product": updated_product.to_dict(include_supplier=True)})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@visibility_bp.route("/products/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):
    """Delete a product."""
    product = Product.query.get_or_404(product_id)
    try:
        # Need to handle related inventory, orders etc. before deleting
        # For simplicity, let's delete associated inventory first
        Inventory.query.filter_by(product_id=product_id).delete()
        # Add checks/handling for orders referencing this product if necessary

        db.session.delete(product)
        db.session.commit()
        return jsonify({"message": "Product and associated inventory deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to delete product: {str(e)}"}), 500

# --- Inventory Management ---

@visibility_bp.route("/inventory", methods=["GET"])
def get_inventory():
    """Get the full inventory list with product details."""
    try:
        inventory_items = db.session.query(Inventory, Product).join(Product, Inventory.product_id == Product.id).all()
        result = []
        for inv, prod in inventory_items:
            item_dict = inv.to_dict()
            item_dict["product_name"] = prod.name
            item_dict["sku"] = prod.sku
            item_dict["price"] = prod.price
            item_dict["reorder_point"] = prod.reorder_point
            item_dict["is_low_stock"] = inv.available_quantity < prod.reorder_point
            result.append(item_dict)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@visibility_bp.route("/inventory/<int:inventory_id>", methods=["PUT"])
def update_inventory_item(inventory_id):
    """Update specific inventory item quantities (e.g., after stock take)."""
    inventory_item = Inventory.query.get_or_404(inventory_id)
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided for update"}), 400

    try:
        updated = False
        if "available_quantity" in data:
            inventory_item.available_quantity = data["available_quantity"]
            updated = True
        if "reserved_quantity" in data:
            inventory_item.reserved_quantity = data["reserved_quantity"]
            updated = True

        if not updated:
            return jsonify({"error": "No valid fields provided for update (available_quantity or reserved_quantity)"}), 400

        db.session.commit()
        # Join with product to provide more context in response
        inv, prod = db.session.query(Inventory, Product).join(Product, Inventory.product_id == Product.id).filter(Inventory.id == inventory_id).one()
        item_dict = inv.to_dict()
        item_dict["product_name"] = prod.name
        item_dict["is_low_stock"] = inv.available_quantity < prod.reorder_point
        return jsonify({"message": "Inventory item updated successfully", "inventory_item": item_dict})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@visibility_bp.route("/inventory/low_stock", methods=["GET"])
def get_low_stock_items():
    """Get items where available quantity is below reorder point."""
    try:
        low_stock = db.session.query(Inventory, Product)\
            .join(Product, Inventory.product_id == Product.id)\
            .filter(Inventory.available_quantity < Product.reorder_point)\
            .all()
        result = []
        for inv, prod in low_stock:
            item_dict = inv.to_dict()
            item_dict["product_name"] = prod.name
            item_dict["sku"] = prod.sku
            item_dict["reorder_point"] = prod.reorder_point
            result.append(item_dict)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Add other visibility/analytics endpoints as needed

