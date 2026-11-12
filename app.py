import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User, Inventory, Order, OrderItem
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
# Using a fallback to sqlite if DATABASE_URL is not set, to prevent crashes
app.config['SECRET_KEY'] = 'super_secret_aaleyah_key_12345'
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///aaleyah_local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin')
        admin.set_password('aaleyah2026')
        db.session.add(admin)
        db.session.commit()

# --- ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    # Get low stock items (20 or less) that are still active
    low_stock_items = Inventory.query.filter(
        Inventory.stock <= 20, 
        Inventory.is_active == True
    ).order_by(Inventory.stock.asc()).all()
    
    # Get discontinued items
    discontinued_items = Inventory.query.filter_by(is_active=False).all()
    
    return render_template(
        'dashboard.html', 
        low_stock_items=low_stock_items,
        discontinued_items=discontinued_items
    )

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_pwd = request.form.get('current_password')
        new_pwd = request.form.get('new_password')
        confirm_pwd = request.form.get('confirm_password')
        
        if not current_user.check_password(current_pwd):
            flash('Current password is incorrect.', 'danger')
        elif new_pwd != confirm_pwd:
            flash('New passwords do not match.', 'danger')
        elif not new_pwd:
            flash('New password cannot be empty.', 'danger')
        else:
            current_user.set_password(new_pwd)
            db.session.commit()
            flash('Password updated successfully! Please log in again.', 'success')
            return redirect(url_for('logout'))
            
    return render_template('profile.html')

@app.route('/inventory', methods=['GET', 'POST'])
@login_required
def inventory_screen():
    if request.method == 'POST':
        edit_id = request.form.get('edit_id')
        name = request.form.get('name')
        cost = float(request.form.get('cost_price'))
        price = float(request.form.get('selling_price'))
        stock = int(request.form.get('stock'))
        
        if edit_id:
            item = db.session.get(Inventory, int(edit_id))
            item.name = name
            item.cost_price = cost
            item.selling_price = price
            item.stock = stock
        else:
            new_item = Inventory(name=name, cost_price=cost, selling_price=price, stock=stock)
            db.session.add(new_item)
        
        db.session.commit()
        return redirect(url_for('inventory_screen'))
        
    items = Inventory.query.all()
    low_stock_items = Inventory.query.filter(Inventory.stock <= 20, Inventory.is_active == True).order_by(Inventory.stock.asc()).all()
    return render_template('inventory.html', items=items, low_stock_items=low_stock_items)

@app.route('/toggle_item/<int:item_id>')
@login_required
def toggle_item(item_id):
    item = db.session.get(Inventory, item_id)
    if item:
        item.is_active = not item.is_active
        db.session.commit()
        if item.is_active:
            flash(f'{item.name} is now ACTIVE.', 'success')
        else:
            flash(f'{item.name} is now DISCONTINUED.', 'warning')
    return redirect(url_for('inventory_screen'))

@app.route('/pos', methods=['GET', 'POST'])
@login_required
def pos_screen():
    if request.method == 'POST':
        cart_data = json.loads(request.form.get('cart_data'))
        scoop_paid_str = request.form.get('scoop_paid')
        scoop_paid = float(scoop_paid_str) if scoop_paid_str else None
        
        total_cost = 0
        total_price = 0
        
        new_order = Order(scoop_paid=scoop_paid)
        db.session.add(new_order)
        db.session.flush()
        
        for c_item in cart_data:
            inv_item = db.session.get(Inventory, int(c_item['id']))
            qty = c_item['qty']
            
            # 1. Deduct Inventory
            inv_item.stock -= qty
            
            # 2. Calculate totals
            item_cost_total = inv_item.cost_price * qty
            item_price_total = inv_item.selling_price * qty
            total_cost += item_cost_total
            total_price += item_price_total
            
            # 3. Create the locked snapshot
            order_item = OrderItem(
                order_id=new_order.id,
                item_id=inv_item.id,
                item_name=inv_item.name,
                cost_price_snapshot=inv_item.cost_price,
                selling_price_snapshot=inv_item.selling_price,
                quantity=qty
            )
            db.session.add(order_item)
            
        # 4. Save financials to the Order
        new_order.total_cost = total_cost
        new_order.total_price = total_price
        
        if scoop_paid is not None:
            new_order.earnings = scoop_paid - total_cost
        else:
            new_order.earnings = 0.0
            
        db.session.commit()
        
        # Check if any items dropped to 20 or below and flash a warning
        low_stock_after_sale = Inventory.query.filter(Inventory.stock <= 20, Inventory.stock > 0, Inventory.is_active == True).all()
        if low_stock_after_sale:
            item_names = ", ".join([f"{item.name} ({item.stock} left)" for item in low_stock_after_sale])
            flash(f'Low Stock Warning: {item_names}', 'warning')
            
        flash('Order saved successfully!', 'success')
        return redirect(url_for('pos_screen'))
        
    # GET REQUEST: Prepare inventory for JavaScript (ONLY ACTIVE ITEMS)
    items = Inventory.query.filter_by(is_active=True).all()
    inventory_dict = {str(item.id): {"name": item.name, "cost": item.cost_price, "price": item.selling_price, "stock": item.stock} for item in items}
    inventory_json = json.dumps(inventory_dict)
    return render_template('pos.html', inventory_json=inventory_json)

# --- ORDER HISTORY & PRINTING ---
@app.route('/history')
@login_required
def history():
    orders = Order.query.order_by(Order.date_created.desc()).all()
    return render_template('history.html', orders=orders)

@app.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('history'))
    return render_template('order_detail.html', order=order)

@app.route('/delete_order/<int:order_id>', methods=['POST'])
@login_required
def delete_order(order_id):
    # SECURITY CHECK: Verify password before deleting
    password = request.form.get('password')
    if not current_user.check_password(password):
        flash('Incorrect password. Deletion cancelled for security.', 'danger')
        return redirect(url_for('history'))
    
    order = db.session.get(Order, order_id)
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('history'))
        
    # Restore inventory before deleting
    for item in order.items:
        inv_item = db.session.get(Inventory, item.item_id)
        if inv_item:
            inv_item.stock += item.quantity
            
    db.session.delete(order)
    db.session.commit()
    flash('Order deleted and stock restored.', 'warning')
    return redirect(url_for('history'))

# --- FINANCIAL REPORTS ---
@app.route('/reports', methods=['GET', 'POST'])
@login_required
def reports():
    stats = None
    if request.method == 'POST':
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        
        orders = Order.query.filter(Order.date_created.between(start_date, end_date)).all()
        
        total_orders = len(orders)
        total_revenue = sum(o.scoop_paid for o in orders if o.scoop_paid is not None)
        total_cost = sum(o.total_cost for o in orders)
        net_profit = total_revenue - total_cost
        total_loss = abs(net_profit) if net_profit < 0 else 0
        
        total_items_sold = sum(item.quantity for o in orders for item in o.items)
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
        
        stats = {
            'start': start_date_str, 'end': end_date_str,
            'total_orders': total_orders, 'total_items_sold': total_items_sold,
            'total_revenue': total_revenue, 'total_cost': total_cost,
            'net_profit': net_profit, 'total_loss': total_loss,
            'avg_order_value': avg_order_value
        }
    return render_template('reports.html', stats=stats)

if __name__ == '__main__':
    app.run(debug=True)