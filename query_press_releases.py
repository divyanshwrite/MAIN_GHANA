#!/usr/bin/env python3
"""
Interactive script to view all press release data using various SQL queries
"""
import os
import psycopg2
import psycopg2.extras

def get_db_connection():
    """Get database connection"""
    db_params = {
        'dbname': os.environ.get('FDA_DB_NAME', 'realdb'),
        'user': os.environ.get('FDA_DB_USER', 'divyanshsingh'),
        'host': os.environ.get('FDA_DB_HOST', 'localhost'),
        'port': os.environ.get('FDA_DB_PORT', 5432),
        'password': os.environ.get('FDA_DB_PASSWORD', '')
    }
    return psycopg2.connect(**db_params)

def execute_query(query, description):
    """Execute a query and display results"""
    print(f"\n{'='*60}")
    print(f"📊 {description}")
    print('='*60)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cur.execute(query)
        results = cur.fetchall()
        
        if results:
            # Print column headers
            if results:
                headers = list(results[0].keys())
                header_line = " | ".join(f"{h:20}" for h in headers)
                print(header_line)
                print("-" * len(header_line))
                
                # Print rows
                for row in results:
                    row_line = " | ".join(f"{str(row[h])[:20]:20}" for h in headers)
                    print(row_line)
                
                print(f"\n📈 Total records: {len(results)}")
        else:
            print("❌ No results found.")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error executing query: {e}")

def main():
    """Main interactive menu"""
    queries = {
        "1": {
            "desc": "ALL PRESS RELEASES (Basic View)",
            "sql": """
                SELECT 
                    id,
                    press_release_title as "TITLE",
                    press_release_date as "DATE", 
                    pdf_press_release_link_public_link as "PDF_URL",
                    created_at as "SCRAPED_AT"
                FROM fda_recalls 
                WHERE entry_type = 'press_release' 
                ORDER BY press_release_date DESC;
            """
        },
        "2": {
            "desc": "PRESS RELEASES WITH TEXT LENGTH",
            "sql": """
                SELECT 
                    id,
                    press_release_title as "TITLE",
                    press_release_date as "DATE",
                    LENGTH(all_text) as "TEXT_LENGTH",
                    created_at as "SCRAPED_AT"
                FROM fda_recalls 
                WHERE entry_type = 'press_release' 
                ORDER BY press_release_date DESC;
            """
        },
        "3": {
            "desc": "PRESS RELEASES WITH TEXT PREVIEW",
            "sql": """
                SELECT 
                    press_release_title as "TITLE",
                    press_release_date as "DATE",
                    LEFT(all_text, 100) as "TEXT_PREVIEW"
                FROM fda_recalls 
                WHERE entry_type = 'press_release' 
                AND all_text IS NOT NULL
                ORDER BY press_release_date DESC;
            """
        },
        "4": {
            "desc": "COMPREHENSIVE VIEW (All Columns)",
            "sql": """
                SELECT 
                    id,
                    press_release_title,
                    press_release_date,
                    pdf_press_release_link_public_link,
                    LENGTH(all_text) as text_length,
                    created_at
                FROM fda_recalls 
                WHERE entry_type = 'press_release'
                ORDER BY press_release_date DESC;
            """
        },
        "5": {
            "desc": "STATISTICS SUMMARY",
            "sql": """
                SELECT 
                    COUNT(*) as "TOTAL_PRESS_RELEASES",
                    COUNT(press_release_title) as "WITH_TITLE",
                    COUNT(press_release_date) as "WITH_DATE", 
                    COUNT(pdf_press_release_link_public_link) as "WITH_PDF_LINK",
                    COUNT(all_text) as "WITH_TEXT",
                    ROUND(AVG(LENGTH(all_text))::numeric, 0) as "AVG_TEXT_LENGTH",
                    MIN(press_release_date) as "OLDEST_DATE",
                    MAX(press_release_date) as "NEWEST_DATE"
                FROM fda_recalls 
                WHERE entry_type = 'press_release';
            """
        },
        "6": {
            "desc": "RECENT PRESS RELEASES (Last 10)",
            "sql": """
                SELECT 
                    press_release_title as "TITLE",
                    press_release_date as "DATE",
                    LENGTH(all_text) as "TEXT_LENGTH"
                FROM fda_recalls 
                WHERE entry_type = 'press_release' 
                AND press_release_title IS NOT NULL
                ORDER BY press_release_date DESC 
                LIMIT 10;
            """
        },
        "7": {
            "desc": "SEARCH BY KEYWORD (COVID)",
            "sql": """
                SELECT 
                    press_release_title as "TITLE",
                    press_release_date as "DATE",
                    LENGTH(all_text) as "TEXT_LENGTH"
                FROM fda_recalls 
                WHERE entry_type = 'press_release' 
                AND (press_release_title ILIKE '%covid%' OR all_text ILIKE '%covid%')
                ORDER BY press_release_date DESC;
            """
        }
    }
    
    print("🏥 FDA GHANA PRESS RELEASES DATABASE VIEWER")
    print("=" * 50)
    
    while True:
        print("\n📋 Available Queries:")
        for key, value in queries.items():
            print(f"  {key}. {value['desc']}")
        print("  8. Custom SQL Query")
        print("  0. Exit")
        
        choice = input("\n🔍 Select a query (0-8): ").strip()
        
        if choice == "0":
            print("👋 Goodbye!")
            break
        elif choice in queries:
            execute_query(queries[choice]["sql"], queries[choice]["desc"])
        elif choice == "8":
            custom_sql = input("\n💻 Enter your custom SQL query:\n> ")
            if custom_sql.strip():
                execute_query(custom_sql, "CUSTOM QUERY")
        else:
            print("❌ Invalid choice. Please try again.")
        
        input("\n⏸️  Press Enter to continue...")

if __name__ == "__main__":
    main()
