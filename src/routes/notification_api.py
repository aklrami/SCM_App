from flask import Blueprint, jsonify, request
from src.extensions import db
from src.models.notification import Notification

notification_bp = Blueprint("notification_api", __name__, url_prefix="/api")

@notification_bp.route("/notifications", methods=["GET"])
def get_notifications():
    """Get notifications, optionally filter by read status or user."""
    # Basic implementation: Get all unread notifications
    # Add user filtering if user_id is implemented and authentication is added
    try:
        query = Notification.query.filter_by(is_read=False).order_by(Notification.created_at.desc())
        # Example filtering (if query params were used):
        # read_status = request.args.get("read", default="false").lower()
        # if read_status == "true":
        #     query = Notification.query.filter_by(is_read=True)
        # elif read_status == "all":
        #     query = Notification.query

        notifications = query.all()
        return jsonify([{
            "id": n.id,
            "message": n.message,
            "type": n.type,
            "related_entity_type": n.related_entity_type,
            "related_entity_id": n.related_entity_id,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat()
        } for n in notifications])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@notification_bp.route("/notifications/<int:notification_id>/read", methods=["PUT"])
def mark_notification_read(notification_id):
    """Mark a specific notification as read."""
    notification = Notification.query.get_or_404(notification_id)
    try:
        if not notification.is_read:
            notification.is_read = True
            db.session.commit()
        return jsonify({"message": "Notification marked as read", "notification_id": notification.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# Potential endpoint to create notifications internally (not typically exposed directly)
# def create_notification(message, type, related_entity_type=None, related_entity_id=None, user_id=None):
#     try:
#         new_notification = Notification(
#             message=message,
#             type=type,
#             related_entity_type=related_entity_type,
#             related_entity_id=related_entity_id,
#             user_id=user_id
#         )
#         db.session.add(new_notification)
#         db.session.commit()
#         return True
#     except Exception as e:
#         db.session.rollback()
#         print(f"Error creating notification: {e}") # Log error
#         return False

