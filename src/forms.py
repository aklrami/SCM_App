from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SubmitField, TextAreaField, EmailField, FloatField, IntegerField, SelectField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange, EqualTo

class SupplierForm(FlaskForm):
    name = StringField("Supplier Name", validators=[DataRequired(), Length(min=2, max=100)])
    contact_person = StringField("Contact Person", validators=[Optional(), Length(max=100)])
    email = EmailField("Supplier Business Email", validators=[DataRequired(), Email(), Length(max=120)]) 
    phone = StringField("Phone", validators=[Optional(), Length(max=20)])
    address = TextAreaField("Address", validators=[Optional(), Length(max=200)])
    submit = SubmitField("Save Supplier")

class ProductForm(FlaskForm):
    name = StringField("Product Name", validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField("Description", validators=[Optional()])
    sku = StringField("SKU", validators=[DataRequired(), Length(min=1, max=50)])
    product_category_id = SelectField("Product Category", coerce=int, validators=[Optional()]) # Made optional to allow new category creation
    new_category_name = StringField("New Category Name", validators=[Optional(), Length(min=2, max=100)])
    new_category_description = TextAreaField("New Category Description", validators=[Optional()])
    price = FloatField("Price", validators=[DataRequired(), NumberRange(min=0)])
    supplier_id = SelectField("Supplier", coerce=int, validators=[DataRequired()]) 
    submit = SubmitField("Save Product")

class RegistrationForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=2, max=20)])
    email = EmailField("Login Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password", message="Passwords must match.")])
    role = SelectField("Register as", choices=[
        ("user", "User (View Inventory, Place Orders)"),
        ("supplier", "Supplier (Manage Own Products & Supplier Profile)")
    ], validators=[DataRequired()], default="user")
    submit = SubmitField("Sign Up")

class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember Me")
    submit = SubmitField("Login")

class AddInventoryItemForm(FlaskForm):
    product_id = SelectField("Product", coerce=int, validators=[DataRequired()])
    quantity_on_hand = IntegerField("Quantity on Hand", validators=[DataRequired(), NumberRange(min=0)], default=0)
    reorder_level = IntegerField("Reorder Level", validators=[DataRequired(), NumberRange(min=0)], default=10) # Changed from low_stock_threshold for consistency
    location = StringField("Location", validators=[Optional(), Length(max=100)]) # Added location
    submit = SubmitField("Add Inventory Item")

class AdjustStockForm(FlaskForm):
    adjustment_type = SelectField("Adjustment Type", choices=[("increase", "Increase Stock"), ("decrease", "Decrease Stock")], validators=[DataRequired()])
    adjustment = IntegerField("Adjustment Quantity", validators=[DataRequired(), NumberRange(min=1)]) # Renamed from quantity_on_hand for clarity, and ensure it's a positive number for adjustment
    # quantity_on_hand = IntegerField("New Quantity on Hand", validators=[DataRequired(), NumberRange(min=0)]) # This field seems to be for direct edit, not adjustment. The route logic uses 'adjustment'
    # reorder_level = IntegerField("Reorder Level", validators=[DataRequired(), NumberRange(min=0)]) # Reorder level and location are usually part of general inventory edit, not stock adjustment action
    # location = StringField("Location", validators=[Optional(), Length(max=100)])
    submit = SubmitField("Adjust Stock")

class OrderItemForm(FlaskForm):
    product_id = SelectField("Product", coerce=int, validators=[DataRequired()])
    quantity = IntegerField("Quantity", validators=[DataRequired(), NumberRange(min=1)], default=1)

class CreateOrderForm(FlaskForm):
    customer_name = StringField("Customer Name", validators=[Optional(), Length(max=100)])
    customer_email = EmailField("Customer Email", validators=[Optional(), Email(), Length(max=120)])
    shipping_address = TextAreaField("Shipping Address", validators=[DataRequired(), Length(max=200)])
    order_category_id = SelectField("Order Category", coerce=int, validators=[Optional()])
    submit = SubmitField("Place Order")

class UpdateOrderStatusForm(FlaskForm):
    status = SelectField("Order Status", validators=[DataRequired()], 
                         choices=[
                             ("Pending", "Pending"), 
                             ("Processing", "Processing"), 
                             ("Shipped", "Shipped"), 
                             ("Delivered", "Delivered"), 
                             ("Cancelled", "Cancelled")
                         ])
    submit = SubmitField("Update Status")

class UpdateProfileForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=2, max=20)])
    email = EmailField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    picture = FileField("Update Profile Picture", validators=[FileAllowed(["jpg", "png", "jpeg"])])
    submit_profile = SubmitField("Update Profile")

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current Password", validators=[DataRequired()])
    new_password = PasswordField("New Password", validators=[DataRequired(), Length(min=6)])
    confirm_new_password = PasswordField("Confirm New Password", validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")])
    submit_password = SubmitField("Change Password")

class RemoveFromCartForm(FlaskForm):
    submit = SubmitField("Remove")

class OrderCategoryForm(FlaskForm):
    name = StringField("Category Name", validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField("Description", validators=[Optional()])
    submit = SubmitField("Save Category")

