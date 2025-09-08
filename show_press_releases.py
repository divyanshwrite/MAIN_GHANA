#!/usr/bin/env python3
"""
Script to show all press release data with the new column structure
"""
import os
import psycopg2
import psycopg2.extras

def show_press_releases():
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
        
        print("=== PRESS RELEASES WITH NEW COLUMN STRUCTURE ===\n")
        
        # Query press releases with the new columns
        cur.execute("""
            SELECT 
                press_release_title as "PRESS_RELEASE_TITLE",
                press_release_date as "PRESS_RELEASE_DATE",
                pdf_press_release_link_public_link as "PDF_PUBLIC_LINK",
                CASE 
                    WHEN all_text IS NOT NULL THEN LENGTH(all_text)
                    ELSE 0 
                END as "TEXT_LENGTH_CHARS",
                CASE 
                    WHEN all_text IS NOT NULL THEN SUBSTRING(all_text FROM 1 FOR 100) || '...'
                    ELSE 'No text extracted'
                END as "TEXT_SAMPLE"
            FROM fda_recalls 
            WHERE entry_type = 'press_release' 
            AND press_release_title IS NOT NULL 
            ORDER BY press_release_date DESC 
            LIMIT 10;
        """)
        
        press_releases = cur.fetchall()
        
        if press_releases:
            for i, pr in enumerate(press_releases, 1):
                print(f"📄 PRESS RELEASE #{i}")
                print(f"   TITLE: {pr['PRESS_RELEASE_TITLE']}")
                print(f"   DATE: {pr['PRESS_RELEASE_DATE']}")
                print(f"   PUBLIC PDF LINK: {pr['PDF_PUBLIC_LINK']}")
                print(f"   TEXT EXTRACTED: {pr['TEXT_LENGTH_CHARS']} characters")
                print(f"   SAMPLE TEXT: {pr['TEXT_SAMPLE']}")
                print("-" * 80)
        else:
            print("❌ No press releases found with the new column structure.")
        
        # Show summary statistics
        print("\n=== SUMMARY STATISTICS ===")
        cur.execute("""
            SELECT 
                COUNT(*) as total_press_releases,
                COUNT(press_release_title) as with_title,
                COUNT(press_release_date) as with_date,
                COUNT(pdf_press_release_link_public_link) as with_pdf_link,
                COUNT(all_text) as with_text,
                AVG(LENGTH(all_text)) as avg_text_length
            FROM fda_recalls 
            WHERE entry_type = 'press_release';
        """)
        
        stats = cur.fetchone()
        print(f"Total Press Releases: {stats['total_press_releases']}")
        print(f"With Title: {stats['with_title']}")
        print(f"With Date: {stats['with_date']}")
        print(f"With PDF Link: {stats['with_pdf_link']}")
        print(f"With Extracted Text: {stats['with_text']}")
        print(f"Average Text Length: {int(stats['avg_text_length'] or 0)} characters")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    show_press_releases()
