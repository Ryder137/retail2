from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import sqlite3
import os
import time

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Ensure static directories exist
static_dir = os.path.join(os.path.dirname(__file__), 'static')
images_dir = os.path.join(static_dir, 'images')
os.makedirs(images_dir, exist_ok=True)

# Database initialization
def init_db():
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        branch_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Branches table
    c.execute('''CREATE TABLE IF NOT EXISTS branches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        location TEXT NOT NULL,
        manager_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
      # Items table
    c.execute('''CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        category TEXT,
        unit TEXT,
        min_stock_level INTEGER DEFAULT 10,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Check if SKU column exists in items table, if not add it
    try:
        c.execute('SELECT sku FROM items LIMIT 1')
    except sqlite3.OperationalError:
        # SKU column doesn't exist, add it
        c.execute('ALTER TABLE items ADD COLUMN sku TEXT')
        # Generate SKUs for existing items
        items = c.execute('SELECT id, name FROM items WHERE sku IS NULL OR sku = ""').fetchall()
        for item in items:
            sku = f"SKU{item[0]:06d}"
            c.execute('UPDATE items SET sku = ? WHERE id = ?', (sku, item[0]))
        conn.commit()
            
    # Inventory table
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER,
        branch_id INTEGER,
        quantity INTEGER DEFAULT 0,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (item_id) REFERENCES items (id),
        FOREIGN KEY (branch_id) REFERENCES branches (id)
    )''')
    
    # Transfer requests table
    c.execute('''CREATE TABLE IF NOT EXISTS transfer_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER,
        from_branch_id INTEGER,
        to_branch_id INTEGER,
        quantity INTEGER,
        status TEXT DEFAULT 'pending',
        requested_by INTEGER,
        approved_by INTEGER,
        request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        approved_date TIMESTAMP,
        notes TEXT,
        FOREIGN KEY (item_id) REFERENCES items (id),
        FOREIGN KEY (from_branch_id) REFERENCES branches (id),
        FOREIGN KEY (to_branch_id) REFERENCES branches (id),
        FOREIGN KEY (requested_by) REFERENCES users (id),
        FOREIGN KEY (approved_by) REFERENCES users (id)
    )''')
    
    # Audit logs table
    c.execute('''CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        table_name TEXT,
        record_id INTEGER,
        details TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    # Insert default admin user if not exists
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        admin_password = generate_password_hash('admin123')
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                 ('admin', admin_password, 'owner'))
    
    # Insert sample branches
    c.execute("SELECT COUNT(*) FROM branches")
    if c.fetchone()[0] == 0:
        branches = [
            ('Main Branch', 'Downtown Mall'),
            ('Branch A', 'North Plaza'),
            ('Branch B', 'South Center')
        ]
        c.executemany("INSERT INTO branches (name, location) VALUES (?, ?)", branches)
    
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect('inventory.db')
    conn.row_factory = sqlite3.Row
    return conn

def log_action(user_id, action, table_name=None, record_id=None, details=None):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO audit_logs (user_id, action, table_name, record_id, details) VALUES (?, ?, ?, ?, ?)",
        (user_id, action, table_name, record_id, details)
    )
    conn.commit()
    conn.close()

