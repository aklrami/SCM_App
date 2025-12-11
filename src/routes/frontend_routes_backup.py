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
    if current_user.is_admin:
        stats["total_users"] = User.query.count()
        stats["total_products"] = Product.query.count()
        stats["pending_orders"] = Order.query.filter_by(status="Pending").count()
    elif current_user.is_supplier:
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if supplier_profile:
            stats["supplier_products"] = Product.query.filter_by(supplier_id=supplier_profile.id).count()
            stats["supplier_orders"] = Order.query.join(OrderItem).join(Product).filter(Product.supplier_id == supplier_profile.id).distinct().count()
        else:
            stats["supplier_products"] = 0
            stats["supplier_orders"] = 0
    elif current_user.is_general_user: # Changed from is_user
        stats["user_orders"] = Order.query.filter_by(user_id=current_user.id).count()

    chart_data = None
    if current_user.is_admin:
        order_trend_labels = [(datetime.utcnow() - timedelta(days=i)).strftime("%b %d") for i in range(6, -1, -1)]
        order_trend_data = [Order.query.filter(db.func.date(Order.order_date) == (datetime.utcnow() - timedelta(days=i)).date()).count() for i in range(6, -1, -1)]
        
        category_data = db.session.query(Product.category, db.func.count(Product.id)).group_by(Product.category).all()
        category_labels = [c[0] if c[0] else "Uncategorized" for c in category_data]
        category_counts = [c[1] for c in category_data]

        chart_data = {
            "order_trend": {"labels": order_trend_labels, "data": order_trend_data},
            "category_distribution": {"labels": category_labels, "data": category_counts}
        }

    return render_template("dashboard.html", title="Dashboard", stats=stats, chart_data=chart_data)


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
        if Product.query.filter_by(supplier_id=supplier.id).first():
             flash(f"Cannot delete supplier \'{supplier.name}\'. It is associated with products. Reassign or delete products first.", "danger")
             return redirect(url_for("frontend.view_suppliers"))
        
        db.session.delete(supplier)
        db.session.commit()
        flash("Supplier profile deleted successfully!", "success")
        if current_user.is_admin:
            return redirect(url_for("frontend.view_suppliers"))
        else: 
            return redirect(url_for("frontend.view_dashboard")) 
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
    
    if current_user.is_general_user: # Changed from is_user
        flash("Access denied. Please browse products in the shop.", "info")
        return redirect(url_for("frontend.shop_products"))

    page = request.args.get("page", 1, type=int)
    search_term = request.args.get("search", "")
    query = Product.query
    if current_user.is_supplier:
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if supplier_profile:
            query = query.filter(Product.supplier_id == supplier_profile.id)
        else:
            query = query.filter(False) 
            flash("You need to set up your supplier profile to view or manage your products.", "info")
    
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
        if request.method == "GET": 
            form.supplier_id.data = supplier_profile.id 

    if form.validate_on_submit():
        try:
            if current_user.is_supplier:
                supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
                if not supplier_profile or form.supplier_id.data != supplier_profile.id:
                    flash("Invalid supplier ID for your role.", "danger")
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
            
            if new_category_created_this_request: # Commit here if new category was added
                db.session.commit()
            else: # Otherwise, commit only the product (or product + existing category link)
                db.session.commit()

            flash("Product added successfully!", "success")
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
    
    # Repopulate choices if form validation fails or it's a GET request
    if request.method == "GET" or (form.is_submitted() and not form.validate()):
        form.product_category_id.choices = [(oc.id, oc.name) for oc in OrderCategory.query.order_by(OrderCategory.name).all()]
        form.product_category_id.choices.insert(0, (0, "Select a category or add new below"))
        if current_user.is_admin:
            form.supplier_id.choices = [(s.id, s.name) for s in Supplier.query.order_by(Supplier.name).all()]
        elif current_user.is_supplier:
            supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
            if supplier_profile:
                form.supplier_id.choices = [(supplier_profile.id, supplier_profile.name)]
                form.supplier_id.data = supplier_profile.id 
            else: 
                form.supplier_id.choices = []

    return render_template("product_form.html", title="Add Product", form=form, legend="New Product")

