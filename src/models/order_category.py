#!/usr/bin/env python
# coding: utf-8

from src.main import db # Assuming db is initialized in main

class OrderCategory(db.Model):
    __tablename__ = 'order_category'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Relationship to Orders
    # This will add an 'orders' attribute to OrderCategory instances
    # and a 'category' attribute to Order instances (due to backref)
    orders = db.relationship('Order', backref='category', lazy='dynamic')

    def __repr__(self):
        return f'<OrderCategory {self.id}: {self.name}>'