def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def role_required(roles):
    def decorator(f):
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] not in roles:
                flash('Access denied. Insufficient permissions.', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['branch_id'] = user['branch_id']
            
            log_action(user['id'], f"User logged in")
            flash(f'Welcome, {username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'user_id' in session:
        log_action(session['user_id'], "User logged out")
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    
    # Get branch filter from query parameter
    branch_id = request.args.get('branch_id')
    
    # Get total items
    total_items = conn.execute('SELECT COUNT(*) as count FROM items').fetchone()['count']
    
    # Get total branches
    total_branches = conn.execute('SELECT COUNT(*) as count FROM branches').fetchone()['count']
    
    # Get pending transfers (optionally filtered by branch)
    pending_transfers_query = 'SELECT COUNT(*) as count FROM transfer_requests WHERE status = "pending"'
    if branch_id:
        pending_transfers_query += f' AND (from_branch_id = {branch_id} OR to_branch_id = {branch_id})'
    
    pending_transfers = conn.execute(pending_transfers_query).fetchone()['count']
    
    # Get low stock alerts (optionally filtered by branch)
    low_stock_query = '''
        SELECT COUNT(*) as count FROM inventory i
        JOIN items it ON i.item_id = it.id
        WHERE i.quantity <= it.min_stock_level
    '''
    if branch_id:
        low_stock_query += f' AND i.branch_id = {branch_id}'
    elif session['role'] != 'owner' and session['branch_id']:
        low_stock_query += f' AND i.branch_id = {session["branch_id"]}'
    
    low_stock_count = conn.execute(low_stock_query).fetchone()['count']
    
    # Get recent activities (audit logs)
    recent_activities = conn.execute('''
        SELECT al.*, u.username 
        FROM audit_logs al
        JOIN users u ON al.user_id = u.id
        ORDER BY al.timestamp DESC
        LIMIT 10
    ''').fetchall()
    
    # Get all branches for filtering
    branches = conn.execute('SELECT * FROM branches ORDER BY name').fetchall()
    
    # Get selected branch info if branch_id is provided
    selected_branch = None
    if branch_id:
        selected_branch = conn.execute('SELECT * FROM branches WHERE id = ?', (branch_id,)).fetchone()
    
    conn.close()
    
    return render_template('dashboard.html',
                         total_items=total_items,
                         total_branches=total_branches,
                         pending_transfers=pending_transfers,
                         low_stock_count=low_stock_count,
                         recent_activities=recent_activities,
                         branches=branches,
                         selected_branch=selected_branch,
                         branch_id=branch_id)

@app.route('/inventory')
@login_required
def inventory():
    conn = get_db_connection()
    
    query = '''
        SELECT i.*, it.name, it.description, it.category, it.unit, it.min_stock_level, b.name as branch_name
        FROM inventory i
        JOIN items it ON i.item_id = it.id
        JOIN branches b ON i.branch_id = b.id
    '''
    
    if session['role'] != 'owner' and session['branch_id']:
        query += f' WHERE i.branch_id = {session["branch_id"]}'
    
    query += ' ORDER BY it.name, b.name'
    
    inventory_items = conn.execute(query).fetchall()
    
    # Get branches for filtering
    branches = conn.execute('SELECT * FROM branches ORDER BY name').fetchall()
    
    conn.close()
    
    return render_template('inventory.html', inventory_items=inventory_items, branches=branches)

@app.route('/items')
@login_required
def items():
    conn = get_db_connection()
    items = conn.execute('SELECT id, name, sku, description, category, unit, min_stock_level FROM items ORDER BY name').fetchall()
    conn.close()
    
    return render_template('items.html', items=items)

@app.route('/add_item', methods=['GET', 'POST'])
@login_required
@role_required(['owner', 'manager'])
def add_item():
    if request.method == 'POST':
        name = request.form['name']
        sku = request.form.get('sku') or f"SKU{int(time.time())}"  # Generate SKU if not provided
        description = request.form['description']
        category = request.form['category']
        unit = request.form['unit']
        min_stock_level = request.form['min_stock_level']
        
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                'INSERT INTO items (name, sku, description, category, unit, min_stock_level) VALUES (?, ?, ?, ?, ?, ?)',
                (name, sku, description, category, unit, min_stock_level)
            )
            item_id = cursor.lastrowid
            
            # Create inventory records for all branches
            branches = conn.execute('SELECT id FROM branches').fetchall()
            for branch in branches:
                conn.execute(
                    'INSERT INTO inventory (item_id, branch_id, quantity) VALUES (?, ?, ?)',
                    (item_id, branch['id'], 0)
                )
            
            conn.commit()
            
            log_action(session['user_id'], f"Added new item: {name} (SKU: {sku})", "items", item_id)
            flash(f'Item "{name}" (SKU: {sku}) added successfully!', 'success')
            return redirect(url_for('items'))
            
        except sqlite3.IntegrityError as e:
            if 'sku' in str(e).lower():
                flash('SKU already exists. Please use a different SKU.', 'error')
            else:
                flash('Error adding item. Please check your input.', 'error')
        except Exception as e:
            flash(f'Error adding item: {str(e)}', 'error')
        finally:
            conn.close()
    
    return render_template('add_item.html')

@app.route('/edit_item/<int:item_id>', methods=['GET', 'POST'])
@login_required
@role_required(['owner', 'manager'])
def edit_item(item_id):
    conn = get_db_connection()
    
    if request.method == 'POST':
        name = request.form['name']
        sku = request.form.get('sku')
        description = request.form['description']
        category = request.form['category']
        unit = request.form['unit']
        min_stock_level = request.form['min_stock_level']
        
        try:
            conn.execute(
                'UPDATE items SET name = ?, sku = ?, description = ?, category = ?, unit = ?, min_stock_level = ? WHERE id = ?',
                (name, sku, description, category, unit, min_stock_level, item_id)
            )
            conn.commit()
            
            log_action(session['user_id'], f"Updated item: {name} (SKU: {sku})", "items", item_id)
            flash(f'Item "{name}" updated successfully!', 'success')
            conn.close()
            return redirect(url_for('items'))
            
        except sqlite3.IntegrityError as e:
            if 'sku' in str(e).lower():
                flash('SKU already exists. Please use a different SKU.', 'error')
            else:
                flash('Error updating item. Please check your input.', 'error')
        except Exception as e:
            flash(f'Error updating item: {str(e)}', 'error')
        finally:
            conn.close()
            return redirect(url_for('edit_item', item_id=item_id))
    
    item = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()
    conn.close()
    
    if not item:
        flash('Item not found', 'error')
        return redirect(url_for('items'))
    
    return render_template('edit_item.html', item=item)

@app.route('/update_stock/<int:inventory_id>', methods=['POST'])
@login_required
def update_stock(inventory_id):
    new_quantity = request.form['quantity']
    
    conn = get_db_connection()
    
    # Check if user has permission to update this inventory
    inventory = conn.execute('''
        SELECT i.*, it.name as item_name, b.name as branch_name
        FROM inventory i
        JOIN items it ON i.item_id = it.id
        JOIN branches b ON i.branch_id = b.id
        WHERE i.id = ?
    ''', (inventory_id,)).fetchone()
    
    if not inventory:
        flash('Inventory record not found', 'error')
        conn.close()
        return redirect(url_for('inventory'))
    
    if session['role'] not in ['owner', 'manager'] and inventory['branch_id'] != session['branch_id']:
        flash('You can only update inventory for your branch', 'error')
        conn.close()
        return redirect(url_for('inventory'))
    
    old_quantity = inventory['quantity']
    conn.execute(
        'UPDATE inventory SET quantity = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?',
        (new_quantity, inventory_id)
    )
    conn.commit()
    conn.close()
    
    log_action(session['user_id'], 
              f"Updated stock for {inventory['item_name']} at {inventory['branch_name']} from {old_quantity} to {new_quantity}",
              "inventory", inventory_id)
    
    flash('Stock updated successfully!', 'success')
    return redirect(url_for('inventory'))

@app.route('/transfers')
@login_required
def transfers():
    conn = get_db_connection()
    
    query = '''
        SELECT tr.*, 
               it.name as item_name,
               fb.name as from_branch_name,
               tb.name as to_branch_name,
               ru.username as requested_by_username,
               au.username as approved_by_username
        FROM transfer_requests tr
        JOIN items it ON tr.item_id = it.id
        JOIN branches fb ON tr.from_branch_id = fb.id
        JOIN branches tb ON tr.to_branch_id = tb.id
        JOIN users ru ON tr.requested_by = ru.id
        LEFT JOIN users au ON tr.approved_by = au.id
    '''
    
    if session['role'] == 'staff' and session['branch_id']:
        query += f' WHERE tr.from_branch_id = {session["branch_id"]} OR tr.to_branch_id = {session["branch_id"]}'
    elif session['role'] == 'manager' and session['branch_id']:
        query += f' WHERE tr.from_branch_id = {session["branch_id"]} OR tr.to_branch_id = {session["branch_id"]}'
    
    query += ' ORDER BY tr.request_date DESC'
    
    transfers = conn.execute(query).fetchall()
    conn.close()
    
    return render_template('transfers.html', transfers=transfers)

@app.route('/request_transfer', methods=['GET', 'POST'])
@login_required
def request_transfer():
    if request.method == 'POST':
        item_id = request.form['item_id']
        from_branch_id = request.form['from_branch_id']
        to_branch_id = request.form['to_branch_id']
        quantity = request.form['quantity']
        notes = request.form['notes']
        
        conn = get_db_connection()
        
        # Check if source branch has enough stock
        current_stock = conn.execute(
            'SELECT quantity FROM inventory WHERE item_id = ? AND branch_id = ?',
            (item_id, from_branch_id)
        ).fetchone()
        
        if not current_stock or current_stock['quantity'] < int(quantity):
            flash('Insufficient stock at source branch', 'error')
            conn.close()
            return redirect(url_for('request_transfer'))
        
        cursor = conn.execute(
            '''INSERT INTO transfer_requests 
               (item_id, from_branch_id, to_branch_id, quantity, requested_by, notes) 
               VALUES (?, ?, ?, ?, ?, ?)''',
            (item_id, from_branch_id, to_branch_id, quantity, session['user_id'], notes)
        )
        request_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        log_action(session['user_id'], f"Requested transfer of {quantity} units", "transfer_requests", request_id)
        flash('Transfer request submitted successfully!', 'success')
        return redirect(url_for('transfers'))
    
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM items ORDER BY name').fetchall()
    branches = conn.execute('SELECT * FROM branches ORDER BY name').fetchall()
    
    # Get inventory levels for stock checking
    inventory_rows = conn.execute('''
        SELECT i.*, it.name as item_name, b.name as branch_name
        FROM inventory i
        JOIN items it ON i.item_id = it.id
        JOIN branches b ON i.branch_id = b.id
        ORDER BY it.name, b.name
    ''').fetchall()
    
    # Convert Row objects to dictionaries for JSON serialization
    inventory = [dict(row) for row in inventory_rows]
    
    # Get user's pending transfer requests
    user_transfers = conn.execute('''
        SELECT tr.*, 
               it.name as item_name,
               fb.name as from_branch_name,
               tb.name as to_branch_name
        FROM transfer_requests tr
        JOIN items it ON tr.item_id = it.id
        JOIN branches fb ON tr.from_branch_id = fb.id
        JOIN branches tb ON tr.to_branch_id = tb.id
        WHERE tr.requested_by = ? AND tr.status = 'pending'
        ORDER BY tr.request_date DESC
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return render_template('request_transfer.html', items=items, branches=branches, 
                         inventory=inventory, user_transfers=user_transfers)

@app.route('/approve_transfer/<int:transfer_id>')
@login_required
@role_required(['owner', 'manager'])
def approve_transfer(transfer_id):
    conn = get_db_connection()
    
    # Get transfer details
    transfer = conn.execute(
        'SELECT * FROM transfer_requests WHERE id = ?', (transfer_id,)
    ).fetchone()
    
    if not transfer or transfer['status'] != 'pending':
        flash('Invalid transfer request', 'error')
        conn.close()
        return redirect(url_for('transfers'))
    
    # Check stock availability again
    current_stock = conn.execute(
        'SELECT quantity FROM inventory WHERE item_id = ? AND branch_id = ?',
        (transfer['item_id'], transfer['from_branch_id'])
    ).fetchone()
    
    if current_stock['quantity'] < transfer['quantity']:
        flash('Insufficient stock for transfer', 'error')
        conn.close()
        return redirect(url_for('transfers'))
    
    # Update stock levels
    # Reduce from source branch
    conn.execute(
        'UPDATE inventory SET quantity = quantity - ?, last_updated = CURRENT_TIMESTAMP WHERE item_id = ? AND branch_id = ?',
        (transfer['quantity'], transfer['item_id'], transfer['from_branch_id'])
    )
    
    # Add to destination branch
    conn.execute(
        'UPDATE inventory SET quantity = quantity + ?, last_updated = CURRENT_TIMESTAMP WHERE item_id = ? AND branch_id = ?',
        (transfer['quantity'], transfer['item_id'], transfer['to_branch_id'])
    )
    
    # Update transfer status
    conn.execute(
        'UPDATE transfer_requests SET status = "approved", approved_by = ?, approved_date = CURRENT_TIMESTAMP WHERE id = ?',
        (session['user_id'], transfer_id)
    )
    
    conn.commit()
    conn.close()
    
    log_action(session['user_id'], f"Approved transfer request #{transfer_id}", "transfer_requests", transfer_id)
    flash('Transfer approved and completed!', 'success')
    return redirect(url_for('transfers'))

@app.route('/reject_transfer/<int:transfer_id>')
@login_required
@role_required(['owner', 'manager'])
def reject_transfer(transfer_id):
    conn = get_db_connection()
    conn.execute(
        'UPDATE transfer_requests SET status = "rejected", approved_by = ?, approved_date = CURRENT_TIMESTAMP WHERE id = ?',
        (session['user_id'], transfer_id)
    )
    conn.commit()
    conn.close()
    
    log_action(session['user_id'], f"Rejected transfer request #{transfer_id}", "transfer_requests", transfer_id)
    flash('Transfer request rejected', 'info')
    return redirect(url_for('transfers'))

@app.route('/reports')
@login_required
@role_required(['owner', 'manager'])
def reports():
    conn = get_db_connection()
    branches = conn.execute('SELECT * FROM branches ORDER BY name').fetchall()
    conn.close()
    return render_template('reports.html', branches=branches)

@app.route('/generate_report')
@login_required
@role_required(['owner', 'manager'])
def generate_report():
    report_type = request.args.get('type', 'inventory')
    branch_id = request.args.get('branch_id')
    
    conn = get_db_connection()
    
    if report_type == 'inventory':
        query = '''
            SELECT i.*, it.name, it.description, it.category, it.unit, it.min_stock_level, b.name as branch_name,
                   CASE WHEN i.quantity <= it.min_stock_level THEN 'Low Stock' ELSE 'Normal' END as stock_status
            FROM inventory i
            JOIN items it ON i.item_id = it.id
            JOIN branches b ON i.branch_id = b.id
        '''
        
        if branch_id:
            query += f' WHERE i.branch_id = {branch_id}'
        elif session['role'] == 'manager' and session['branch_id']:
            query += f' WHERE i.branch_id = {session["branch_id"]}'
        
        query += ' ORDER BY it.name, b.name'
        data = conn.execute(query).fetchall()
        
    elif report_type == 'transfers':
        query = '''
            SELECT tr.*, 
                   it.name as item_name,
                   fb.name as from_branch_name,
                   tb.name as to_branch_name,
                   ru.username as requested_by_username
            FROM transfer_requests tr
            JOIN items it ON tr.item_id = it.id
            JOIN branches fb ON tr.from_branch_id = fb.id
            JOIN branches tb ON tr.to_branch_id = tb.id
            JOIN users ru ON tr.requested_by = ru.id
            WHERE tr.request_date >= date('now', '-30 days')
        '''
        
        if branch_id:
            query += f' AND (tr.from_branch_id = {branch_id} OR tr.to_branch_id = {branch_id})'
        elif session['role'] == 'manager' and session['branch_id']:
            query += f' AND (tr.from_branch_id = {session["branch_id"]} OR tr.to_branch_id = {session["branch_id"]})'
        
        query += ' ORDER BY tr.request_date DESC'
        data = conn.execute(query).fetchall()
    
    conn.close()
    
    return jsonify([dict(row) for row in data])

@app.route('/low_stock_alerts')
@login_required
def low_stock_alerts():
    conn = get_db_connection()
    
    query = '''
        SELECT i.*, it.name, it.description, it.category, it.min_stock_level, b.name as branch_name
        FROM inventory i
        JOIN items it ON i.item_id = it.id
        JOIN branches b ON i.branch_id = b.id
        WHERE i.quantity <= it.min_stock_level
    '''
    
    if session['role'] != 'owner' and session['branch_id']:
        query += f' AND i.branch_id = {session["branch_id"]}'
    
    query += ' ORDER BY (i.quantity / CAST(it.min_stock_level AS FLOAT)), it.name'
    
    low_stock_items = conn.execute(query).fetchall()
    conn.close()
    
    return render_template('low_stock_alerts.html', low_stock_items=low_stock_items)

@app.route('/users')
@login_required
@role_required(['owner'])
def users():
    conn = get_db_connection()
    users = conn.execute('''
        SELECT u.*, b.name as branch_name
        FROM users u
        LEFT JOIN branches b ON u.branch_id = b.id
        ORDER BY u.username
    ''').fetchall()
    conn.close()
    
    return render_template('users.html', users=users)

@app.route('/add_user', methods=['GET', 'POST'])
@login_required
@role_required(['owner'])
def add_user():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        branch_id = request.form.get('branch_id') or None
        
        hashed_password = generate_password_hash(password)
        
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                'INSERT INTO users (username, password, role, branch_id) VALUES (?, ?, ?, ?)',
                (username, hashed_password, role, branch_id)
            )
            user_id = cursor.lastrowid
            conn.commit()
            
            log_action(session['user_id'], f"Added new user: {username}", "users", user_id)
            flash('User added successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Username already exists', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('users'))
    
    conn = get_db_connection()
    branches = conn.execute('SELECT * FROM branches ORDER BY name').fetchall()
    conn.close()
    
    return render_template('add_user.html', branches=branches)

@app.route('/delete_transfer/<int:transfer_id>', methods=['POST'])
@login_required
def delete_transfer(transfer_id):
    try:
        conn = get_db_connection()
        
        # Get transfer details for validation and logging
        transfer = conn.execute('''
            SELECT tr.*, it.name as item_name, fb.name as from_branch_name, tb.name as to_branch_name
            FROM transfer_requests tr
            JOIN items it ON tr.item_id = it.id
            JOIN branches fb ON tr.from_branch_id = fb.id
            JOIN branches tb ON tr.to_branch_id = tb.id
            WHERE tr.id = ?
        ''', (transfer_id,)).fetchone()
        
        if not transfer:
            flash('Transfer request not found.', 'error')
            return redirect(url_for('transfers'))
        
        # Check permissions - only owners, managers, or the person who requested can delete
        if not (session['role'] in ['owner', 'manager'] or session['user_id'] == transfer['requested_by']):
            flash('You do not have permission to delete this transfer request.', 'error')
            return redirect(url_for('transfers'))
        
        # Only allow deletion of pending transfers
        if transfer['status'] != 'pending':
            flash('Only pending transfer requests can be deleted.', 'error')
            return redirect(url_for('transfers'))
        
        item_name = transfer['item_name']
        from_branch = transfer['from_branch_name']
        to_branch = transfer['to_branch_name']
        quantity = transfer['quantity']
          # Delete the transfer request
        conn.execute('DELETE FROM transfer_requests WHERE id = ?', (transfer_id,))
        conn.commit()
        
        # Log the action
        log_action(session['user_id'], 'DELETE', 'transfer_requests', transfer_id, 
                  f'Deleted transfer request: {item_name} ({quantity} units) from {from_branch} to {to_branch}')
        
        flash(f'Transfer request for "{item_name}" ({quantity} units) from "{from_branch}" to "{to_branch}" has been successfully deleted.', 'success')
        
    except Exception as e:
        flash(f'Error deleting transfer request: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('transfers'))

@app.route('/delete_activity/<int:activity_id>', methods=['POST'])
@login_required
@role_required(['owner', 'manager'])
def delete_activity(activity_id):
    try:
        conn = get_db_connection()
        
        # Get activity details for logging
        activity = conn.execute('''
            SELECT al.*, u.username 
            FROM audit_logs al
            JOIN users u ON al.user_id = u.id
            WHERE al.id = ?
        ''', (activity_id,)).fetchone()
        
        if not activity:
            flash('Activity record not found.', 'error')
            return redirect(url_for('dashboard'))
        
        username = activity['username']
        action = activity['action']
        
        # Delete the activity record
        conn.execute('DELETE FROM audit_logs WHERE id = ?', (activity_id,))
        conn.commit()
        
        # Log the deletion action (meta-logging)
        log_action(session['user_id'], 'DELETE', 'audit_logs', activity_id, 
                  f'Removed activity log: {username} - {action}')
        
        flash(f'Activity record for "{username}" has been successfully removed.', 'success')
        
    except Exception as e:
        flash(f'Error removing activity record: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('dashboard'))

@app.route('/archive_transfer/<int:transfer_id>', methods=['POST'])
@login_required
@role_required(['owner', 'manager'])
def archive_transfer(transfer_id):
    try:
        conn = get_db_connection()
        
        # Get transfer details for validation and logging
        transfer = conn.execute('''
            SELECT tr.*, it.name as item_name, fb.name as from_branch_name, tb.name as to_branch_name
            FROM transfer_requests tr
            JOIN items it ON tr.item_id = it.id
            JOIN branches fb ON tr.from_branch_id = fb.id
            JOIN branches tb ON tr.to_branch_id = tb.id
            WHERE tr.id = ?
        ''', (transfer_id,)).fetchone()
        
        if not transfer:
            flash('Transfer request not found.', 'error')
            return redirect(url_for('transfers'))
        
        # Only allow archiving of completed transfers (approved or rejected)
        if transfer['status'] not in ['approved', 'rejected']:
            flash('Only completed transfer requests can be archived.', 'error')
            return redirect(url_for('transfers'))
        
        item_name = transfer['item_name']
        from_branch = transfer['from_branch_name']
        to_branch = transfer['to_branch_name']
        quantity = transfer['quantity']
        status = transfer['status']
        
        # Archive (delete) the transfer request
        conn.execute('DELETE FROM transfer_requests WHERE id = ?', (transfer_id,))
        conn.commit()
        
        # Log the action
        log_action(session['user_id'], 'ARCHIVE', 'transfer_requests', transfer_id, 
                  f'Archived {status} transfer: {item_name} ({quantity} units) from {from_branch} to {to_branch}')
        
        flash(f'Transfer record for "{item_name}" ({quantity} units) from "{from_branch}" to "{to_branch}" has been successfully archived.', 'success')
        
    except Exception as e:
        flash(f'Error archiving transfer record: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('transfers'))

@app.route('/delete_inventory/<int:inventory_id>', methods=['POST'])
@login_required
@role_required(['owner', 'manager', 'staff'])
def delete_inventory(inventory_id):
    try:
        conn = get_db_connection()
        
        # Get inventory record details for validation and logging
        inventory = conn.execute('''
            SELECT i.id, it.name as item_name, b.name as branch_name, i.quantity, it.unit, i.branch_id
            FROM inventory i
            JOIN items it ON i.item_id = it.id
            JOIN branches b ON i.branch_id = b.id
            WHERE i.id = ?
        ''', (inventory_id,)).fetchone()
        
        if not inventory:
            flash('Inventory record not found.', 'error')
            return redirect(url_for('inventory'))
        
        # Check permissions - staff can only delete from their own branch
        if session['role'] == 'staff' and session.get('branch_id') != inventory['branch_id']:
            flash('You can only delete inventory records from your assigned branch.', 'error')
            return redirect(url_for('inventory'))
        
        item_name = inventory['item_name']
        branch_name = inventory['branch_name']
        quantity = inventory['quantity']
        unit = inventory['unit']
        
        # Delete the inventory record
        conn.execute('DELETE FROM inventory WHERE id = ?', (inventory_id,))
        conn.commit()
        
        # Log the action
        log_action(session['user_id'], 'DELETE', 'inventory', inventory_id, 
                  f'Deleted inventory: {item_name} ({quantity} {unit}) from {branch_name}')
        
        flash(f'Inventory record for "{item_name}" ({quantity} {unit}) at "{branch_name}" has been successfully deleted.', 'success')
        
    except Exception as e:
        flash(f'Error deleting inventory record: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('inventory'))

@app.route('/delete_item/<int:item_id>', methods=['POST'])
@login_required
@role_required(['owner', 'manager'])
def delete_item(item_id):
    try:
        conn = get_db_connection()
        
        # Get item name for flash message
        item = conn.execute('SELECT name FROM items WHERE id = ?', (item_id,)).fetchone()
        if not item:
            flash('Item not found.', 'error')
            return redirect(url_for('items'))
        
        item_name = item['name']
        
        # Check if item is used in any inventory
        inventory_count = conn.execute(
            'SELECT COUNT(*) as count FROM inventory WHERE item_id = ?', 
            (item_id,)
        ).fetchone()['count']
        
        if inventory_count > 0:
            flash(f'Cannot delete "{item_name}" as it is currently in use in inventory. Please remove all inventory records first.', 'error')
            return redirect(url_for('items'))
        
        # Check if item is used in any transfer requests
        transfer_count = conn.execute(
            'SELECT COUNT(*) as count FROM transfer_requests WHERE item_id = ?', 
            (item_id,)
        ).fetchone()['count']
        
        if transfer_count > 0:
            flash(f'Cannot delete "{item_name}" as it has associated transfer requests.', 'error')
            return redirect(url_for('items'))
        
        # Delete the item
        conn.execute('DELETE FROM items WHERE id = ?', (item_id,))
        conn.commit()
        
        # Log the action
        log_action(session['user_id'], 'DELETE', 'items', item_id, f'Deleted item: {item_name}')
        
        flash(f'Item "{item_name}" has been successfully deleted.', 'success')
        
    except Exception as e:
        flash(f'Error deleting item: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('items'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)