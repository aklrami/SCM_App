import os
import secrets
from PIL import Image # For resizing images
from flask import Blueprint, render_template, url_for, flash, redirect, request, abort, current_app, session
from werkzeug.security import generate_password_hash, check_password_hash
from src.main import db
from src.models.user import User
from src.models.supplier import Supplier
from src.models.product import Product
from src.models.inventory import Inventory
from src.models.order import Order, OrderItem
from src.models.order_category import OrderCategory # Ensure this is imported
from flask_login import login_user, current_user, logout_user, login_required
from functools import wraps
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
import logging
from datetime import datetime, timedelta # Added timedelta

from .utils import save_profile_picture # Assuming utils.py contains save_profile_picture
from src.forms import (
    RegistrationForm, LoginForm, 
    SupplierForm, ProductForm, 
    AddInventoryItemForm, AdjustStockForm,
    CreateOrderForm, OrderItemForm, UpdateOrderStatusForm,
    UpdateProfileForm, ChangePasswordForm, RemoveFromCartForm,
    OrderCategoryForm # Keep if category management page is desired, or remove if only via product form
)

frontend_bp = Blueprint("frontend", __name__)

# Role-based access control decorator
def role_required(role_name_or_list):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Please log in to access this page.", "info")
                return redirect(url_for("frontend.login", next=request.url))
            if not current_user.is_active:
                flash("Your account is not active. Please contact an administrator.", "warning")
                logout_user()
                return redirect(url_for("frontend.login"))
            
            allowed_roles = []
            if isinstance(role_name_or_list, str):
                allowed_roles.append(role_name_or_list)
            elif isinstance(role_name_or_list, list):
                allowed_roles = role_name_or_list
            else: # Should not happen, but as a safeguard
                allowed_roles = []

            # Admin has access to everything this decorator is applied to, unless specifically denied in route
            if current_user.is_admin:
                return f(*args, **kwargs)
            
            if current_user.role not in allowed_roles:
                flash("You do not have permission to access this page.", "danger")
                # Redirect to dashboard or a more appropriate page based on role
                return redirect(url_for("frontend.view_dashboard")) 
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@frontend_bp.route("/")
@frontend_bp.route("/index")
def index():
    if current_user.is_authenticated and current_user.is_active:
        return redirect(url_for("frontend.view_dashboard"))
    return redirect(url_for("frontend.login"))

@frontend_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("frontend.index"))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        
        is_first_user = User.query.count() == 0 
        user_role_to_set = "admin" if is_first_user else form.role.data
        user_is_active = True if is_first_user else False
        
        user = User(username=form.username.data, 
                    email=form.email.data, 
                    password_hash=hashed_password, 
                    role=user_role_to_set,
                    is_active=user_is_active)
        try:
            db.session.add(user)
            db.session.commit()
            if is_first_user:
                flash(f"Admin account created for {form.username.data}! You can now log in.", "success") # Corrected f-string
            else:
                flash_message = f"Account created for {form.username.data} as a {user_role_to_set.capitalize()}! Your account is pending admin approval."
                if user_role_to_set == "supplier":
                    flash_message += " Once activated, you may need to set up your supplier profile."
                flash(flash_message, "info")
            return redirect(url_for("frontend.login"))
        except IntegrityError as ie:
            db.session.rollback()
            if "user.email" in str(ie.orig).lower() or "user_email_key" in str(ie.orig).lower():
                 flash("Email address already exists. Please use a different one.", "danger")
            elif "user.username" in str(ie.orig).lower() or "user_username_key" in str(ie.orig).lower():
                 flash("Username already exists. Please choose a different one.", "danger")
            else:
                current_app.logger.error(f"IntegrityError during registration: {ie}")
                flash("A registration error occurred. Please try a different username or email.", "danger")
            return render_template("register.html", title="Register", form=form)
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Unexpected error during registration: {e}", exc_info=True)
            flash(f"An unexpected error occurred. Please try again.", "danger")
            return render_template("register.html", title="Register", form=form)
    return render_template("register.html", title="Register", form=form)

