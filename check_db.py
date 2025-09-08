#!/usr/bin/env python3
"""
Script to check the database structure and press release entries
"""
import os
import psycopg2
import psycopg2.extras

def check_database():
    # DB connection params
    db_params = {
        'dbname': os.environ.get('FDA_DB_NAME', 'realdb'),
        'user': os.environ.get('FDA_DB_USER', 'divyanshsingh'),
        'host': os.environ.get('FDA_DB_HOST', 'localhost'),
        'port': os.environ.get('FDA_DB_PORT', 5432),
        'password': os.environ.get('FDA_DB_PASSWORD', '')
    }
    
    try:
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        print("=== DATABASE STRUCTURE ===")
        # Get table columns
        cur.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'fda_recalls' 
            ORDER BY ordinal_position;
        """)
        
        columns = cur.fetchall()
        for col in columns:
            print(f"{col['column_name']}: {col['data_type']} ({'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'})")
        
        print("\n=== ENTRY COUNT BY TYPE ===")
        cur.execute("""
            SELECT entry_type, COUNT(*) as count 
            FROM fda_recalls 
            GROUP BY entry_type 
            ORDER BY entry_type;
        """)
        
        counts = cur.fetchall()
        for count in counts:
            print(f"{count['entry_type']}: {count['count']} entries")
        
        print("\n=== RECENT PRESS RELEASES ===")
        cur.execute("""
            SELECT press_release_title, press_release_date, pdf_press_release_link_public_link, 
                   LENGTH(all_text) as text_length
            FROM fda_recalls 
            WHERE entry_type = 'press_release' 
            ORDER BY created_at DESC 
            LIMIT 5;
        """)
        
        press_releases = cur.fetchall()
        if press_releases:
            for pr in press_releases:
                title = pr['press_release_title'] or 'No Title'
                date = pr['press_release_date'] or 'No Date'
                url = pr['pdf_press_release_link_public_link'] or 'No URL'
                text_len = pr['text_length'] or 0
                print(f"- {title[:50]}...")
                print(f"  Date: {date}")
                print(f"  URL: {url}")
                print(f"  Text Length: {text_len} characters")
                print()
        else:
            print("No press release entries found yet.")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")

if __name__ == "__main__":
    check_database()
