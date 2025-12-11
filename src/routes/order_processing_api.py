from flask import Blueprint, jsonify, request
from src.extensions import db
from src.models.purchase_order import PurchaseOrder
from src.models.product import Product
from src.models.supplier import Supplier
from src.models.inventory import Inventory
from datetime import datetime

order_processing_bp = Blueprint("order_processing_api", __name__, url_prefix="/api")

# --- Purchase Order CRUD ---

@order_processing_bp.route("/purchase_orders", methods=["GET"])
def get_purchase_orders():
    """Get a list of all purchase orders."""
    try:
        orders = PurchaseOrder.query.options(
            db.joinedload(PurchaseOrder.product),
            db.joinedload(PurchaseOrder.supplier)
        ).order_by(PurchaseOrder.created_at.desc()).all()
        return jsonify([o.to_dict(include_product=True, include_supplier=True) for o in orders])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@order_processing_bp.route("/purchase_orders", methods=["POST"])
def create_purchase_order():
    """Create a new purchase order."""
    data = request.get_json()
    required_fields = ["product_id", "supplier_id", "quantity", "expected_delivery"]
    if not data or not all(field in data for field in required_fields):
        return jsonify({"error": f"Missing required fields: {', '.join(required_fields)}"}), 400

    try:
        # Validate product and supplier exist
        product = Product.query.get(data["product_id"])
        if not product:
            return jsonify({"error": f"Product with ID {data['product_id']} not found."}), 404
        supplier = Supplier.query.get(data["supplier_id"])
        if not supplier:
            return jsonify({"error": f"Supplier with ID {data['supplier_id']} not found."}), 404

        # Validate quantity
        quantity = data["quantity"]
        if not isinstance(quantity, int) or quantity <= 0:
            return jsonify({"error": "Quantity must be a positive integer."}), 400

        # Validate expected delivery date format (assuming YYYY-MM-DD)
        try:
            expected_delivery_date = datetime.strptime(data["expected_delivery"], "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Invalid expected_delivery date format. Use YYYY-MM-DD."}), 400

        new_order = PurchaseOrder(
            product_id=data["product_id"],
            supplier_id=data["supplier_id"],
            quantity=quantity,
            status=data.get("status", "Pending"), # Default status
            expected_delivery=expected_delivery_date,
            # created_at is handled by default in the model
        )
        db.session.add(new_order)
        db.session.commit()

        # Eager load relationships for the response
        created_order = PurchaseOrder.query.options(
            db.joinedload(PurchaseOrder.product),
            db.joinedload(PurchaseOrder.supplier)
        ).get(new_order.id)

        return jsonify({"message": "Purchase order created successfully", "order": created_order.to_dict(include_product=True, include_supplier=True)}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@order_processing_bp.route("/purchase_orders/<int:order_id>", methods=["GET"])
def get_purchase_order(order_id):
    """Get details for a specific purchase order."""
    order = PurchaseOrder.query.options(
        db.joinedload(PurchaseOrder.product),
        db.joinedload(PurchaseOrder.supplier)
    ).get_or_404(order_id)
    return jsonify(order.to_dict(include_product=True, include_supplier=True))

@order_processing_bp.route("/purchase_orders/<int:order_id>", methods=["PUT"])
def update_purchase_order(order_id):
    """Update an existing purchase order (e.g., status, quantity, delivery date)."""
    order = PurchaseOrder.query.get_or_404(order_id)
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided for update"}), 400

    try:
        updated = False
        if "quantity" in data:
            quantity = data["quantity"]
            if not isinstance(quantity, int) or quantity <= 0:
                return jsonify({"error": "Quantity must be a positive integer."}), 400
            order.quantity = quantity
            updated = True
        if "status" in data:
            # Add validation for allowed statuses if needed
            order.status = data["status"]
            # If status changes to 'Delivered', update inventory
            if data["status"] == "Delivered" and order.status != "Delivered": # Check if status actually changed to Delivered
                inventory_item = Inventory.query.filter_by(product_id=order.product_id).first()
                if inventory_item:
                    inventory_item.available_quantity += order.quantity
                    # Optionally set delivered_at timestamp
                    order.delivered_at = datetime.utcnow()
                else:
                    # Handle case where inventory record doesn't exist (shouldn't happen ideally)
                    db.session.rollback()
                    return jsonify({"error": f"Inventory record for product ID {order.product_id} not found."}), 500
            updated = True
        if "expected_delivery" in data:
            try:
                order.expected_delivery = datetime.strptime(data["expected_delivery"], "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"error": "Invalid expected_delivery date format. Use YYYY-MM-DD."}), 400
            updated = True
        # Add other updatable fields as needed

        if not updated:
            return jsonify({"error": "No valid fields provided for update"}), 400

        db.session.commit()
        # Eager load relationships for the response
        updated_order = PurchaseOrder.query.options(
            db.joinedload(PurchaseOrder.product),
            db.joinedload(PurchaseOrder.supplier)
        ).get(order_id)
        return jsonify({"message": "Purchase order updated successfully", "order": updated_order.to_dict(include_product=True, include_supplier=True)})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@order_processing_bp.route("/purchase_orders/<int:order_id>", methods=["DELETE"])
def delete_purchase_order(order_id):
    """Delete a purchase order."""
    order = PurchaseOrder.query.get_or_404(order_id)

    # Optional: Add logic here - e.g., only allow deletion if status is 'Draft' or 'Cancelled'
    # if order.status not in ["Draft", "Cancelled"]:
    #     return jsonify({"error": "Cannot delete an active or delivered order."}), 403

    try:
        db.session.delete(order)
        db.session.commit()
        return jsonify({"message": "Purchase order deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to delete purchase order: {str(e)}"}), 500

# Add other order processing related endpoints if needed