@frontend_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated and current_user.is_active:
        return redirect(url_for("frontend.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            if not user.is_active:
                flash("Your account is not yet active. Please wait for admin approval or contact support.", "warning")
                return redirect(url_for("frontend.login"))
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get("next")
            flash("Login Successful!", "success")
            return redirect(next_page) if next_page else redirect(url_for("frontend.view_dashboard"))
        else:
            flash("Login Unsuccessful. Please check email and password", "danger")
    return render_template("login.html", title="Login", form=form)

@frontend_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("frontend.login"))

@frontend_bp.route("/dashboard")
@login_required
def view_dashboard():
    if not current_user.is_active:
        flash("Your account is not active. Please contact an administrator.", "warning")
        logout_user()
        return redirect(url_for("frontend.login"))

    stats = {}
    low_stock = []
    latest_orders = []
    top_suppliers = []
    chart_data = None

    # -----------------------------
    # KPI STATS
    # -----------------------------
    if current_user.is_admin:
        stats["total_users"] = User.query.count()
        stats["total_products"] = Product.query.count()
        stats["pending_orders"] = Order.query.filter_by(status="Pending").count()

    elif current_user.is_supplier:
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if supplier_profile:
            stats["supplier_products"] = Product.query.filter_by(supplier_id=supplier_profile.id).count()
            stats["supplier_orders"] = (
                Order.query.join(OrderItem).join(Product)
                .filter(Product.supplier_id == supplier_profile.id)
                .distinct()
                .count()
            )
        else:
            stats["supplier_products"] = 0
            stats["supplier_orders"] = 0

    elif current_user.is_general_user:
        stats["user_orders"] = Order.query.filter_by(user_id=current_user.id).count()

    # -----------------------------
    # LOW STOCK (Admin + Supplier)
    # -----------------------------
    if current_user.is_admin:
        low_stock_q = (
            db.session.query(
                Inventory.id.label("inventory_id"),
                Product.id.label("product_id"),
                Product.name.label("product_name"),
                Product.sku.label("sku"),
                Inventory.quantity_on_hand.label("qoh"),
                Inventory.reorder_level.label("reorder"),
                Inventory.location.label("location"),
                Supplier.name.label("supplier_name"),
            )
            .join(Product, Inventory.product_id == Product.id)
            .outerjoin(Supplier, Product.supplier_id == Supplier.id)
            .filter(Inventory.reorder_level.isnot(None))
            .filter(Inventory.quantity_on_hand <= Inventory.reorder_level)
            .order_by((Inventory.reorder_level - Inventory.quantity_on_hand).desc())
            .limit(6)
            .all()
        )
        low_stock = [dict(r._mapping) for r in low_stock_q]

    elif current_user.is_supplier:
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if supplier_profile:
            low_stock_q = (
                db.session.query(
                    Inventory.id.label("inventory_id"),
                    Product.id.label("product_id"),
                    Product.name.label("product_name"),
                    Product.sku.label("sku"),
                    Inventory.quantity_on_hand.label("qoh"),
                    Inventory.reorder_level.label("reorder"),
                    Inventory.location.label("location"),
                )
                .join(Product, Inventory.product_id == Product.id)
                .filter(Product.supplier_id == supplier_profile.id)
                .filter(Inventory.reorder_level.isnot(None))
                .filter(Inventory.quantity_on_hand <= Inventory.reorder_level)
                .order_by((Inventory.reorder_level - Inventory.quantity_on_hand).desc())
                .limit(6)
                .all()
            )
            low_stock = [dict(r._mapping) for r in low_stock_q]

    # -----------------------------
    # LATEST ORDERS (role-aware)
    # -----------------------------
    if current_user.is_admin:
        latest_orders = Order.query.order_by(Order.order_date.desc()).limit(8).all()

    elif current_user.is_supplier:
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if supplier_profile:
            latest_orders = (
                Order.query.join(OrderItem).join(Product)
                .filter(Product.supplier_id == supplier_profile.id)
                .distinct()
                .order_by(Order.order_date.desc())
                .limit(8)
                .all()
            )

    elif current_user.is_general_user:
        latest_orders = (
            Order.query.filter_by(user_id=current_user.id)
            .order_by(Order.order_date.desc())
            .limit(8)
            .all()
        )

    # -----------------------------
    # ADMIN: TOP SUPPLIERS
    # -----------------------------
    if current_user.is_admin:
        top_suppliers_q = (
            db.session.query(
                Supplier.id.label("supplier_id"),
                Supplier.name.label("supplier_name"),
                db.func.coalesce(db.func.sum(OrderItem.quantity), 0).label("units_sold"),
                db.func.count(db.func.distinct(Order.id)).label("orders_count"),
            )
            .join(Product, Product.supplier_id == Supplier.id)
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .group_by(Supplier.id, Supplier.name)
            .order_by(db.func.coalesce(db.func.sum(OrderItem.quantity), 0).desc())
            .limit(5)
            .all()
        )
        top_suppliers = [dict(r._mapping) for r in top_suppliers_q]

    # -----------------------------
    # CHARTS (Admin only) - efficient
    # -----------------------------
    if current_user.is_admin:
        today = datetime.utcnow().date()
        start_day = today - timedelta(days=6)

        per_day = (
            db.session.query(
                db.func.date(Order.order_date).label("d"),
                db.func.count(Order.id).label("c"),
            )
            .filter(db.func.date(Order.order_date) >= start_day)
            .group_by(db.func.date(Order.order_date))
            .all()
        )
        per_day_map = {row.d: row.c for row in per_day}

        order_trend_labels = [(start_day + timedelta(days=i)).strftime("%b %d") for i in range(7)]
        order_trend_data = [int(per_day_map.get(start_day + timedelta(days=i), 0)) for i in range(7)]

        category_data = (
            db.session.query(Product.category, db.func.count(Product.id))
            .group_by(Product.category)
            .all()
        )
        category_labels = [c[0] if c[0] else "Uncategorized" for c in category_data]
        category_counts = [int(c[1]) for c in category_data]

        chart_data = {
            "order_trend": {"labels": order_trend_labels, "data": order_trend_data},
            "category_distribution": {"labels": category_labels, "data": category_counts},
        }

    return render_template(
        "dashboard.html",
        title="Dashboard",
        stats=stats,
        chart_data=chart_data,
        low_stock=low_stock,
        latest_orders=latest_orders,
        top_suppliers=top_suppliers,
    )

@frontend_bp.route("/admin/users")
@role_required("admin")
def manage_users():
    users = User.query.order_by(User.date_created.desc()).all()
    return render_template("admin_users.html", title="Manage Users", users=users)

@frontend_bp.route("/admin/user/activate/<int:user_id>", methods=["POST"])
@role_required("admin")
def activate_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id and user.role == "admin": 
        flash("Admins cannot deactivate their own account.", "danger")
        return redirect(url_for("frontend.manage_users"))
    user.is_active = True
    db.session.commit()
    flash(f"User {user.username} has been activated.", "success")
    return redirect(url_for("frontend.manage_users"))

@frontend_bp.route("/admin/user/deactivate/<int:user_id>", methods=["POST"])
@role_required("admin")
def deactivate_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id and user.role == "admin":
        flash("Admins cannot deactivate their own account.", "danger")
        return redirect(url_for("frontend.manage_users"))
    user.is_active = False
    db.session.commit()
    flash(f"User {user.username} has been deactivated.", "warning")
    return redirect(url_for("frontend.manage_users"))

@frontend_bp.route("/admin/user/set_role/<int:user_id>/<string:new_role>", methods=["POST"])
@role_required("admin")
def set_user_role(user_id, new_role):
    user = User.query.get_or_404(user_id)
    if new_role not in ["user", "supplier", "admin"]:
        flash("Invalid role specified.", "danger")
        return redirect(url_for("frontend.manage_users"))
    if user.id == current_user.id and user.role == "admin" and new_role != "admin":
        flash("Admins cannot change their own role from Admin.", "danger")
        return redirect(url_for("frontend.manage_users"))
    user.role = new_role
    if new_role == "admin": 
        user.is_active = True
    db.session.commit()
    flash(f"User {user.username}\\'s role has been set to {new_role.capitalize()}.")
    return redirect(url_for("frontend.manage_users"))

# --- Supplier Routes ---
@frontend_bp.route("/suppliers")
@login_required 
def view_suppliers():
    if not current_user.is_active:
        flash("Your account is not active. Please contact an administrator.", "warning")
        logout_user()
        return redirect(url_for("frontend.login"))

    if current_user.is_supplier:
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if supplier_profile:
            return redirect(url_for("frontend.edit_supplier", supplier_id=supplier_profile.id))
        else:
            flash("Please create your supplier profile to proceed.", "info")
            return redirect(url_for("frontend.add_supplier"))
    elif current_user.is_admin:
        suppliers = Supplier.query.order_by(Supplier.name).all()
        return render_template("suppliers.html", title="Manage Suppliers", suppliers=suppliers)
    else: 
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("frontend.view_dashboard"))

@frontend_bp.route("/supplier/add", methods=["GET", "POST"])
@role_required(["admin", "supplier"])
def add_supplier():
    form = SupplierForm()
    if current_user.is_supplier:
        existing_supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if existing_supplier_profile:
            flash("You already have a supplier profile. You can edit it.", "info")
            return redirect(url_for("frontend.edit_supplier", supplier_id=existing_supplier_profile.id))

    if form.validate_on_submit():
        try:
            supplier = Supplier(
                name=form.name.data,
                contact_person=form.contact_person.data,
                email=form.email.data,
                phone=form.phone.data,
                address=form.address.data
            )
            if current_user.is_supplier:
                supplier.user_id = current_user.id 
            
            db.session.add(supplier)
            db.session.commit()
            flash("Supplier profile created successfully!", "success")
            if current_user.is_supplier:
                return redirect(url_for("frontend.edit_supplier", supplier_id=supplier.id))
            return redirect(url_for("frontend.view_suppliers"))
        except IntegrityError:
            db.session.rollback()
            flash("Supplier email or name already exists.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding supplier: {e}")
            flash("An error occurred while adding the supplier.", "danger")
    return render_template("supplier_form.html", title="Create Supplier Profile", form=form, legend="New Supplier Profile")

