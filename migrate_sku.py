# Database Migration Script for SKU Support
# Run this script to add SKU column to existing items table

import sqlite3
import time

def migrate_database():
    """Add SKU column to items table and populate with generated SKUs"""
    conn = sqlite3.connect('inventory.db')
    conn.row_factory = sqlite3.Row
    
    try:
        # Check if SKU column exists
        cursor = conn.execute("PRAGMA table_info(items)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'sku' not in columns:
            print("Adding SKU column to items table...")
            
            # Add SKU column
            conn.execute('ALTER TABLE items ADD COLUMN sku TEXT')
            
            # Generate SKUs for existing items
            items = conn.execute('SELECT id, name FROM items WHERE sku IS NULL OR sku = ""').fetchall()
            for item in items:
                sku = f"SKU{item['id']:06d}"
                conn.execute('UPDATE items SET sku = ? WHERE id = ?', (sku, item['id']))
                print(f"Generated SKU '{sku}' for item: {item['name']}")
            
            # Create unique index on SKU
            try:
                conn.execute('CREATE UNIQUE INDEX idx_items_sku ON items(sku)')
                print("Created unique index on SKU column")
            except sqlite3.OperationalError:
                print("SKU index already exists")
            
            conn.commit()
            print("SKU migration completed successfully!")
        else:
            print("SKU column already exists")
            
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_database()