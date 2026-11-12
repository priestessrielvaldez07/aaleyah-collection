from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False) # <-- CHANGED TO 255

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    cost_price = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, default=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    customer_name = db.Column(db.String(150), nullable=True)
    total_cost = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, default=0.0)
    scoop_paid = db.Column(db.Float, nullable=True)
    earnings = db.Column(db.Float, default=0.0)
    items = db.relationship('OrderItem', backref='order', cascade="all, delete-orphan")

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    item_id = db.Column(db.Integer, nullable=False)
    item_name = db.Column(db.String(150), nullable=False)
    cost_price_snapshot = db.Column(db.Float, nullable=False)
    selling_price_snapshot = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)