@frontend_bp.route("/product/edit/<int:product_id>", methods=["GET", "POST"])
@login_required 
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
    form.product_category_id.choices = [(oc.id, oc.name) for oc in OrderCategory.query.order_by(OrderCategory.name).all()]
    form.product_category_id.choices.insert(0, (0, "Select a category or add new below"))
    if current_user.is_admin:
        form.supplier_id.choices = [(s.id, s.name) for s in Supplier.query.order_by(Supplier.name).all()]
    elif current_user.is_supplier:
        supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
        if supplier_profile:
            form.supplier_id.choices = [(supplier_profile.id, supplier_profile.name)]
            form.supplier_id.render_kw = {"disabled": True} 
        else: 
            flash("Supplier profile not found. Cannot edit product.", "danger")
            return redirect(url_for("frontend.view_products"))

    if request.method == "GET":
        form.supplier_id.data = product.supplier_id
        if product.category: # New way: product.category is a string name
            category_obj = OrderCategory.query.filter_by(name=product.category).first()
            if category_obj:
                form.product_category_id.data = category_obj.id
            else:
                flash(f"Product has category \'{product.category}\' not in the OrderCategory table. You can create it or select another.", "warning")
                form.new_category_name.data = product.category 

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
            
            product.name = form.name.data
            product.sku = form.sku.data
            product.description = form.description.data
            product.category = category_to_assign.name if category_to_assign else None # New way
            product.price = form.price.data
            if current_user.is_admin: 
                product.supplier_id = form.supplier_id.data
            
            if new_category_created_this_request:
                db.session.commit() # Commit category first if new
            db.session.commit() # Commit product changes
            flash("Product updated successfully!", "success")
            return redirect(url_for("frontend.view_products"))
        except IntegrityError as ie:
            db.session.rollback()
            current_app.logger.error(f"Integrity error updating product: {ie}")
            flash("Product SKU or name may already exist for another product, or other database error.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating product: {e}", exc_info=True)
            flash(f"An error occurred while updating the product: {str(e)}", "danger")

    # Repopulate choices if form validation fails or it's a GET request and not yet populated
    if (form.is_submitted() and not form.validate()) or (request.method == "GET" and not form.product_category_id.choices):
        form.product_category_id.choices = [(oc.id, oc.name) for oc in OrderCategory.query.order_by(OrderCategory.name).all()]
        form.product_category_id.choices.insert(0, (0, "Select a category or add new below"))
        if current_user.is_admin:
            form.supplier_id.choices = [(s.id, s.name) for s in Supplier.query.order_by(Supplier.name).all()]
        elif current_user.is_supplier:
            supplier_profile = Supplier.query.filter_by(user_id=current_user.id).first()
            if supplier_profile:
                form.supplier_id.choices = [(supplier_profile.id, supplier_profile.name)]

    return render_template("product_form.html", title=f"Edit Product: {product.name}", form=form, legend=f"Edit Product: {product.name}")

@frontend_bp.route("/product/delete/<int:product_id>", methods=["POST"])
@login_required 
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
        if Inventory.query.filter_by(product_id=product.id).first():
            flash(f"Cannot delete product \'{product.name}\'. It is in inventory. Please remove from inventory first.", "danger")
            return redirect(url_for("frontend.view_products"))
        if OrderItem.query.filter_by(product_id=product.id).first():
            flash(f"Cannot delete product \'{product.name}\'. It is part of an order. Please remove from orders first.", "danger")
            return redirect(url_for("frontend.view_products"))
            
        db.session.delete(product)
        db.session.commit()
        flash("Product deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting product: {e}")
        flash("An error occurred while deleting the product.", "danger")
    return redirect(url_for("frontend.view_products"))

# --- Inventory Routes ---
@frontend_bp.route("/inventory")
@login_required 
def view_inventory():
    if not current_user.is_active:
        flash("Your account is not active. Please contact an administrator.", "warning")
        logout_user()
        return redirect(url_for("frontend.login"))
    
    # Restrict access for suppliers
    if current_user.is_supplier:
        flash("You do not have permission to access the Inventory page.", "danger")
        return redirect(url_for("frontend.view_dashboard"))

    page = request.args.get("page", 1, type=int)
    search_term = request.args.get("search", "")
    low_stock_filter = request.args.get("low_stock") == "on"

    query = Inventory.query.join(Product) 

    if search_term:
        query = query.filter(or_(Product.name.ilike(f"%{search_term}%"), Product.sku.ilike(f"%{search_term}%")))
    
    if low_stock_filter:
        # Ensure reorder_level is not None before comparing
        query = query.filter(Inventory.reorder_level != None, Inventory.quantity_on_hand <= Inventory.reorder_level)

    inventory_items_pagination = query.order_by(Product.name).paginate(page=page, per_page=10)
    
    return render_template("inventory.html", 
                           title="Inventory Management", 
                           inventory_items_pagination=inventory_items_pagination, 
                           search_term=search_term,
                           low_stock_filter=low_stock_filter)