@frontend_bp.route("/supplier/edit/<int:supplier_id>", methods=["GET", "POST"])
@login_required 
def edit_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    if not (current_user.is_admin or (current_user.is_supplier and supplier.user_id == current_user.id)):
        flash("You do not have permission to edit this supplier profile.", "danger")
        abort(403)
    form = SupplierForm(obj=supplier)
    if form.validate_on_submit():
        try:
            form.populate_obj(supplier)
            db.session.commit()
            flash("Supplier profile updated successfully!", "success")
            if current_user.is_admin:
                 return redirect(url_for("frontend.view_suppliers"))
            return redirect(url_for("frontend.edit_supplier", supplier_id=supplier.id)) 
        except IntegrityError:
            db.session.rollback()
            flash("Supplier email or name already exists for another record.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating supplier: {e}")
            flash("An error occurred while updating the supplier.", "danger")
    return render_template("supplier_form.html", title="Edit Supplier Profile", form=form, legend=f"Edit Supplier: {supplier.name}")

@frontend_bp.route("/supplier/delete/<int:supplier_id>", methods=["POST"])
@login_required 
def delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    if not (current_user.is_admin or (current_user.is_supplier and supplier.user_id == current_user.id)):
        flash("You do not have permission to delete this supplier profile.", "danger")
        abort(403)
    try:
        # Check if supplier is associated with any products
        if Product.query.filter_by(supplier_id=supplier.id).first():
             flash(f"Cannot delete supplier \'{supplier.name}\'. It is associated with products. Reassign or delete products first.", "danger")
             return redirect(url_for("frontend.view_suppliers"))
        
        db.session.delete(supplier)
        db.session.commit()
        flash("Supplier profile deleted successfully!", "success")
        if current_user.is_admin:
            return redirect(url_for("frontend.view_suppliers"))
        else: # If a supplier deletes their own profile
            return redirect(url_for("frontend.view_dashboard")) # Or perhaps to login page after logout
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting supplier: {e}")
        flash("An error occurred while deleting the supplier.", "danger")
        return redirect(url_for("frontend.view_suppliers"))

# --- Product Routes ---
@frontend_bp.route("/products")
@login_required 
def view_products():
    if not current_user.is_active:
        flash("Your account is not active. Please contact an administrator.", "warning")
        logout_user()
        return redirect(url_for("frontend.login"))
    
    # General users are redirected to shop, they don\'t manage products here
    if current_user.is_general_user:
        flash("Access denied. Please browse products in the shop.", "info")
        return redirect(url_for("frontend.shop_products"))

    page = request.args.get("page", 1, type=int)
    search_term = request.args.get("search", "")
    query = Product.query

    # If the current user is a supplier, filter products by their supplier_id
    if current_user.is_supplier:
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if supplier_profile:
            query = query.filter(Product.supplier_id == supplier_profile.id)
        else:
            # No supplier profile, so they shouldn\'t see any products to manage
            query = query.filter(False) # Effectively returns no results
            flash("You need to set up your supplier profile to view or manage your products.", "info")
            # Optionally redirect to add_supplier or dashboard
            # return redirect(url_for("frontend.add_supplier")) 
    
    if search_term:
        query = query.filter(Product.name.ilike(f"%{search_term}%"))
        
    products_pagination = query.order_by(Product.name).paginate(page=page, per_page=10)
    return render_template("products.html", title="Manage Products", products_pagination=products_pagination, search_term=search_term)

@frontend_bp.route("/product/add", methods=["GET", "POST"])
@role_required(["admin", "supplier"])
def add_product():
    form = ProductForm()
    categories = OrderCategory.query.order_by(OrderCategory.name).all()
    form.product_category_id.choices = [(oc.id, oc.name) for oc in categories]
    form.product_category_id.choices.insert(0, (0, "Select a category or add new below"))

    if current_user.is_admin:
        form.supplier_id.choices = [(s.id, s.name) for s in Supplier.query.order_by(Supplier.name).all()]
        if not form.supplier_id.choices and request.method == "GET":
             flash("No suppliers available. Please add a supplier first.", "info")
    elif current_user.is_supplier:
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if not supplier_profile:
            flash("You must have a supplier profile to add products.", "danger")
            return redirect(url_for("frontend.add_supplier"))
        form.supplier_id.choices = [(supplier_profile.id, supplier_profile.name)]
        if request.method == "GET": # Pre-select supplier for supplier user
            form.supplier_id.data = supplier_profile.id # Set default value for the field

    if form.validate_on_submit():
        try:
            # Ensure supplier isn\'t trying to assign product to another supplier
            if current_user.is_supplier:
                supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
                if not supplier_profile or form.supplier_id.data != supplier_profile.id:
                    flash("Invalid supplier ID for your role.", "danger")
                    # Repopulate choices before rendering template again
                    form.product_category_id.choices = [(oc.id, oc.name) for oc in OrderCategory.query.order_by(OrderCategory.name).all()]
                    form.product_category_id.choices.insert(0, (0, "Select a category or add new below"))
                    form.supplier_id.choices = [(supplier_profile.id, supplier_profile.name)] if supplier_profile else []
                    return render_template("product_form.html", title="Add Product", form=form, legend="New Product")
            
            category_to_assign = None
            new_category_created_this_request = False # Flag to avoid double commit issues
            if form.new_category_name.data:
                new_cat_name = form.new_category_name.data.strip()
                existing_category = OrderCategory.query.filter(OrderCategory.name.ilike(new_cat_name)).first()
                if existing_category:
                    category_to_assign = existing_category
                    flash(f"Using existing category: \'{new_cat_name}\'.", "info")
                else:
                    new_cat_desc = form.new_category_description.data.strip() if form.new_category_description.data else None
                    category_to_assign = OrderCategory(name=new_cat_name, description=new_cat_desc)
                    db.session.add(category_to_assign)
                    new_category_created_this_request = True # Mark that we added it
                    flash(f"New category \'{new_cat_name}\' will be created.", "info")
            elif form.product_category_id.data and form.product_category_id.data != 0:
                category_to_assign = OrderCategory.query.get(form.product_category_id.data)
                if not category_to_assign:
                    flash("Selected product category not found.", "danger")
                    # Repopulate choices before rendering template
                    form.product_category_id.choices = [(oc.id, oc.name) for oc in OrderCategory.query.order_by(OrderCategory.name).all()]
                    form.product_category_id.choices.insert(0, (0, "Select a category or add new below"))
                    if current_user.is_admin: form.supplier_id.choices = [(s.id, s.name) for s in Supplier.query.order_by(Supplier.name).all()]
                    elif current_user.is_supplier: 
                        sp = Supplier.query.filter_by(user_id=current_user.id).first()
                        form.supplier_id.choices = [(sp.id, sp.name)] if sp else []
                    return render_template("product_form.html", title="Add Product", form=form, legend="New Product")
            else:
                flash("Please select an existing category or provide a name for a new category.", "danger")
                # Repopulate choices before rendering template
                form.product_category_id.choices = [(oc.id, oc.name) for oc in OrderCategory.query.order_by(OrderCategory.name).all()]
                form.product_category_id.choices.insert(0, (0, "Select a category or add new below"))
                if current_user.is_admin: form.supplier_id.choices = [(s.id, s.name) for s in Supplier.query.order_by(Supplier.name).all()]
                elif current_user.is_supplier: 
                    sp = Supplier.query.filter_by(user_id=current_user.id).first()
                    form.supplier_id.choices = [(sp.id, sp.name)] if sp else []
                return render_template("product_form.html", title="Add Product", form=form, legend="New Product")

            product = Product(
                name=form.name.data,
                sku=form.sku.data,
                description=form.description.data,
                category=category_to_assign.name if category_to_assign else None, # Assign category name string
                price=form.price.data,
                supplier_id=form.supplier_id.data
            )
            db.session.add(product)
            
            # If a new category was defined and added to session, commit it now with the product
            if new_category_created_this_request: # Commit here if new category was added
                db.session.commit()
            else: # Otherwise, commit only the product (or product + existing category link)
                db.session.commit()

            # Create an initial inventory record for the new product
            initial_inventory = Inventory(product_id=product.id, quantity_on_hand=0, reorder_level=10, location="Default") # Default qty 0
            db.session.add(initial_inventory)
            db.session.commit()

            flash("Product added successfully! An initial inventory record has been created with 0 stock. Please adjust stock as needed.", "success")
            return redirect(url_for("frontend.view_products"))
        except IntegrityError as ie:
            db.session.rollback()
            current_app.logger.error(f"Integrity error adding product: {ie}")
            if "product_sku_key" in str(ie.orig).lower() or "product.sku" in str(ie.orig).lower():
                 flash("Product SKU already exists.", "danger")
            elif "product_name_key" in str(ie.orig).lower() or "product.name" in str(ie.orig).lower(): 
                 flash("Product name already exists.", "danger")
            else:
                 flash("A database integrity error occurred. This could be a duplicate SKU or product name.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding product: {e}", exc_info=True)
            flash(f"An error occurred while adding the product: {str(e)}", "danger")
    
    # Repopulate choices if form validation fails or it\s a GET request
    if request.method == "GET" or (form.is_submitted() and not form.validate()):
        form.product_category_id.choices = [(oc.id, oc.name) for oc in OrderCategory.query.order_by(OrderCategory.name).all()]
        form.product_category_id.choices.insert(0, (0, "Select a category or add new below"))
        if current_user.is_admin:
            form.supplier_id.choices = [(s.id, s.name) for s in Supplier.query.order_by(Supplier.name).all()]
        elif current_user.is_supplier:
            supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
            if supplier_profile:
                form.supplier_id.choices = [(supplier_profile.id, supplier_profile.name)]
                form.supplier_id.data = supplier_profile.id # Ensure it is pre-selected
            else: # Should not happen if add_product check is in place
                form.supplier_id.choices = []

    return render_template("product_form.html", title="Add Product", form=form, legend="New Product")

