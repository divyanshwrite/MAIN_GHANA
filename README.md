# FDA Ghana Recall & Alert Scraper

A comprehensive web scraper for extracting product recalls and safety alerts from the FDA Ghana website. The scraper downloads PDFs, extracts text content, and stores all data in a PostgreSQL database.

## 🚀 Features

- **Dual Functionality**: Scrapes both product recalls and safety alerts
- **PDF Processing**: Downloads original PDFs and extracts full text content
- **Database Storage**: Stores all data in PostgreSQL with searchable text
- **Robust Error Handling**: Creates fallback PDFs when originals are unavailable
- **Progress Tracking**: Visual progress bars for monitoring scraping status
- **Flexible Options**: Command-line options to run recalls-only, alerts-only, or both

## 📊 Data Extracted

### Product Recalls
- Date recall was issued
- Product name and type
- Manufacturer and recalling firm
- Batch numbers and dates
- Manufacturing and expiry dates
- Reason for recall
- Full PDF text content

### Safety Alerts
- Date alert was issued
- Alert title and description
- Full PDF text content
- Alert categorization

## 🛠 Installation

### Prerequisites
- Python 3.8 or higher
- PostgreSQL database
- Virtual environment (recommended)

### Setup Instructions

1. **Clone the repository:**
```bash
git clone https://github.com/divyanshwrite/MAIN_GHANA.git
cd MAIN_GHANA
```

2. **Create and activate virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
playwright install chromium
```

4. **Set up database environment variables (optional):**
```bash
export FDA_DB_NAME="your_database_name"
export FDA_DB_USER="your_username"
export FDA_DB_HOST="localhost"
export FDA_DB_PORT="5432"
export FDA_DB_PASSWORD="your_password"
```

5. **Initialize database:**
```bash
python create_db_table.py
```

## 🖥 Usage

### Command Line Options

```bash
# Scrape both recalls and alerts (default)
python fda_recall_scraper.py

# Scrape only recalls
python fda_recall_scraper.py --skip-alerts

# Scrape only alerts  
python fda_recall_scraper.py --skip-recalls

# Enable verbose logging
python fda_recall_scraper.py --verbose

# Custom output directory
python fda_recall_scraper.py --output-dir ./custom_output

# Run in non-headless mode (show browser)
python fda_recall_scraper.py --headless false
```

### Database Management

```bash
# Delete all entries from database
python delete_all_entries.py

# Recreate/update database schema
python create_db_table.py
```

## 📁 Output Structure

```
project_root/
├── recalls/                    # Recall PDFs organized by product
│   ├── Product_Name_1/
│   │   └── Recall_Summary_*.pdf
│   └── Product_Name_2/
│       └── Recall_Summary_*.pdf
├── alerts/                     # Alert PDFs
│   ├── Alert_Safety_Alert_*.pdf
│   └── Alert_Medical_Alert_*.pdf
└── scraper.log               # Detailed logging
```

## 🗄 Database Schema

The scraper uses a single `fda_recalls` table to store both recalls and alerts:

```sql
CREATE TABLE fda_recalls (
    id SERIAL PRIMARY KEY,
    entry_type VARCHAR(50) DEFAULT 'recall',     -- 'recall' or 'alert'
    
    -- Recall-specific fields
    date_recall_issued DATE,
    product_name TEXT,
    product_type TEXT,
    manufacturer TEXT,
    recalling_firm TEXT,
    batch_numbers TEXT,
    manufacturing_date TEXT,
    expiry_date TEXT,
    reason_for_recall TEXT,
    
    -- Alert-specific fields
    date_issued DATE,
    alert_title TEXT,
    alert_pdf_filename TEXT,
    
    -- Common fields
    source_url TEXT,
    pdf_path TEXT,
    all_text TEXT,                               -- Extracted PDF content
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## ⚙️ Configuration

### Database Connection

The scraper uses these environment variables (with defaults):

- `FDA_DB_NAME`: Database name (default: 'realdb')
- `FDA_DB_USER`: Database user (default: 'divyanshsingh')
- `FDA_DB_HOST`: Database host (default: 'localhost')
- `FDA_DB_PORT`: Database port (default: 5432)
- `FDA_DB_PASSWORD`: Database password (default: '')

### Default Settings

- **Headless Mode**: Enabled (browser runs in background)
- **Output Directory**: `./recalls`
- **Timeout**: 60 seconds for page loads, 30 seconds for downloads
- **Pagination**: Automatically handles "Show All" entries

## 🔧 Advanced Features

### PDF Text Extraction
The scraper automatically extracts text from downloaded PDFs using PyPDF2 and stores it in the `all_text` column for full-text search capabilities.

### Error Handling
- **404 Errors**: Creates fallback PDFs with available information
- **Connection Issues**: Automatically retries with exponential backoff
- **PDF Processing**: Gracefully handles corrupted or unreadable PDFs
- **Database Errors**: Rolls back transactions on failure

### Logging
Comprehensive logging with different levels:
- **INFO**: General progress and status
- **DEBUG**: Detailed HTTP requests and responses  
- **WARNING**: Non-fatal issues and fallbacks
- **ERROR**: Critical errors and failures

## 📈 Performance

- **Typical Runtime**: 
  - Recalls: ~8-12 minutes for 42 entries
  - Alerts: ~2-3 minutes for 10 entries
- **Success Rate**: 95%+ with fallback PDFs for missing content
- **Text Extraction**: 2,000-8,000 characters per PDF on average

## 🔍 Example Queries

After scraping, you can query the database:

```sql
-- Find all recalls for a specific product
SELECT * FROM fda_recalls 
WHERE entry_type = 'recall' AND product_name ILIKE '%antibiotic%';

-- Search alerts by text content
SELECT alert_title, date_issued FROM fda_recalls 
WHERE entry_type = 'alert' AND all_text ILIKE '%counterfeit%';

-- Get recent entries
SELECT * FROM fda_recalls 
ORDER BY created_at DESC LIMIT 10;

-- Count by type
SELECT entry_type, COUNT(*) FROM fda_recalls GROUP BY entry_type;
```

## 🚨 Common Issues & Solutions

### ModuleNotFoundError
```bash
# Ensure virtual environment is activated
source venv/bin/activate
pip install -r requirements.txt
```

### Database Connection Errors
```bash
# Check PostgreSQL is running
brew services start postgresql  # macOS
sudo systemctl start postgresql # Linux

# Verify connection parameters
python create_db_table.py
```

### Playwright Browser Issues
```bash
# Reinstall browser
playwright install chromium --force
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit changes (`git commit -am 'Add new feature'`)
4. Push to branch (`git push origin feature/new-feature`)
5. Create a Pull Request

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🏥 Data Source

This scraper extracts data from the official FDA Ghana website:
- Recalls: https://fdaghana.gov.gh/newsroom/product-recalls-and-alerts/
- Alerts: https://fdaghana.gov.gh/newsroom/product-alerts/

## 📞 Support

For issues and questions:
1. Check the logs in `scraper.log`
2. Review common issues above
3. Open an issue on GitHub

---

**Last Updated**: September 2025  
**Version**: 2.0.0 - Added alert scraping and PDF text extraction