@frontend_bp.route("/inventory/add", methods=["GET", "POST"])
@role_required(["admin"]) # Only admin can add inventory items directly now
def add_inventory_item():
    form = AddInventoryItemForm()
    product_choices = [(p.id, f"{p.name} (SKU: {p.sku})") for p in Product.query.order_by(Product.name).all()]
    
    form.product_id.choices = product_choices
    if not product_choices and request.method == "GET":
        flash("No products available to add to inventory. Please add products first.", "info")

    if form.validate_on_submit():
        try:
            existing_item = Inventory.query.filter_by(product_id=form.product_id.data).first()
            if existing_item:
                flash("Inventory item for this product already exists. You can adjust stock instead.", "warning")
                return redirect(url_for("frontend.adjust_stock", inventory_item_id=existing_item.id))

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
            flash("Error: Could not add inventory item. Product might not exist or other integrity constraint failed.", "danger")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding inventory item: {e}")
            flash("An error occurred while adding the inventory item.", "danger")
    return render_template("inventory_form.html", title="Add Inventory Item", form=form, legend="New Inventory Item")

@frontend_bp.route("/inventory/adjust/<int:inventory_item_id>", methods=["GET", "POST"])
@role_required(["admin"]) # Only admin can adjust stock directly now
def adjust_stock(inventory_item_id):
    inventory_item = Inventory.query.get_or_404(inventory_item_id)
    product = Product.query.get_or_404(inventory_item.product_id)
            
    form = AdjustStockForm(obj=inventory_item)
    if form.validate_on_submit():
        try:
            inventory_item.quantity_on_hand = form.quantity_on_hand.data
            inventory_item.reorder_level = form.reorder_level.data
            inventory_item.location = form.location.data
            inventory_item.last_updated = datetime.utcnow()
            db.session.commit()
            flash(f"Stock for {product.name} updated successfully!", "success")
            return redirect(url_for("frontend.view_inventory"))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adjusting stock: {e}", exc_info=True)
            flash("An error occurred while adjusting stock. Please try again.", "danger") 
    return render_template("inventory_form.html", title=f"Adjust Stock: {product.name}", form=form, legend=f"Adjust Stock for {product.name} (SKU: {product.sku})")

@frontend_bp.route("/inventory/delete/<int:inventory_item_id>", methods=["POST"])
@role_required(["admin"]) # Only admin can delete inventory items directly now
def delete_inventory_item(inventory_item_id):
    inventory_item = Inventory.query.get_or_404(inventory_item_id)
    product = Product.query.get_or_404(inventory_item.product_id)

    try:
        db.session.delete(inventory_item)
        db.session.commit()
        flash(f"Inventory item for {product.name} deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting inventory item: {e}")
        flash("An error occurred while deleting the inventory item.", "danger")
    return redirect(url_for("frontend.view_inventory"))

# --- Order Routes ---
@frontend_bp.route("/orders")
@login_required 
def view_orders():
    if not current_user.is_active:
        flash("Your account is not active. Please contact an administrator.", "warning")
        logout_user()
        return redirect(url_for("frontend.login"))

    # Restrict access for suppliers
    if current_user.is_supplier:
        flash("You do not have permission to access the Orders page.", "danger")
        return redirect(url_for("frontend.view_dashboard"))

    page = request.args.get("page", 1, type=int)
    search_term = request.args.get("search", "")
    status_filter = request.args.get("status", "")
    query = Order.query

    if current_user.is_general_user: # Changed from is_user
        query = query.filter(Order.user_id == current_user.id)

    if search_term: 
        if search_term.isdigit():
            query = query.filter(Order.id == int(search_term))
        elif current_user.is_admin: # Only admin can search by username for orders
            query = query.join(User).filter(User.username.ilike(f"%{search_term}%"))

    if status_filter:
        query = query.filter(Order.status.ilike(f"%{status_filter}%"))

    orders_pagination = query.order_by(Order.order_date.desc()).paginate(page=page, per_page=10)
    distinct_statuses = [s[0] for s in db.session.query(Order.status).distinct().order_by(Order.status).all() if s[0]]

    return render_template("orders.html", 
                           title="Orders", 
                           orders_pagination=orders_pagination,
                           search_term=search_term,
                           status_filter=status_filter,
                           distinct_statuses=distinct_statuses)

