# /home/ubuntu/supply_chain_frontend/src/seed.py
import sys
import os

# Ensure the src directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.main import create_app
from src.extensions import db
from src.models.supplier import Supplier
from src.models.product import Product
from src.models.inventory import Inventory
from src.models.purchase_order import PurchaseOrder
from datetime import datetime

def seed_database():
    app = create_app()
    with app.app_context():
        print("Checking if database needs seeding...")

        # Check if data already exists (e.g., check if suppliers exist)
        if Supplier.query.first() is not None:
            print("Database already contains data. Skipping seeding.")
            return

        print("Seeding database with initial data...")

        # Create Suppliers
        supplier1 = Supplier(name="Global Components Inc.", contact_details="sales@globalcomponents.com", service_category="Electronics", performance_metrics=92.5)
        supplier2 = Supplier(name="MetalWorks Ltd.", contact_details="info@metalworks.com", service_category="Raw Materials", performance_metrics=88.0)
        supplier3 = Supplier(name="FastShip Logistics", contact_details="ops@fastship.log", service_category="Logistics", performance_metrics=95.0)

        db.session.add_all([supplier1, supplier2, supplier3])
        db.session.flush() # Flush to get IDs for relationships

        # Create Products
        product1 = Product(sku="CPU-INT-i7", name="Intel i7 Processor", description="High-end CPU", price=350.00, reorder_point=20)
        product2 = Product(sku="RAM-DDR4-16G", name="16GB DDR4 RAM", description="Standard RAM module", price=75.50, reorder_point=50)
        product3 = Product(sku="SSD-NVME-1TB", name="1TB NVMe SSD", description="Fast solid state drive", price=120.00, reorder_point=30)
        product4 = Product(sku="ALU-SHEET-1MM", name="Aluminum Sheet 1mm", description="Standard aluminum sheet", price=25.00, reorder_point=100)

        db.session.add_all([product1, product2, product3, product4])
        db.session.flush() # Flush to get IDs

        # Create Inventory Items
        inventory1 = Inventory(product_id=product1.id, available_quantity=50, reserved_quantity=5)
        inventory2 = Inventory(product_id=product2.id, available_quantity=150, reserved_quantity=20)
        inventory3 = Inventory(product_id=product3.id, available_quantity=25, reserved_quantity=0) # Low stock example
        inventory4 = Inventory(product_id=product4.id, available_quantity=300, reserved_quantity=50)

        db.session.add_all([inventory1, inventory2, inventory3, inventory4])

        # Create Purchase Orders
        order1 = PurchaseOrder(supplier_id=supplier1.id, product_id=product1.id, quantity=10, status="Submitted", created_at=datetime(2025, 4, 15))
        order2 = PurchaseOrder(supplier_id=supplier2.id, product_id=product4.id, quantity=200, status="Shipped", created_at=datetime(2025, 4, 20), expected_delivery=datetime(2025, 5, 10))
        order3 = PurchaseOrder(supplier_id=supplier1.id, product_id=product2.id, quantity=50, status="Delivered", created_at=datetime(2025, 4, 1), delivered_at=datetime(2025, 4, 25))

        db.session.add_all([order1, order2, order3])

        try:
            db.session.commit()
            print("Database seeded successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error seeding database: {e}")

if __name__ == "__main__":
    seed_database()
