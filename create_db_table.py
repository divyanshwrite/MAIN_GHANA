#!/usr/bin/env python3
"""
Script to create or update the FDA recalls database table with all_text column
"""
import os
import psycopg2
import psycopg2.extras

def create_or_update_table():
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
        
        # Create table if it doesn't exist
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS fda_recalls (
            id SERIAL PRIMARY KEY,
            entry_type VARCHAR(50) DEFAULT 'recall',
            date_recall_issued DATE,
            date_issued DATE,
            product_name TEXT,
            product_type TEXT,
            manufacturer TEXT,
            recalling_firm TEXT,
            batch_numbers TEXT,
            manufacturing_date TEXT,
            expiry_date TEXT,
            reason_for_recall TEXT,
            source_url TEXT,
            pdf_path TEXT,
            alert_title TEXT,
            alert_pdf_filename TEXT,
            all_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        cur.execute(create_table_sql)
        print("✅ Table 'fda_recalls' created or already exists")
        
        # Add all_text column if it doesn't exist
        try:
            cur.execute("""
                ALTER TABLE fda_recalls 
                ADD COLUMN IF NOT EXISTS all_text TEXT;
            """)
            print("✅ Column 'all_text' added or already exists")
        except Exception as e:
            print(f"Note: {e}")
        
        # Create indexes for better performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_fda_recalls_entry_type ON fda_recalls(entry_type);",
            "CREATE INDEX IF NOT EXISTS idx_fda_recalls_date_issued ON fda_recalls(date_issued);",
            "CREATE INDEX IF NOT EXISTS idx_fda_recalls_date_recall_issued ON fda_recalls(date_recall_issued);",
            "CREATE INDEX IF NOT EXISTS idx_fda_recalls_created_at ON fda_recalls(created_at);"
        ]
        
        for idx_sql in indexes:
            cur.execute(idx_sql)
        
        print("✅ Indexes created")
        
        conn.commit()
        cur.close()
        conn.close()
        
        print("✅ Database setup completed successfully!")
        
    except Exception as e:
        print(f"❌ Error setting up database: {e}")

if __name__ == "__main__":
    create_or_update_table()