@frontend_bp.route("/order/detail/<int:order_id>")
@login_required 
def view_order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    allowed_to_view = False
    if current_user.is_admin or order.user_id == current_user.id:
        allowed_to_view = True
            
    if not allowed_to_view:
        flash("You do not have permission to view this order.", "danger")
        abort(403)
            
    update_status_form = None
    if current_user.is_admin: # Only admin can update status from here
        update_status_form = UpdateOrderStatusForm(status=order.status)
        
    return render_template("order_detail.html", title=f"Order #{order.id}", order=order, update_status_form=update_status_form)

@frontend_bp.route("/order/update_status/<int:order_id>", methods=["POST"])
@role_required(["admin"]) # Only admin can update order status
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    form = UpdateOrderStatusForm()

    if form.validate_on_submit():
        try:
            order.status = form.status.data
            order.last_updated = datetime.utcnow()
            db.session.commit()
            flash(f"Order #{order.id} status updated to {order.status}.", "success")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating order status: {e}")
            flash("An error occurred while updating order status.", "danger")
    else:
        flash("Invalid status selected.", "danger")
    return redirect(url_for("frontend.view_order_detail", order_id=order.id))

# --- Cart and Shop Routes ---
@frontend_bp.route("/shop")
@login_required 
def shop_products():
    page = request.args.get("page", 1, type=int)
    search_term = request.args.get("search", "")
    query = Product.query 
    if search_term:
        query = query.filter(Product.name.ilike(f"%{search_term}%"))
    products_pagination = query.order_by(Product.name).paginate(page=page, per_page=9) 
    return render_template("shop_products.html", title="Shop Products", products_pagination=products_pagination, search_term=search_term)

@frontend_bp.route("/cart/add/<int:product_id>", methods=["POST"])
@login_required
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    quantity = request.form.get("quantity", 1, type=int)
    if quantity < 1:
        quantity = 1
    
    cart = session.get("cart", {})
    current_quantity = cart.get(str(product_id), 0)
    cart[str(product_id)] = current_quantity + quantity
    session["cart"] = cart
    flash(f"{quantity} x {product.name} added to your cart.", "success")
    return redirect(url_for("frontend.view_cart"))

@frontend_bp.route("/cart")
@login_required
def view_cart():
    cart_items_details = []
    grand_total = 0
    cart_session = session.get("cart", {})
    remove_form = RemoveFromCartForm() 

    for product_id_str, quantity in list(cart_session.items()): # Use list() for safe iteration if modifying dict
        product = Product.query.get(int(product_id_str))
        if product:
            subtotal = product.price * quantity
            cart_items_details.append({
                "product_id": product.id,
                "name": product.name,
                "price": product.price,
                "quantity": quantity,
                "subtotal": subtotal
            })
            grand_total += subtotal
        else: 
            session["cart"].pop(product_id_str, None)
            session.modified = True 
            flash(f"A product previously in your cart is no longer available and has been removed.", "warning")

    return render_template("order_form.html", title="Your Cart & Checkout", 
                           cart_items=cart_items_details, grand_total=grand_total, 
                           remove_form=remove_form)

@frontend_bp.route("/cart/remove/<int:product_id>", methods=["POST"])
@login_required
def remove_from_cart(product_id):
    form = RemoveFromCartForm() 
    if form.validate_on_submit():
        cart = session.get("cart", {})
        if str(product_id) in cart:
            product = Product.query.get(product_id) 
            del cart[str(product_id)]
            session["cart"] = cart
            flash(f"{product.name if product else 'Item'} removed from cart.", "info")
        else:
            flash("Item not found in cart.", "warning")
    else:
        flash("Could not remove item due to a form error.", "danger")
    return redirect(url_for("frontend.view_cart"))

@frontend_bp.route("/cart/clear", methods=["POST"])
@login_required
def clear_cart():
    session.pop("cart", None)
    flash("Cart cleared.", "info")
    return redirect(url_for("frontend.view_cart"))