@frontend_bp.route("/product/edit/<int:product_id>", methods=["GET", "POST"])
@login_required # Further role checks inside
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    allowed_to_edit = False
    if current_user.is_admin:
        allowed_to_edit = True
    elif current_user.is_supplier:
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if supplier_profile and product.supplier_id == supplier_profile.id:
            allowed_to_edit = True
    
    if not allowed_to_edit:
        flash("You do not have permission to edit this product.", "danger")
        abort(403)

    form = ProductForm(obj=product)
    # Populate choices for categories and suppliers
    form.product_category_id.choices = [(oc.id, oc.name) for oc in OrderCategory.query.order_by(OrderCategory.name).all()]
    form.product_category_id.choices.insert(0, (0, "Select a category or add new below"))
    if current_user.is_admin:
        form.supplier_id.choices = [(s.id, s.name) for s in Supplier.query.order_by(Supplier.name).all()]
    elif current_user.is_supplier:
        # Supplier can only see their own supplier ID and it should be disabled
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if supplier_profile:
            form.supplier_id.choices = [(supplier_profile.id, supplier_profile.name)]
            form.supplier_id.render_kw = {"disabled": True} # Disable supplier field for suppliers
        else: # Should not happen if checks are in place
            flash("Supplier profile not found. Cannot edit product.", "danger")
            return redirect(url_for("frontend.view_products"))

    if request.method == "GET":
        # Pre-fill form data from product object
        form.supplier_id.data = product.supplier_id
        if product.category: # Product.category is a string name
            category_obj = OrderCategory.query.filter_by(name=product.category).first()
            if category_obj:
                form.product_category_id.data = category_obj.id
            else:
                # If category string exists but no object, suggest creating it
                flash(f"Product has category \'{product.category}\' which is not in the OrderCategory table. You can create it or select another.", "warning")
                form.new_category_name.data = product.category # Pre-fill new category name

    if form.validate_on_submit():
        try:
            category_to_assign = None
            new_category_created_this_request = False
            if form.new_category_name.data:
                new_cat_name = form.new_category_name.data.strip()
                existing_category = OrderCategory.query.filter(OrderCategory.name.ilike(new_cat_name)).first()
                if existing_category:
                    category_to_assign = existing_category
                else:
                    new_cat_desc = form.new_category_description.data.strip() if form.new_category_description.data else None
                    category_to_assign = OrderCategory(name=new_cat_name, description=new_cat_desc)
                    db.session.add(category_to_assign)
                    new_category_created_this_request = True
            elif form.product_category_id.data and form.product_category_id.data != 0:
                category_to_assign = OrderCategory.query.get(form.product_category_id.data)
            
            # Populate product object from form
            product.name = form.name.data
            product.sku = form.sku.data
            product.description = form.description.data
            product.category = category_to_assign.name if category_to_assign else product.category # Keep old if none selected/created
            product.price = form.price.data
            # Supplier cannot change supplier_id of existing product via this form
            if current_user.is_admin:
                product.supplier_id = form.supplier_id.data

            if new_category_created_this_request:
                db.session.commit() # Commit new category first
            db.session.commit() # Commit product changes

            flash("Product updated successfully!", "success")
            return redirect(url_for("frontend.view_products"))
        except IntegrityError as ie:
            db.session.rollback()
            current_app.logger.error(f"Integrity error updating product: {ie}")
            if "product_sku_key" in str(ie.orig).lower() or "product.sku" in str(ie.orig).lower():
                 flash("Product SKU already exists for another product.", "danger")
            elif "product_name_key" in str(ie.orig).lower() or "product.name" in str(ie.orig).lower(): 
                 flash("Product name already exists for another product.", "danger")
            else:
                 flash("A database integrity error occurred. This could be a duplicate SKU or product name.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating product: {e}", exc_info=True)
            flash(f"An error occurred while updating the product: {str(e)}", "danger")
    
    # Repopulate choices if form validation fails or it\s a GET request
    if request.method == "GET" or (form.is_submitted() and not form.validate()):
        form.product_category_id.choices = [(oc.id, oc.name) for oc in OrderCategory.query.order_by(OrderCategory.name).all()]
        form.product_category_id.choices.insert(0, (0, "Select a category or add new below"))
        if current_user.is_admin:
            form.supplier_id.choices = [(s.id, s.name) for s in Supplier.query.order_by(Supplier.name).all()]
        elif current_user.is_supplier:
            supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
            if supplier_profile:
                form.supplier_id.choices = [(supplier_profile.id, supplier_profile.name)]
                form.supplier_id.data = supplier_profile.id # Ensure it is pre-selected
                form.supplier_id.render_kw = {"disabled": True}
            else:
                form.supplier_id.choices = []

    return render_template("product_form.html", title=f"Edit Product: {product.name}", form=form, legend=f"Edit Product: {product.name}")

