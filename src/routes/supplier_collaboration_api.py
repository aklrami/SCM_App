from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from src.extensions import db
from src.models.supplier import Supplier
from src.models.supplier_interaction import SupplierMessage, SupplierReview
from src.models.order import Order, OrderItem # Added Order, OrderItem
from src.models.product import Product # Added Product

supplier_collaboration_bp = Blueprint("supplier_collaboration_api", __name__, url_prefix="/api/suppliers") # Changed url_prefix to match main.py

# --- Supplier CRUD --- (Existing code remains the same)
@supplier_collaboration_bp.route("/", methods=["GET"]) # Changed to / to match /api/suppliers/ route prefix
def get_suppliers():
    """Get a list of all suppliers."""
    try:
        suppliers = Supplier.query.all()
        return jsonify([s.to_dict() for s in suppliers])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@supplier_collaboration_bp.route("/", methods=["POST"]) # Changed to / to match /api/suppliers/ route prefix
def add_supplier():
    """Add a new supplier."""
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "Missing required field: name"}), 400

    try:
        new_supplier = Supplier(
            name=data["name"],
            contact_details=data.get("contact_person", "") + \
                            (f"\nEmail: {data.get('email', 'N/A')}" if data.get("email") else "") + \
                            (f"\nPhone: {data.get('phone', 'N/A')}" if data.get("phone") else "") + \
                            (f"\nAddress: {data.get('address', 'N/A')}" if data.get("address") else ""),
            service_category=data.get("service_category")
        )
        db.session.add(new_supplier)
        db.session.commit()
        return jsonify({"message": "Supplier added successfully", "supplier": new_supplier.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@supplier_collaboration_bp.route("/<int:supplier_id>", methods=["GET"])
def get_supplier(supplier_id):
    """Get details for a specific supplier."""
    supplier = Supplier.query.get_or_404(supplier_id)
    return jsonify(supplier.to_dict())

@supplier_collaboration_bp.route("/<int:supplier_id>", methods=["PUT"])
def update_supplier(supplier_id):
    """Update an existing supplier."""
    supplier = Supplier.query.get_or_404(supplier_id)
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided for update"}), 400

    try:
        if "name" in data: supplier.name = data["name"]
        
        contact_person = data.get("contact_person")
        email = data.get("email")
        phone = data.get("phone")
        address = data.get("address")
        
        if any(k in data for k in ["contact_person", "email", "phone", "address"]):
            supplier.contact_details = (f"{contact_person}" if contact_person else "") + \
                                     (f"\nEmail: {email}" if email else "") + \
                                     (f"\nPhone: {phone}" if phone else "") + \
                                     (f"\nAddress: {address}" if address else "")

        if "service_category" in data: supplier.service_category = data["service_category"]

        db.session.commit()
        return jsonify({"message": "Supplier updated successfully", "supplier": supplier.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@supplier_collaboration_bp.route("/<int:supplier_id>", methods=["DELETE"])
def delete_supplier(supplier_id):
    """Delete a supplier."""
    supplier = Supplier.query.get_or_404(supplier_id)
    try:
        if supplier.purchase_orders or supplier.products:
             return jsonify({"error": "Cannot delete supplier with existing products or orders. Please reassign or delete them first."}), 400

        db.session.delete(supplier)
        db.session.commit()
        return jsonify({"message": "Supplier deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to delete supplier: {str(e)}"}), 500

# --- Supplier Order Item Management ---
@supplier_collaboration_bp.route("/order_items", methods=["GET"])
@login_required
def get_supplier_order_items():
    """Get all order items for the currently logged-in supplier."""
    if not current_user.is_authenticated or current_user.role != "supplier":
        return jsonify({"error": "Unauthorized access. Supplier login required."}), 403
    
    supplier_id = current_user.id # Assuming supplier user's ID is the supplier_id
    
    try:
        # Query OrderItems, joining with Product to filter by supplier_id
        order_items = db.session.query(OrderItem).join(Product, OrderItem.product_id == Product.id).filter(Product.supplier_id == supplier_id).all()
        
        # Serialize the order items. Consider adding more details if needed.
        result = []
        for item in order_items:
            result.append({
                "order_item_id": item.id,
                "order_id": item.order_id,
                "product_id": item.product_id,
                "product_name": item.product.name, # Assuming Product model has a 'name' field
                "quantity": item.quantity,
                "price_at_purchase": item.price_at_purchase,
                "status": item.status
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@supplier_collaboration_bp.route("/order_items/<int:item_id>/status", methods=["PUT"])
@login_required
def update_supplier_order_item_status(item_id):
    """Update the status of a specific order item by the supplier."""
    if not current_user.is_authenticated or current_user.role != "supplier":
        return jsonify({"error": "Unauthorized access. Supplier login required."}), 403

    data = request.get_json()
    new_status = data.get("status")

    if not new_status:
        return jsonify({"error": "Missing 'status' in request body"}), 400

    # Define allowed statuses (should match admin's options)
    allowed_statuses = ["Pending", "Processing", "Shipped", "Delivered", "Cancelled"]
    if new_status not in allowed_statuses:
        return jsonify({"error": f"Invalid status. Allowed statuses are: {', '.join(allowed_statuses)}"}), 400

    supplier_id = current_user.id # Assuming supplier user's ID is the supplier_id

    try:
        order_item = db.session.query(OrderItem).join(Product, OrderItem.product_id == Product.id).filter(OrderItem.id == item_id, Product.supplier_id == supplier_id).first()

        if not order_item:
            return jsonify({"error": "Order item not found or you do not have permission to update it."}), 404

        order_item.status = new_status
        db.session.commit()
        return jsonify({"message": "Order item status updated successfully", "order_item_id": order_item.id, "new_status": order_item.status})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# --- Supplier Collaboration Features (Messages, Reviews, Performance) --- (Existing code remains the same)
@supplier_collaboration_bp.route("/<int:supplier_id>/messages", methods=["GET", "POST"])
def manage_supplier_messages(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    if request.method == "POST":
        data = request.get_json()
        if not data or "message_content" not in data:
            return jsonify({"error": "Missing message_content"}), 400
        try:
            new_message = SupplierMessage(supplier_id=supplier_id, message_content=data["message_content"], category=data.get("category"))
            db.session.add(new_message)
            db.session.commit()
            return jsonify({"message": "Message sent successfully", "message_id": new_message.id}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500
    else: # GET
        try:
            messages = SupplierMessage.query.filter_by(supplier_id=supplier_id).order_by(SupplierMessage.timestamp.desc()).all()
            return jsonify([m.to_dict() for m in messages])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@supplier_collaboration_bp.route("/<int:supplier_id>/performance", methods=["GET"])
def get_supplier_performance(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    try:
        performance_score = supplier.performance_metrics or 0
        return jsonify({"supplier_id": supplier.id, "supplier_name": supplier.name, "overall_performance_score": performance_score})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@supplier_collaboration_bp.route("/<int:supplier_id>/reviews", methods=["POST"])
def create_supplier_review(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    data = request.get_json()
    if not data or "rating" not in data:
        return jsonify({"error": "Missing required field: rating"}), 400
    try:
        new_review = SupplierReview(supplier_id=supplier_id, rating=data["rating"], feedback_text=data.get("feedback_text"))
        db.session.add(new_review)
        db.session.commit()
        return jsonify({"message": "Review created successfully", "review_id": new_review.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@supplier_collaboration_bp.route("/<int:supplier_id>/reviews", methods=["GET"])
def get_supplier_reviews(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    try:
        reviews = SupplierReview.query.filter_by(supplier_id=supplier_id).order_by(SupplierReview.review_date.desc()).all()
        return jsonify([r.to_dict() for r in reviews])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