@frontend_bp.route("/order/place", methods=["POST"])
@login_required
def place_order():
    cart_session = session.get("cart", {})
    if not cart_session:
        flash("Your cart is empty. Cannot place order.", "warning")
        return redirect(url_for("frontend.view_cart"))

    try:
        total_amount = 0
        order_items_to_create = []
        insufficient_stock_items = []

        for product_id_str, quantity_in_cart in cart_session.items():
            product_id = int(product_id_str)
            product = Product.query.get(product_id)
            if not product:
                flash(f"Product ID {product_id} not found. It may have been removed.", "danger")
                continue 

            inventory_item = Inventory.query.filter_by(product_id=product.id).first()
            if not inventory_item or inventory_item.quantity_on_hand < quantity_in_cart:
                insufficient_stock_items.append(f"{product.name} (Ordered: {quantity_in_cart}, Available: {inventory_item.quantity_on_hand if inventory_item else 0})")
                continue
            
            order_items_to_create.append({
                "product": product,
                "quantity": quantity_in_cart,
                "price_at_purchase": product.price
            })
            total_amount += product.price * quantity_in_cart
        
        if insufficient_stock_items:
            flash("Order not placed due to insufficient stock for: " + ", ".join(insufficient_stock_items), "danger")
            return redirect(url_for("frontend.view_cart"))
        
        if not order_items_to_create:
            flash("No valid items to order after stock check.", "warning")
            return redirect(url_for("frontend.view_cart"))

        new_order = Order(
            user_id=current_user.id,
            total_amount=total_amount,
            status="Pending",
        )
        db.session.add(new_order)
        db.session.flush() 

        for item_data in order_items_to_create:
            order_item_entry = OrderItem(
                order_id=new_order.id,
                product_id=item_data["product"].id,
                quantity=item_data["quantity"],
                price_at_purchase=item_data["price_at_purchase"]
            )
            db.session.add(order_item_entry)
            
            inventory_item = Inventory.query.filter_by(product_id=item_data["product"].id).first()
            if inventory_item: # Should always exist if stock check passed
                inventory_item.quantity_on_hand -= item_data["quantity"]
                inventory_item.last_updated = datetime.utcnow()
        
        db.session.commit()
        session.pop("cart", None) 
        flash("Order placed successfully!", "success")
        return redirect(url_for("frontend.view_order_detail", order_id=new_order.id))

    except IntegrityError as ie:
        db.session.rollback()
        current_app.logger.error(f"Integrity error placing order: {ie}", exc_info=True)
        flash("A database error occurred. Please try again.", "danger")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error placing order: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
    return redirect(url_for("frontend.view_cart"))

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
            flash("Username or email already taken.", "danger")
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {e}", "danger")

    if password_form.submit_password.data and password_form.validate():
        if check_password_hash(current_user.password_hash, password_form.current_password.data):
            current_user.password_hash = generate_password_hash(password_form.new_password.data)
            try:
                db.session.commit()
                flash("Your password has been updated!", "success")
                return redirect(url_for("frontend.profile"))
            except Exception as e:
                db.session.rollback()
                flash(f"An error occurred updating password: {e}", "danger")
        else:
            flash("Incorrect current password.", "danger")
            
    profile_image_url = url_for("static", filename="profile_pics/" + current_user.image_file) if current_user.image_file else url_for("static", filename="profile_pics/default.jpg") # Corrected attribute name to image_file
    return render_template("profile.html", title="Profile", 
                           profile_form=profile_form, password_form=password_form, 
                           profile_image_url=profile_image_url)


# Error Handlers
@frontend_bp.app_errorhandler(404)
def handle_404(err):
    return render_template("errors/404.html"), 404

@frontend_bp.app_errorhandler(403)
def handle_403(err):
    return render_template("errors/403.html"), 403

@frontend_bp.app_errorhandler(500)
def handle_500(err):
    current_app.logger.error(f"Server error: {err}", exc_info=True)
    # db.session.rollback() # Optional: rollback session on 500 errors
    return render_template("errors/500.html"), 500

# Context Processors
@frontend_bp.context_processor
def inject_current_year():
    return dict(current_year=datetime.utcnow().year)

@frontend_bp.context_processor
def utility_processor():
    def get_supplier_profile_for_current_user():
        if current_user.is_authenticated and current_user.is_supplier:
            return Supplier.query.filter_by(user_id=current_user.id).first()
        return None
    return dict(get_supplier_profile_for_current_user=get_supplier_profile_for_current_user)