@frontend_bp.route("/product/delete/<int:product_id>", methods=["POST"])
@login_required # Further role checks inside
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    allowed_to_delete = False
    if current_user.is_admin:
        allowed_to_delete = True
    elif current_user.is_supplier:
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if supplier_profile and product.supplier_id == supplier_profile.id:
            allowed_to_delete = True
    
    if not allowed_to_delete:
        flash("You do not have permission to delete this product.", "danger")
        abort(403)
    try:
        # Check if product is in any orders
        if OrderItem.query.filter_by(product_id=product.id).first():
            flash(f"Cannot delete product \'{product.name}\\' as it is part of existing orders. Consider deactivating it instead.", "danger")
            return redirect(url_for("frontend.view_products"))
        
        # Delete associated inventory records first
        Inventory.query.filter_by(product_id=product.id).delete()
        # Then delete the product
        db.session.delete(product)
        db.session.commit()
        flash("Product and its inventory records deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting product: {e}")
        flash("An error occurred while deleting the product.", "danger")
    return redirect(url_for("frontend.view_products"))

# --- Inventory Routes ---
@frontend_bp.route("/inventory")
@role_required(["admin", "supplier", "user"])
def view_inventory():
    page = request.args.get("page", 1, type=int)
    search_term = request.args.get("search", "")
    query = Inventory.query.join(Product) # Join with Product to allow searching by product name

    if current_user.is_supplier:
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if supplier_profile:
            query = query.filter(Product.supplier_id == supplier_profile.id)
        else:
            query = query.filter(False) # No supplier profile, no inventory to show
            flash("Please set up your supplier profile to manage inventory.", "info")

    if search_term:
        query = query.filter(or_(
            Product.name.ilike(f"%{search_term}%"),
            Product.sku.ilike(f"%{search_term}%"),
            Inventory.location.ilike(f"%{search_term}%")
        ))

    inventory_items_pagination = query.order_by(Product.name).paginate(page=page, per_page=10)
    return render_template("inventory.html", title="Manage Inventory", inventory_items_pagination=inventory_items_pagination, search_term=search_term)

