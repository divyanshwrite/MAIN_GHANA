#!/usr/bin/env python3
"""
Script to delete all entries from the FDA recalls database table
"""
import os
import psycopg2
import psycopg2.extras

def delete_all_entries():
    # DB connection params (same as in main scraper)
    db_params = {
        'dbname': os.environ.get('FDA_DB_NAME', 'realdb'),
        'user': os.environ.get('FDA_DB_USER', 'divyanshsingh'),
        'host': os.environ.get('FDA_DB_HOST', 'localhost'),
        'port': os.environ.get('FDA_DB_PORT', 5432),
        'password': os.environ.get('FDA_DB_PASSWORD', '')
    }
    
    try:
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()
        
        # First, check how many entries exist
        cur.execute("SELECT COUNT(*) FROM fda_recalls;")
        count = cur.fetchone()[0]
        print(f"📊 Found {count} entries in the database")
        
        if count == 0:
            print("✅ Database is already empty")
            return
        
        # Show breakdown by entry type
        cur.execute("""
            SELECT entry_type, COUNT(*) 
            FROM fda_recalls 
            GROUP BY entry_type;
        """)
        breakdown = cur.fetchall()
        print("📋 Current entries breakdown:")
        for entry_type, cnt in breakdown:
            print(f"   - {entry_type}: {cnt} entries")
        
        # Confirm deletion
        response = input(f"\n⚠️  Are you sure you want to delete ALL {count} entries? (type 'YES' to confirm): ")
        
        if response == 'YES':
            # Delete all entries
            cur.execute("DELETE FROM fda_recalls;")
            deleted_count = cur.rowcount
            
            # Reset the sequence (auto-increment counter)
            cur.execute("ALTER SEQUENCE fda_recalls_id_seq RESTART WITH 1;")
            
            conn.commit()
            print(f"✅ Successfully deleted {deleted_count} entries from the database")
            print("✅ Auto-increment ID counter has been reset to 1")
        else:
            print("❌ Deletion cancelled")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error accessing database: {e}")

if __name__ == "__main__":
    delete_all_entries()
