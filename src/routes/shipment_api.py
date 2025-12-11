from flask import Blueprint, jsonify, request
from src.extensions import db
from src.models.purchase_order import PurchaseOrder
from src.models.shipment import Shipment
from datetime import datetime

shipment_bp = Blueprint("shipment_api", __name__, url_prefix="/api")

@shipment_bp.route("/purchase_orders/<int:po_id>/shipments", methods=["GET"])
def get_shipments_for_order(po_id):
    """Get all shipments associated with a specific purchase order."""
    purchase_order = PurchaseOrder.query.get_or_404(po_id)
    try:
        shipments = Shipment.query.filter_by(purchase_order_id=po_id).order_by(Shipment.created_at.desc()).all()
        return jsonify([{
            "id": s.id,
            "purchase_order_id": s.purchase_order_id,
            "tracking_number": s.tracking_number,
            "carrier_details": s.carrier_details,
            "estimated_delivery_date": s.estimated_delivery_date.isoformat() if s.estimated_delivery_date else None,
            "actual_delivery_date": s.actual_delivery_date.isoformat() if s.actual_delivery_date else None,
            "status": s.status,
            "created_at": s.created_at.isoformat()
        } for s in shipments])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@shipment_bp.route("/shipments", methods=["POST"])
def create_shipment():
    """Create a new shipment record, typically linked to a purchase order."""
    data = request.get_json()
    if not data or "purchase_order_id" not in data:
        return jsonify({"error": "Missing required field: purchase_order_id"}), 400

    purchase_order = PurchaseOrder.query.get(data["purchase_order_id"])
    if not purchase_order:
        # Corrected f-string with single quotes for dict key
        return jsonify({"error": f"Purchase Order with id {data['purchase_order_id']} not found"}), 404

    try:
        new_shipment = Shipment(
            purchase_order_id=data["purchase_order_id"],
            tracking_number=data.get("tracking_number"),
            carrier_details=data.get("carrier_details"),
            status=data.get("status", "In Transit") # Default status
        )
        # Handle date parsing if provided
        if data.get("estimated_delivery_date"):
            try:
                new_shipment.estimated_delivery_date = datetime.fromisoformat(data["estimated_delivery_date"].split("T")[0]).date()
            except ValueError:
                return jsonify({"error": "Invalid format for estimated_delivery_date. Use YYYY-MM-DD."}), 400

        db.session.add(new_shipment)
        # Optionally update PO status to "Shipped" if not already
        if purchase_order.status not in ["Shipped", "Delivered", "Cancelled"]:
             purchase_order.status = "Shipped"
             purchase_order.shipped_at = datetime.utcnow()

        db.session.commit()
        return jsonify({"message": "Shipment created successfully", "shipment_id": new_shipment.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@shipment_bp.route("/shipments/<int:shipment_id>", methods=["PUT"])
def update_shipment(shipment_id):
    """Update shipment status, tracking, or delivery dates."""
    shipment = Shipment.query.get_or_404(shipment_id)
    data = request.get_json()
    if not data:
        return jsonify({"error": "No update data provided"}), 400

    try:
        updated = False
        if "tracking_number" in data:
            shipment.tracking_number = data["tracking_number"]
            updated = True
        if "carrier_details" in data:
            shipment.carrier_details = data["carrier_details"]
            updated = True
        if "status" in data:
            shipment.status = data["status"]
            updated = True
            # If status is "Delivered", update actual delivery date and potentially PO status
            if data["status"] == "Delivered":
                shipment.actual_delivery_date = datetime.utcnow().date()
                # Check if all shipments for the PO are delivered to update PO status
                # (More complex logic needed here for multi-shipment POs)
                po = PurchaseOrder.query.get(shipment.purchase_order_id)
                if po and po.status != "Delivered": # Simplified check
                    po.status = "Delivered"
                    po.delivered_at = datetime.utcnow()

        if "actual_delivery_date" in data:
             try:
                shipment.actual_delivery_date = datetime.fromisoformat(data["actual_delivery_date"].split("T")[0]).date()
                updated = True
             except ValueError:
                return jsonify({"error": "Invalid format for actual_delivery_date. Use YYYY-MM-DD."}), 400

        if updated:
            db.session.commit()
            return jsonify({"message": "Shipment updated successfully", "shipment_id": shipment.id})
        else:
            return jsonify({"message": "No fields provided to update"}), 304 # Not Modified

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

