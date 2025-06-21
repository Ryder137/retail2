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

# ...existing code for other routes...

if __name__ == '__main__':
    init_db()
    app.run(debug=True)