@frontend_bp.route("/inventory/add", methods=["GET", "POST"])
@role_required(["admin", "supplier"])
def add_inventory_item():
    form = AddInventoryItemForm()
    # Populate product choices, filtered by supplier if current user is a supplier
    product_query = Product.query
    if current_user.is_supplier:
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if supplier_profile:
            product_query = product_query.filter(Product.supplier_id == supplier_profile.id)
        else:
            flash("Supplier profile not found. Cannot add inventory.", "danger")
            return redirect(url_for("frontend.view_inventory"))
    
    form.product_id.choices = [(p.id, f"{p.name} (SKU: {p.sku})") for p in product_query.order_by(Product.name).all()]
    if not form.product_id.choices:
        flash("No products available to add to inventory. Please add products first.", "info")
        # Optionally redirect to add_product if no products for this supplier
        # if current_user.is_supplier: return redirect(url_for("frontend.add_product"))

    if form.validate_on_submit():
        try:
            # Check if inventory for this product already exists
            existing_inventory = Inventory.query.filter_by(product_id=form.product_id.data).first()
            if existing_inventory:
                flash("Inventory record for this product already exists. Please edit the existing record.", "warning")
                return redirect(url_for("frontend.edit_inventory_item", inventory_id=existing_inventory.id))

            inventory_item = Inventory(
                product_id=form.product_id.data,
                quantity_on_hand=form.quantity_on_hand.data,
                reorder_level=form.reorder_level.data,
                location=form.location.data
            )
            db.session.add(inventory_item)
            db.session.commit()
            flash("Inventory item added successfully!", "success")
            return redirect(url_for("frontend.view_inventory"))
        except IntegrityError:
            db.session.rollback()
            flash("Error: Could not add inventory item due to a database conflict (e.g., product already has inventory).", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding inventory item: {e}")
            flash("An error occurred while adding the inventory item.", "danger")
    return render_template("inventory_form.html", title="Add Inventory Item", form=form, legend="New Inventory Item")

@frontend_bp.route("/inventory/edit/<int:inventory_id>", methods=["GET", "POST"])
@role_required(["admin", "supplier"])
def edit_inventory_item(inventory_id):
    inventory_item = Inventory.query.get_or_404(inventory_id)
    product = Product.query.get_or_404(inventory_item.product_id)

    # Security check: ensure supplier owns this inventory item\s product
    if current_user.is_supplier:
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if not supplier_profile or product.supplier_id != supplier_profile.id:
            flash("You do not have permission to edit this inventory item.", "danger")
            abort(403)

    form = AddInventoryItemForm(obj=inventory_item)
    # Product field should be read-only or not present in edit form for inventory
    # For simplicity, we will allow it to be displayed but not changed directly via this form.
    # The form.product_id is usually for selection on creation.
    # If we want to show the product, we can pass it to the template separately.
    del form.product_id # Remove product_id from edit form as it shouldn\t be changed here

    if form.validate_on_submit():
        try:
            inventory_item.quantity_on_hand = form.quantity_on_hand.data
            inventory_item.reorder_level = form.reorder_level.data
            inventory_item.location = form.location.data
            inventory_item.last_updated = datetime.utcnow()
            db.session.commit()
            flash("Inventory item updated successfully!", "success")
            return redirect(url_for("frontend.view_inventory"))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating inventory item: {e}")
            flash("An error occurred while updating the inventory item.", "danger")
    return render_template("inventory_form.html", title=f"Edit Inventory for {product.name}", 
                           form=form, legend=f"Edit Inventory: {product.name} (SKU: {product.sku})", 
                           product_name=product.name, product_sku=product.sku, inventory_id=inventory_id)

@frontend_bp.route("/inventory/adjust_stock/<int:inventory_id>", methods=["GET", "POST"])
@role_required(["admin", "supplier"])
def adjust_stock(inventory_id):
    inventory_item = Inventory.query.get_or_404(inventory_id)
    product = Product.query.get_or_404(inventory_item.product_id)
    form = AdjustStockForm()

    if current_user.is_supplier:
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if not supplier_profile or product.supplier_id != supplier_profile.id:
            flash("You do not have permission to adjust stock for this item.", "danger")
            abort(403)

    if form.validate_on_submit(): # This is POST request
        try:
            adjustment = form.adjustment.data
            if form.adjustment_type.data == "decrease":
                if inventory_item.quantity_on_hand - adjustment < 0:
                    flash("Cannot decrease stock below zero.", "danger")
                else:
                    inventory_item.quantity_on_hand -= adjustment
                    flash(f"Stock decreased by {adjustment}. New stock: {inventory_item.quantity_on_hand}", "success")
            else: # Increase
                inventory_item.quantity_on_hand += adjustment
                flash(f"Stock increased by {adjustment}. New stock: {inventory_item.quantity_on_hand}", "success")
            inventory_item.last_updated = datetime.utcnow()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adjusting stock: {e}")
            flash("An error occurred while adjusting stock.", "danger")
        return redirect(url_for("frontend.view_inventory"))
    
    # For GET request, render the adjustment form page
    return render_template("adjust_stock_form.html", title=f"Adjust Stock for {product.name}", 
                           form=form, legend=f"Adjust Stock: {product.name} (SKU: {product.sku})", 
                           inventory_item=inventory_item, product=product)

# --- Order Routes ---
@frontend_bp.route("/orders")
@login_required
def view_orders():
    page = request.args.get("page", 1, type=int)
    search_term = request.args.get("search", "")
    status_filter = request.args.get("status", "all")

    query = Order.query
    if current_user.is_supplier:
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if supplier_profile:
            # Filter orders that contain at least one item from this supplier
            query = query.join(OrderItem).join(Product).filter(Product.supplier_id == supplier_profile.id).distinct()
        else:
            query = query.filter(False) # No supplier profile, no orders to show
            flash("Please set up your supplier profile to view orders.", "info")
    elif current_user.is_general_user:
        query = query.filter(Order.user_id == current_user.id)
    # Admin sees all orders by default

    if search_term and current_user.is_admin: # Admin can search by order ID or customer name/email
        query = query.filter(or_(
            Order.id.like(f"%{search_term}%"), 
            Order.customer_name.ilike(f"%{search_term}%"),
            Order.customer_email.ilike(f"%{search_term}%")
        ))
    elif search_term: # Other users might search by order ID if allowed
        query = query.filter(Order.id.like(f"%{search_term}%"))

    if status_filter != "all":
        query = query.filter(Order.status == status_filter)

    orders_pagination = query.order_by(Order.order_date.desc()).paginate(page=page, per_page=10)
    return render_template("orders.html", title="Manage Orders", orders_pagination=orders_pagination, 
                           search_term=search_term, status_filter=status_filter)

@frontend_bp.route("/order/<int:order_id>")
@login_required
def view_order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    # Security: Ensure user has permission to view this order
    if current_user.is_general_user and order.user_id != current_user.id:
        flash("You do not have permission to view this order.", "danger")
        abort(403)
    elif current_user.is_supplier:
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if not supplier_profile or not any(item.product.supplier_id == supplier_profile.id for item in order.items):
            flash("You do not have permission to view this order or it contains no items from you.", "danger")
            abort(403)
    # Admin can view any order
    return render_template("order_detail.html", title=f"Order #{order.id}", order=order)

@frontend_bp.route("/order/update_status/<int:order_id>", methods=["POST"])
@role_required("admin")
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    form = UpdateOrderStatusForm()
    if form.validate_on_submit(): # This form might not have fields if status is just from select
        new_status = request.form.get("status")
        if new_status in ["Pending", "Processing", "Shipped", "Delivered", "Cancelled"]:
            order.status = new_status
            db.session.commit()
            flash(f"Order #{order.id} status updated to {new_status}.", "success")
        else:
            flash("Invalid status selected.", "danger")
    else:
        flash("Failed to update order status.", "danger")
    return redirect(url_for("frontend.view_order_detail", order_id=order_id))

# Route for supplier to update their item status (called by form in order_detail.html)
@frontend_bp.route("/order_item/update_status/<int:item_id>", methods=["POST"])
@role_required("supplier")
def update_supplier_order_item_status(item_id):
    order_item = OrderItem.query.get_or_404(item_id)
    order_id_for_redirect = request.form.get("order_id", order_item.order_id) # Get order_id for redirect

    # Security: Ensure the current supplier owns this order item
    supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
    if not supplier_profile or order_item.product.supplier_id != supplier_profile.id:
        flash("You do not have permission to update this item's status.", "danger")
        return redirect(url_for("frontend.view_order_detail", order_id=order_id_for_redirect))

    new_status = request.form.get("status")
    allowed_statuses = ["Pending", "Processing", "Shipped", "Delivered", "Cancelled"]

    if new_status and new_status in allowed_statuses:
        try:
            order_item.status = new_status
            db.session.commit()
            flash(f"Item \'{order_item.product.name}\' status updated to {new_status}.", "success")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating item status: {e}")
            flash("Error updating item status.", "danger")
    else:
        flash("Invalid status selected for item.", "danger")
    
    return redirect(url_for("frontend.view_order_detail", order_id=order_id_for_redirect))


# --- Shop & Cart Routes ---
@frontend_bp.route("/shop")
@login_required
def shop_products():
    page = request.args.get("page", 1, type=int)
    search_term = request.args.get("search", "")
    category_filter = request.args.get("category", "all")

    query = Product.query.join(Inventory).filter(Inventory.quantity_on_hand > 0) # Only show products with stock

    if search_term:
        query = query.filter(Product.name.ilike(f"%{search_term}%"))
    
    if category_filter != "all":
        query = query.filter(Product.category == category_filter)

    products_pagination = query.order_by(Product.name).paginate(page=page, per_page=9) # 9 for 3x3 grid
    categories = db.session.query(Product.category).distinct().order_by(Product.category).all()
    category_names = [c[0] for c in categories if c[0]]

    return render_template("shop_products.html", title="Shop Products", 
                           products_pagination=products_pagination, 
                           search_term=search_term, 
                           categories=category_names, 
                           current_category=category_filter)

@frontend_bp.route("/cart/add/<int:product_id>", methods=["POST"])
@login_required
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    inventory = Inventory.query.filter_by(product_id=product.id).first()
    quantity_to_add = int(request.form.get("quantity", 1))

    if quantity_to_add <= 0:
        flash("Quantity must be positive.", "danger")
        return redirect(request.referrer or url_for("frontend.shop_products"))

    if not inventory or inventory.quantity_on_hand < quantity_to_add:
        flash(f"Not enough stock for {product.name}. Available: {inventory.quantity_on_hand if inventory else 0}", "warning")
        return redirect(request.referrer or url_for("frontend.shop_products"))

    cart = session.get("cart", {})
    current_quantity_in_cart = cart.get(str(product_id), 0)
    
    if inventory.quantity_on_hand < (current_quantity_in_cart + quantity_to_add):
        flash(f"Cannot add {quantity_to_add} more of {product.name}. Total would exceed stock. Available: {inventory.quantity_on_hand}, In Cart: {current_quantity_in_cart}", "warning")
    else:
        cart[str(product_id)] = current_quantity_in_cart + quantity_to_add
        session["cart"] = cart
        session.modified = True
        flash(f"{quantity_to_add} x {product.name} added to cart.", "success")
    
    return redirect(request.referrer or url_for("frontend.shop_products"))

@frontend_bp.route("/cart", methods=["GET"])
@login_required
def view_cart():
    cart_session = session.get("cart", {})
    cart_items_details = []
    grand_total = 0
    remove_form = RemoveFromCartForm() # For removing individual items
    checkout_form = CreateOrderForm() # For the checkout details

    # Populate choices for order_category_id for the checkout_form
    order_categories = OrderCategory.query.order_by(OrderCategory.name).all()
    checkout_form.order_category_id.choices = [(oc.id, oc.name) for oc in order_categories]
    if not checkout_form.order_category_id.choices:
        checkout_form.order_category_id.choices = []

    # Pre-fill customer details if available
    if request.method == "GET":
        checkout_form.customer_name.data = checkout_form.customer_name.data or current_user.username
        checkout_form.customer_email.data = checkout_form.customer_email.data or current_user.email
        # Add shipping address prefill if stored on user model

    for product_id_str, quantity_in_cart in list(cart_session.items()): # Use list() for safe iteration if modifying
        product = Product.query.get(int(product_id_str))
        if product:
            inventory_item = Inventory.query.filter_by(product_id=product.id).first()
            available_stock = inventory_item.quantity_on_hand if inventory_item else 0
            
            # Adjust quantity in cart if it exceeds available stock (e.g., stock changed after adding)
            actual_quantity = min(quantity_in_cart, available_stock)
            if actual_quantity == 0 and quantity_in_cart > 0:
                # Item is now out of stock, remove from cart or notify
                cart_session.pop(product_id_str, None)
                session.modified = True
                flash(f"{product.name} was removed from your cart as it is now out of stock.", "warning")
                continue # Skip adding this item to display
            elif actual_quantity < quantity_in_cart:
                cart_session[product_id_str] = actual_quantity
                session.modified = True
                flash(f"Quantity for {product.name} adjusted to {actual_quantity} due to stock availability.", "info")

            subtotal = product.price * actual_quantity
            cart_items_details.append({
                "product_id": product.id, "name": product.name, "price": product.price,
                "quantity": actual_quantity, "available_stock": available_stock, "subtotal": subtotal
            })
            grand_total += subtotal
        else:
            # Product not found (e.g., deleted), remove from cart
            cart_session.pop(product_id_str, None)
            session.modified = True
            flash(f"A product (ID: {product_id_str}) was removed from your cart as it no longer exists.", "warning")

    return render_template("order_form.html", title="Your Cart & Checkout", 
                           cart_items=cart_items_details, grand_total=grand_total, 
                           remove_form=remove_form, checkout_form=checkout_form)

@frontend_bp.route("/cart/update/<int:product_id>", methods=["POST"])
@login_required
def update_cart_item(product_id):
    cart = session.get("cart", {})
    product_id_str = str(product_id)
    new_quantity = int(request.form.get("quantity", 0))

    if product_id_str in cart:
        if new_quantity > 0:
            product = Product.query.get(product_id)
            inventory = Inventory.query.filter_by(product_id=product_id).first()
            if product and inventory:
                if inventory.quantity_on_hand < new_quantity:
                    flash(f"Cannot update quantity for {product.name}. Only {inventory.quantity_on_hand} available.", "warning")
                    cart[product_id_str] = inventory.quantity_on_hand # Adjust to max available
                else:
                    cart[product_id_str] = new_quantity
                    flash(f"Quantity for {product.name} updated.", "success")
            else:
                flash("Product not found or inventory missing.", "danger") # Should not happen if in cart
                cart.pop(product_id_str, None)
        else: # Quantity is 0 or less, remove item
            cart.pop(product_id_str, None)
            flash("Item removed from cart.", "info")
        session["cart"] = cart
        session.modified = True
    else:
        flash("Item not found in cart to update.", "warning")
    return redirect(url_for("frontend.view_cart"))

@frontend_bp.route("/cart/remove/<int:product_id>", methods=["POST"])
@login_required
def remove_from_cart(product_id):
    form = RemoveFromCartForm() # For CSRF validation
    if form.validate_on_submit():
        cart = session.get("cart", {})
        product_id_str = str(product_id)
        if product_id_str in cart:
            product_name = Product.query.get(product_id).name if Product.query.get(product_id) else "Item"
            cart.pop(product_id_str, None)
            session["cart"] = cart
            session.modified = True
            flash(f"{product_name} removed from cart.", "info")
        else:
            flash("Item not found in cart.", "warning")
    else:
        # Handle case where form validation might fail if it had fields
        flash("Could not remove item.", "danger")
    return redirect(url_for("frontend.view_cart"))

@frontend_bp.route("/cart/clear")
@login_required
def clear_cart():
    # Clear the cart stored in the session
    session.pop("cart", None)
    session.modified = True
    flash("Cart cleared.", "info")
    return redirect(url_for("frontend.view_cart"))

@frontend_bp.route("/order/place", methods=["POST"])
@login_required
def place_order():
    cart_session = session.get("cart", {})
    if not cart_session:
        flash("Your cart is empty. Cannot place order.", "warning")
        return redirect(url_for("frontend.view_cart"))

    form = CreateOrderForm() 
    # CRITICAL FIX: Populate choices for order_category_id BEFORE validation on POST
    order_categories = OrderCategory.query.order_by(OrderCategory.name).all()
    form.order_category_id.choices = [(oc.id, oc.name) for oc in order_categories]
    if not form.order_category_id.choices:
        form.order_category_id.choices = [] # Ensure choices is an empty list if no categories

    if form.validate_on_submit():
        try:
            total_amount = 0
            order_items_to_create = []
            insufficient_stock_items = []

            for product_id_str, quantity_in_cart in cart_session.items():
                product_id = int(product_id_str)
                product = Product.query.get(product_id)
                if not product:
                    flash(f"Product ID {product_id} not found. It may have been removed from the store.", "danger")
                    # Potentially remove from cart here and ask user to review
                    continue 

                inventory_item = Inventory.query.filter_by(product_id=product.id).first()
                if not inventory_item or inventory_item.quantity_on_hand < quantity_in_cart:
                    insufficient_stock_items.append(f"{product.name} (Ordered: {quantity_in_cart}, Available: {inventory_item.quantity_on_hand if inventory_item else 0})")
                    continue # Skip this item, will be reported to user
                
                order_items_to_create.append({
                    "product": product,
                    "quantity": quantity_in_cart,
                    "price_at_purchase": product.price
                })
                total_amount += product.price * quantity_in_cart
            
            if insufficient_stock_items:
                flash("Order not placed. Some items have insufficient stock: " + ", ".join(insufficient_stock_items) + ". Please adjust your cart.", "danger")
                return redirect(url_for("frontend.view_cart"))
            
            if not order_items_to_create:
                flash("No valid items to order after stock check. Your cart might be empty or all items were out of stock.", "warning")
                return redirect(url_for("frontend.view_cart"))

            # Create the order
            new_order = Order(
                user_id=current_user.id,
                total_amount=total_amount,
                status="Pending",
                shipping_address=form.shipping_address.data, # From form
                customer_name=form.customer_name.data or current_user.username, # From form or current user
                customer_email=form.customer_email.data or current_user.email # From form or current user
                # order_category_id = form.order_category_id.data # If you have categories for orders
            )
            db.session.add(new_order)
            db.session.flush() # Get the new_order.id before committing fully

            # Create order items and decrement stock
            for item_data in order_items_to_create:
                order_item_entry = OrderItem(
                    order_id=new_order.id,
                    product_id=item_data["product"].id,
                    quantity=item_data["quantity"],
                    price_at_purchase=item_data["price_at_purchase"]
                )
                db.session.add(order_item_entry)
                
                # Decrement stock
                inventory_item = Inventory.query.filter_by(product_id=item_data["product"].id).first()
                if inventory_item: # Should always exist if stock check passed
                    inventory_item.quantity_on_hand -= item_data["quantity"]
                    inventory_item.last_updated = datetime.utcnow()
            
            db.session.commit() # Commit order, items, and stock changes together
            session.pop("cart", None) # Clear cart after successful order
            flash("Order placed successfully!", "success")
            return redirect(url_for("frontend.view_order_detail", order_id=new_order.id))

        except IntegrityError as ie:
            db.session.rollback()
            current_app.logger.error(f"Integrity error placing order: {ie}", exc_info=True)
            flash("A database error occurred while placing the order. Please try again.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error placing order: {e}", exc_info=True)
            flash("An unexpected error occurred while placing the order. Please try again.", "danger")
        # If form validation failed or an error occurred, redirect back to cart to show messages
        return redirect(url_for("frontend.view_cart"))
    else:
        # Form validation failed
        flash("Please correct the errors in the checkout form.", "danger")
        # Re-render cart page with form errors. Need to pass cart details again.
        cart_items_details = []
        grand_total = 0
        cart_session = session.get("cart", {})
        remove_form = RemoveFromCartForm()
        for product_id_str, quantity_in_cart in list(cart_session.items()):
            product = Product.query.get(int(product_id_str))
            if product:
                inventory_item = Inventory.query.filter_by(product_id=product.id).first()
                available_stock = inventory_item.quantity_on_hand if inventory_item else 0
                actual_quantity = min(quantity_in_cart, available_stock)
                subtotal = product.price * actual_quantity
                cart_items_details.append({
                    "product_id": product.id, "name": product.name, "price": product.price,
                    "quantity": actual_quantity, "available_stock": available_stock, "subtotal": subtotal
                })
                grand_total += subtotal
        return render_template("order_form.html", title="Your Cart & Checkout", 
                               cart_items=cart_items_details, grand_total=grand_total, 
                               remove_form=remove_form, checkout_form=form) # Pass the invalid form back as 'checkout_form'

# --- User Profile Routes ---
@frontend_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    profile_form = UpdateProfileForm(obj=current_user)
    password_form = ChangePasswordForm()

    if profile_form.submit_profile.data and profile_form.validate():
        current_user.username = profile_form.username.data
        current_user.email = profile_form.email.data
        if profile_form.picture.data:
            try:
                # Pass current_app and current_user to save_profile_picture
                picture_file = save_profile_picture(profile_form.picture.data, current_app, current_user)
                current_user.image_file = picture_file # Corrected attribute name to image_file
            except Exception as e:
                flash(f"Error saving profile picture: {e}", "danger")
        try:
            db.session.commit()
            flash("Your profile has been updated!", "success")
            return redirect(url_for("frontend.profile"))
        except IntegrityError:
            db.session.rollback()
            flash("That username or email is already taken. Please choose a different one.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating profile: {e}")
            flash("An unexpected error occurred while updating your profile.", "danger")

    if password_form.submit_password.data and password_form.validate():
        if check_password_hash(current_user.password_hash, password_form.old_password.data):
            current_user.password_hash = generate_password_hash(password_form.new_password.data)
            try:
                db.session.commit()
                flash("Your password has been updated!", "success")
                return redirect(url_for("frontend.profile"))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error updating password: {e}")
                flash("An unexpected error occurred while updating your password.", "danger")
        else:
            flash("Incorrect old password.", "danger")

    image_file = url_for("static", filename="profile_pics/" + (current_user.image_file or "default.jpg"))
    return render_template("profile.html", title="Profile", 
                           profile_form=profile_form, password_form=password_form, image_file=image_file)


# --- Order Category Routes (Admin only) ---
@frontend_bp.route("/admin/order_categories", methods=["GET", "POST"])
@role_required("admin")
def manage_order_categories():
    form = OrderCategoryForm()
    if form.validate_on_submit():
        try:
            category = OrderCategory(name=form.name.data, description=form.description.data)
            db.session.add(category)
            db.session.commit()
            flash("Order category added successfully!", "success")
            return redirect(url_for("frontend.manage_order_categories"))
        except IntegrityError:
            db.session.rollback()
            flash("Order category name already exists.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding order category: {e}")
            flash("An error occurred while adding the order category.", "danger")
    
    categories = OrderCategory.query.order_by(OrderCategory.name).all()
    return render_template("order_categories.html", title="Manage Order Categories", form=form, categories=categories)

@frontend_bp.route("/admin/order_category/edit/<int:category_id>", methods=["GET", "POST"])
@role_required("admin")
def edit_order_category(category_id):
    category = OrderCategory.query.get_or_404(category_id)
    form = OrderCategoryForm(obj=category)
    if form.validate_on_submit():
        try:
            form.populate_obj(category)
            db.session.commit()
            flash("Order category updated successfully!", "success")
            return redirect(url_for("frontend.manage_order_categories"))
        except IntegrityError:
            db.session.rollback()
            flash("Another order category with this name already exists.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating order category: {e}")
            flash("An error occurred while updating the order category.", "danger")
    return render_template("order_category_form.html", title="Edit Order Category", form=form, legend=f"Edit Category: {category.name}")

@frontend_bp.route("/admin/order_category/delete/<int:category_id>", methods=["POST"])
@role_required("admin")
def delete_order_category(category_id):
    category = OrderCategory.query.get_or_404(category_id)
    # Check if category is in use by products or orders before deleting
    if Product.query.filter_by(category=category.name).first() or Order.query.filter_by(order_category_id=category.id).first():
        flash(f"Cannot delete category \'{category.name}\\' as it is currently in use by products or orders.", "danger")
        return redirect(url_for("frontend.manage_order_categories"))
    try:
        db.session.delete(category)
        db.session.commit()
        flash("Order category deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting order category: {e}")
        flash("An error occurred while deleting the order category.", "danger")
    return redirect(url_for("frontend.manage_order_categories"))


# Error Handlers
@frontend_bp.app_errorhandler(404)
def error_404(error):
    return render_template("errors/404.html", title="Page Not Found"), 404

# @frontend_bp.app_errorhandler(500) # This is handled by main.py\s app.errorhandler
# def error_500(error):
#     return render_template("errors/500.html", title="Server Error"), 500

@frontend_bp.app_errorhandler(403)
def error_403(error):
    return render_template("errors/403.html", title="Access Denied"), 403




@frontend_bp.route("/inventory/delete/<int:inventory_id>", methods=["POST"])
@role_required(["admin", "supplier"])
def delete_inventory_item(inventory_id):
    inventory_item = Inventory.query.get_or_404(inventory_id)
    product = Product.query.get_or_404(inventory_item.product_id) # For supplier check

    if current_user.is_supplier:
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if not supplier_profile or product.supplier_id != supplier_profile.id:
            flash("You do not have permission to delete this inventory item.", "danger")
            abort(403)
    elif not current_user.is_admin: # Double check for admin if not supplier
        flash("You do not have permission to delete this inventory item.", "danger")
        abort(403)

    try:
        db.session.delete(inventory_item)
        db.session.commit()
        flash(f"Inventory item for 	{product.name} deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting inventory item: {e}")
        flash("An error occurred while deleting the inventory item.", "danger")
    return redirect(url_for("frontend.view_inventory"))

