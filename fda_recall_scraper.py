import argparse
import logging
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Optional

from tqdm import tqdm
from bs4 import BeautifulSoup
from fpdf import FPDF
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import requests
import psycopg2
import psycopg2.extras
from datetime import datetime
import PyPDF2
import pytesseract
from PIL import Image
from pdf2image import convert_from_path

# Logging configuration
def setup_logging(verbose: bool = False, output_dir: Path = Path("./recalls")):
    log_level = logging.DEBUG if verbose else logging.INFO
    log_file = output_dir / "scraper.log"
    output_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",

        handlers=[
            logging.FileHandler(log_file, mode="w"),
            logging.StreamHandler(sys.stdout)
        ]
    )

# Utility functions
def clean_filename(name: str) -> str:
    # Remove special characters and trim whitespace
    return re.sub(r"[^\w\- ]", "", name).strip().replace(" ", "_")

def to_latin1(text: str) -> str:
    # Replace non-latin-1 characters with closest ASCII or '?'
    if not isinstance(text, str):
        text = str(text)
    try:
        return text.encode("latin-1", errors="replace").decode("latin-1")
    except Exception:
        return text.encode("ascii", errors="replace").decode("ascii")

def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text content from PDF file using both PyPDF2 and OCR"""
    try:
        text = ""
        
        # First try PyPDF2 for text-based PDFs
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            logging.warning(f"PyPDF2 extraction failed for {pdf_path}: {e}")
        
        # If no text extracted or very little text, try OCR
        if len(text.strip()) < 100:  # If very little text extracted
            logging.info(f"Attempting OCR extraction for {pdf_path}")
            try:
                # Convert PDF pages to images
                images = convert_from_path(pdf_path, dpi=200)
                ocr_text = ""
                
                for i, image in enumerate(images[:10]):  # Limit to first 10 pages
                    try:
                        # Extract text using OCR
                        page_text = pytesseract.image_to_string(image, lang='eng')
                        if page_text.strip():
                            ocr_text += f"Page {i+1}:\n{page_text}\n\n"
                    except Exception as e:
                        logging.warning(f"OCR failed for page {i+1} of {pdf_path}: {e}")
                
                if len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text
                    logging.info(f"OCR extracted {len(ocr_text)} characters from {pdf_path}")
                
            except Exception as e:
                logging.error(f"OCR extraction failed for {pdf_path}: {e}")
        
        return text.strip()
    except Exception as e:
        logging.error(f"Failed to extract text from PDF {pdf_path}: {e}")
        return ""

def save_pdf(output_path: Path, title: str, fields: Dict[str, str]):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=to_latin1(title), ln=True, align="C")
    pdf.ln(10)
    for key, value in fields.items():
        safe_key = to_latin1(key)
        safe_value = to_latin1(value)
        pdf.multi_cell(0, 10, f"{safe_key}: {safe_value}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))

# Scraper class

class FDARecallScraper:
    BASE_URL = "https://fdaghana.gov.gh/newsroom/product-recalls-and-alerts/"
    ALERTS_URL = "https://fdaghana.gov.gh/newsroom/product-alerts/"
    PRESS_RELEASES_URL = "https://fdaghana.gov.gh/newsroom/press-release/"

    def __init__(self, output_dir: Path, headless: bool = True, verbose: bool = False):
        self.output_dir = output_dir
        self.headless = headless
        self.verbose = verbose
        setup_logging(verbose, output_dir)
        self.session = requests.Session()
        # DB connection params (edit as needed or use env vars)
        self.db_params = {
            'dbname': os.environ.get('FDA_DB_NAME', 'realdb'),
            'user': os.environ.get('FDA_DB_USER', 'divyanshsingh'),
            'host': os.environ.get('FDA_DB_HOST', 'localhost'),
            'port': os.environ.get('FDA_DB_PORT', 5432),
            'password': os.environ.get('FDA_DB_PASSWORD', '')
        }
        self.db_conn = None
        self._connect_db()

    def _connect_db(self):
        try:
            self.db_conn = psycopg2.connect(**self.db_params)
        except Exception as e:
            logging.error(f"Could not connect to database: {e}")
            self.db_conn = None


    def _insert_db(self, fields: dict, pdf_path: str, source_url: str = None, entry_type: str = 'recall', alert_title: str = None, alert_pdf_filename: str = None, all_text: str = None, press_release_title: str = None, press_release_date: str = None, pdf_public_link: str = None):
        if not self.db_conn:
            return
        def parse_date(val):
            if not val:
                return None
            val = val.strip()
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"):
                try:
                    return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
                except Exception:
                    continue
            for fmt in ("%Y", "%Y-%m"):
                try:
                    return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
                except Exception:
                    continue
            return None
        try:
            with self.db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                if entry_type == 'alert':
                    cur.execute("""
                        INSERT INTO fda_recalls (
                            entry_type, date_issued, alert_title, alert_pdf_filename, pdf_path, all_text, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    """,
                    [
                        'alert',
                        parse_date(fields.get("Date Issued") or fields.get("Date Alert was Issued")),
                        alert_title,
                        alert_pdf_filename,
                        pdf_path,
                        all_text
                    ])
                elif entry_type == 'press_release':
                    cur.execute("""
                        INSERT INTO fda_recalls (
                            entry_type, press_release_title, press_release_date, pdf_press_release_link_public_link, pdf_path, all_text, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    """,
                    [
                        'press_release',
                        press_release_title,
                        parse_date(press_release_date or fields.get("Date Issued") or fields.get("Date")),
                        pdf_public_link,
                        pdf_path,
                        all_text
                    ])
                else:
                    cur.execute("""
                        INSERT INTO public.fda_recalls (
                            date_recall_issued, product_name, product_type, manufacturer, recalling_firm,
                            batch_numbers, manufacturing_date, expiry_date, reason_for_recall, source_url, pdf_path, entry_type, all_text, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    [
                        parse_date(fields.get("Date Recall was Issued")),
                        fields.get("Product Name"),
                        fields.get("Product Type"),
                        fields.get("Manufacturer"),
                        fields.get("Recalling Firm"),
                        fields.get("Batch(es)"),
                        fields.get("Manufacturing Date"),
                        fields.get("Expiry Date"),
                        fields.get("Reason for Recall"),
                        source_url,
                        pdf_path,
                        'recall',
                        all_text
                    ])
                self.db_conn.commit()
        except Exception as e:
            logging.error(f"Failed to insert into DB: {e}")
            try:
                self.db_conn.rollback()
            except Exception:
                pass

    def scrape_alerts(self):
        logging.info("Starting FDA Ghana Alerts Scraper...")
        
        # Use Playwright to render the JavaScript table properly
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            try:
                page.goto(self.ALERTS_URL, timeout=60000)
                page.wait_for_load_state("networkidle")
                
                # Wait for DataTable to load
                try:
                    page.wait_for_selector("table#DataTables_Table_0", timeout=10000)
                    logging.info("DataTable found and loaded")
                except Exception:
                    logging.warning("DataTable not found, using basic table")
                
                # Try to set "Show all entries" if available
                try:
                    select = page.query_selector('select[name="DataTables_Table_0_length"]')
                    if select:
                        options = select.query_selector_all("option")
                        for option in options:
                            text = option.inner_text().strip()
                            if text == "All" or text == "-1":
                                select.select_option(value=option.get_attribute("value"))
                                page.wait_for_timeout(2000)  # Wait for table to update
                                break
                except Exception as e:
                    logging.warning(f"Could not set show all entries: {e}")
                
                html = page.content()
            except Exception as e:
                logging.error(f"Error loading alerts page with Playwright: {e}")
                return
            finally:
                browser.close()
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Look for the DataTable
        table = soup.find("table", {"id": "DataTables_Table_0"})
        if not table:
            table = soup.find("table")
            
        if not table:
            logging.error("Could not find alerts table on the page.")
            return
            
        tbody = table.find("tbody")
        if tbody:
            rows = tbody.find_all("tr")
        else:
            rows = table.find_all("tr")[1:]  # skip header if no tbody
            
        logging.info(f"Found {len(rows)} alert entries.")
        
        # Debug: Print first few rows to see what we're getting
        for i, row in enumerate(rows[:3]):
            cols = row.find_all(["td", "th"])
            logging.debug(f"Row {i+1}: {[col.get_text(strip=True) for col in cols]}")
        
        alerts_dir = self.output_dir.parent / "alerts"
        alerts_dir.mkdir(parents=True, exist_ok=True)
        
        for i, row in enumerate(tqdm(rows, desc="Processing alerts"), 1):
            cols = row.find_all(["td", "th"])
            if len(cols) < 2:
                continue
                
            date_issued = cols[0].get_text(strip=True)
            alert_name_cell = cols[1]
            alert_title = alert_name_cell.get_text(strip=True)
            
            # Skip empty or invalid rows
            if not date_issued or not alert_title or len(alert_title) < 5:
                continue
            
            # Check for links in the name cell
            link = alert_name_cell.find("a")
            
            logging.info(f"Processing alert {i}: {alert_title[:50]}...")
            
            cleaned_title = clean_filename(alert_title)[:60]
            date_str = "".join(date_issued.split("/"))  # fallback if needed
            try:
                dt = datetime.strptime(date_issued, "%d/%m/%Y")
                date_str = dt.strftime("%Y%m%d")
            except Exception:
                date_str = re.sub(r"[^0-9]", "", date_issued)[:8]
            
            pdf_filename = f"Alert_{cleaned_title}_{date_str}.pdf"
            pdf_path = alerts_dir / pdf_filename
            pdf_saved = False
            extracted_text = ""
            
            if link and link.has_attr("href"):
                pdf_url = link["href"]
                if not pdf_url.startswith("http"):
                    pdf_url = requests.compat.urljoin(self.ALERTS_URL, pdf_url)
                logging.info(f"Attempting to download alert PDF: {pdf_url}")
                try:
                    r = self.session.get(pdf_url, timeout=30)
                    logging.info(f"HTTP status for {pdf_url}: {r.status_code}, content-type: {r.headers.get('content-type')}")
                    if r.status_code == 200:
                        content_type = r.headers.get("content-type", "").lower()
                        if content_type.startswith("application/pdf"):
                            with open(pdf_path, "wb") as f:
                                f.write(r.content)
                            pdf_saved = True
                            logging.info(f"Downloaded alert PDF: {pdf_path}")
                            
                            # Extract text from the downloaded PDF
                            extracted_text = extract_pdf_text(pdf_path)
                            if extracted_text:
                                logging.info(f"Extracted {len(extracted_text)} characters from PDF")
                            
                        elif "text/html" in content_type:
                            # It's an HTML page, try to extract more info
                            detail_soup = BeautifulSoup(r.text, "html.parser")
                            # Look for PDF links in the detail page
                            pdf_links = detail_soup.find_all("a", href=lambda x: x and x.endswith('.pdf'))
                            if pdf_links:
                                for pdf_link in pdf_links:
                                    direct_pdf_url = pdf_link["href"]
                                    if not direct_pdf_url.startswith("http"):
                                        direct_pdf_url = requests.compat.urljoin(pdf_url, direct_pdf_url)
                                    try:
                                        pdf_resp = self.session.get(direct_pdf_url, timeout=30)
                                        if pdf_resp.status_code == 200 and pdf_resp.headers.get("content-type", "").lower().startswith("application/pdf"):
                                            with open(pdf_path, "wb") as f:
                                                f.write(pdf_resp.content)
                                            pdf_saved = True
                                            logging.info(f"Downloaded alert PDF from detail page: {pdf_path}")
                                            break
                                    except Exception as e:
                                        logging.warning(f"Failed to download PDF from detail page: {e}")
                            
                            if not pdf_saved:
                                # Create PDF with HTML content
                                self._create_alert_pdf_from_html(pdf_path, alert_title, date_issued, detail_soup)
                                pdf_saved = True
                        else:
                            logging.warning(f"Alert link is not a PDF: {pdf_url} (content-type: {content_type})")
                    else:
                        logging.warning(f"Alert PDF not found: {pdf_url} (status {r.status_code})")
                except Exception as e:
                    logging.error(f"Failed to download alert for '{alert_title}' at {pdf_url}: {e}")
            
            if not pdf_saved:
                # Fallback PDF with alert info
                self._create_fallback_alert_pdf(pdf_path, alert_title, date_issued)
                logging.info(f"Saved fallback alert PDF: {pdf_path}")
                # For fallback PDFs, use the alert title as the extracted text
                extracted_text = f"Alert Title: {alert_title}\nDate Issued: {date_issued}"
            
            # Insert into DB with extracted text
            self._insert_db(
                fields={"Date Issued": date_issued},
                pdf_path=str(pdf_path),
                entry_type='alert',
                alert_title=alert_title,
                alert_pdf_filename=pdf_path.name,
                all_text=extracted_text
            )

    def _create_alert_pdf_from_html(self, pdf_path, title, date_issued, soup):
        """Create PDF from HTML content of alert detail page"""
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=to_latin1(f"FDA Ghana Alert - {date_issued}"), ln=True, align="C")
        pdf.ln(5)
        pdf.set_font("Arial", "B", 14)
        pdf.multi_cell(0, 10, to_latin1(title))
        pdf.ln(5)
        
        # Extract main content
        content_div = soup.find("div", class_="entry-content") or soup.find("div", class_="content") or soup.find("main")
        if content_div:
            text_content = content_div.get_text(separator="\n", strip=True)
            pdf.set_font("Arial", size=10)
            # Clean and limit content
            lines = text_content.split("\n")[:50]  # Limit lines
            for line in lines:
                if line.strip():
                    pdf.multi_cell(0, 5, to_latin1(line.strip()[:100]))
        
        pdf.output(str(pdf_path))
        
    def _create_fallback_alert_pdf(self, pdf_path, title, date_issued):
        """Create fallback PDF for alert"""
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=to_latin1(f"FDA Ghana Alert - {date_issued}"), ln=True, align="C")
        pdf.ln(10)
        pdf.set_font("Arial", "B", 14)
        pdf.multi_cell(0, 10, to_latin1(title))
        pdf.ln(5)
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 8, "Alert details were not directly accessible from the FDA Ghana website.")
        pdf.multi_cell(0, 8, f"Date Issued: {date_issued}")
        pdf.output(str(pdf_path))

    def scrape_press_releases(self):
        logging.info("Starting FDA Ghana Press Releases Scraper...")
        
        # Use Playwright to render the JavaScript table properly
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            try:
                page.goto(self.PRESS_RELEASES_URL, timeout=60000)
                page.wait_for_load_state("networkidle")
                
                # Wait for DataTable to load
                try:
                    page.wait_for_selector("table", timeout=10000)
                    logging.info("Press releases table found and loaded")
                except Exception:
                    logging.warning("Press releases table not found immediately")
                
                # Try to set "Show all entries" if available
                try:
                    # Look for DataTable length select
                    select = page.query_selector('select[name*="length"], select[name*="DataTables_Table"]')
                    if select:
                        options = select.query_selector_all("option")
                        for option in options:
                            text = option.inner_text().strip()
                            if text == "All" or text == "-1":
                                select.select_option(value=option.get_attribute("value"))
                                page.wait_for_timeout(2000)  # Wait for table to update
                                break
                        else:
                            # If no "All" option, try to select the largest number
                            max_val = 10
                            max_option = None
                            for option in options:
                                text = option.inner_text().strip()
                                if text.isdigit() and int(text) > max_val:
                                    max_val = int(text)
                                    max_option = option
                            if max_option:
                                select.select_option(value=max_option.get_attribute("value"))
                                page.wait_for_timeout(2000)
                except Exception as e:
                    logging.warning(f"Could not set show all entries for press releases: {e}")
                
                html = page.content()
            except Exception as e:
                logging.error(f"Error loading press releases page with Playwright: {e}")
                return
            finally:
                browser.close()
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Look for the main table - try different approaches
        table = None
        # First try to find DataTable
        table = soup.find("table", {"id": lambda x: x and "DataTables_Table" in x})
        if not table:
            # Try to find any table with date and title columns
            tables = soup.find_all("table")
            for t in tables:
                headers = [th.get_text(strip=True).lower() for th in t.find_all("th")]
                if any("date" in h for h in headers) and any("title" in h or "press" in h for h in headers):
                    table = t
                    break
        if not table:
            # Fallback to first table
            tables = soup.find_all("table")
            if tables:
                table = tables[0]
            
        if not table:
            logging.error("Could not find press releases table on the page.")
            return
            
        tbody = table.find("tbody")
        if tbody:
            rows = tbody.find_all("tr")
        else:
            rows = table.find_all("tr")[1:]  # skip header if no tbody
            
        logging.info(f"Found {len(rows)} press release entries.")
        
        # Debug: Print first few rows to see what we're getting
        for i, row in enumerate(rows[:3]):
            cols = row.find_all(["td", "th"])
            logging.debug(f"Press Release Row {i+1}: {[col.get_text(strip=True) for col in cols]}")
        
        press_releases_dir = self.output_dir.parent / "press_releases"
        press_releases_dir.mkdir(parents=True, exist_ok=True)
        
        for i, row in enumerate(tqdm(rows, desc="Processing press releases"), 1):
            cols = row.find_all(["td", "th"])
            if len(cols) < 2:
                continue
                
            date_issued = cols[0].get_text(strip=True)
            press_release_cell = cols[1]
            press_release_title = press_release_cell.get_text(strip=True)
            
            # Skip empty or invalid rows
            if not date_issued or not press_release_title or len(press_release_title) < 5:
                continue
            
            # Check for links in the title cell
            link = press_release_cell.find("a")
            
            logging.info(f"Processing press release {i}: {press_release_title[:50]}...")
            
            cleaned_title = clean_filename(press_release_title)[:60]
            date_str = "".join(date_issued.split("/"))  # fallback if needed
            try:
                dt = datetime.strptime(date_issued, "%d/%m/%Y")
                date_str = dt.strftime("%Y%m%d")
            except Exception:
                # Try other date formats
                for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
                    try:
                        dt = datetime.strptime(date_issued, fmt)
                        date_str = dt.strftime("%Y%m%d")
                        break
                    except Exception:
                        continue
                else:
                    date_str = re.sub(r"[^0-9]", "", date_issued)[:8]
            
            pdf_filename = f"{cleaned_title}_{date_str}.pdf"
            pdf_path = press_releases_dir / pdf_filename
            pdf_saved = False
            extracted_text = ""
            pdf_public_url = None
            
            if link and link.has_attr("href"):
                pdf_url = link["href"]
                if not pdf_url.startswith("http"):
                    pdf_url = requests.compat.urljoin(self.PRESS_RELEASES_URL, pdf_url)
                
                # Store the public URL for database
                pdf_public_url = pdf_url
                
                logging.info(f"Attempting to download press release PDF: {pdf_url}")
                try:
                    r = self.session.get(pdf_url, timeout=30)
                    logging.info(f"HTTP status for {pdf_url}: {r.status_code}, content-type: {r.headers.get('content-type')}")
                    if r.status_code == 200:
                        content_type = r.headers.get("content-type", "").lower()
                        if content_type.startswith("application/pdf"):
                            with open(pdf_path, "wb") as f:
                                f.write(r.content)
                            pdf_saved = True
                            logging.info(f"Downloaded press release PDF: {pdf_path}")
                            
                            # Extract text from the downloaded PDF
                            extracted_text = extract_pdf_text(pdf_path)
                            if extracted_text:
                                logging.info(f"Extracted {len(extracted_text)} characters from PDF")
                            
                        elif "text/html" in content_type:
                            # It's an HTML page, try to extract more info or find PDF links
                            detail_soup = BeautifulSoup(r.text, "html.parser")
                            # Look for PDF links in the detail page
                            pdf_links = detail_soup.find_all("a", href=lambda x: x and x.endswith('.pdf'))
                            if pdf_links:
                                for pdf_link in pdf_links:
                                    direct_pdf_url = pdf_link["href"]
                                    if not direct_pdf_url.startswith("http"):
                                        direct_pdf_url = requests.compat.urljoin(pdf_url, direct_pdf_url)
                                    try:
                                        pdf_resp = self.session.get(direct_pdf_url, timeout=30)
                                        if pdf_resp.status_code == 200 and pdf_resp.headers.get("content-type", "").lower().startswith("application/pdf"):
                                            with open(pdf_path, "wb") as f:
                                                f.write(pdf_resp.content)
                                            pdf_saved = True
                                            logging.info(f"Downloaded press release PDF from detail page: {pdf_path}")
                                            
                                            # Extract text from the downloaded PDF
                                            extracted_text = extract_pdf_text(pdf_path)
                                            if extracted_text:
                                                logging.info(f"Extracted {len(extracted_text)} characters from PDF")
                                            break
                                    except Exception as e:
                                        logging.warning(f"Failed to download PDF from detail page: {e}")
                            
                            if not pdf_saved:
                                # Create PDF with HTML content
                                self._create_press_release_pdf_from_html(pdf_path, press_release_title, date_issued, detail_soup)
                                pdf_saved = True
                                extracted_text = f"Press Release Title: {press_release_title}\nDate: {date_issued}\nContent extracted from HTML page"
                        else:
                            logging.warning(f"Press release link is not a PDF: {pdf_url} (content-type: {content_type})")
                    else:
                        logging.warning(f"Press release PDF not found: {pdf_url} (status {r.status_code})")
                        # Create 404 fallback PDF
                        fallback_filename = f"Page_Not_Found_{cleaned_title}_{date_str}.pdf"
                        fallback_path = press_releases_dir / fallback_filename
                        self._create_not_found_pdf(fallback_path, press_release_title, date_issued)
                        pdf_path = fallback_path
                        pdf_saved = True
                        extracted_text = "Page not found for this press release"
                        
                except Exception as e:
                    logging.error(f"Failed to download press release for '{press_release_title}' at {pdf_url}: {e}")
                    # Create fallback PDF for failed download
                    fallback_filename = f"Page_Not_Found_{cleaned_title}_{date_str}.pdf"
                    fallback_path = press_releases_dir / fallback_filename
                    self._create_not_found_pdf(fallback_path, press_release_title, date_issued)
                    pdf_path = fallback_path
                    pdf_saved = True
                    extracted_text = "Page not found for this press release"
            
            if not pdf_saved:
                # Fallback PDF with press release info
                self._create_fallback_press_release_pdf(pdf_path, press_release_title, date_issued)
                logging.info(f"Saved fallback press release PDF: {pdf_path}")
                extracted_text = f"Press Release Title: {press_release_title}\nDate: {date_issued}"
            
            # Insert into DB with extracted text and new columns
            self._insert_db(
                fields={"Date": date_issued},
                pdf_path=str(pdf_path),
                entry_type='press_release',
                press_release_title=press_release_title,
                press_release_date=date_issued,
                pdf_public_link=pdf_public_url,
                all_text=extracted_text
            )

    def _create_press_release_pdf_from_html(self, pdf_path, title, date_issued, soup):
        """Create PDF from HTML content of press release detail page"""
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=to_latin1(f"FDA Ghana Press Release - {date_issued}"), ln=True, align="C")
        pdf.ln(5)
        pdf.set_font("Arial", "B", 14)
        pdf.multi_cell(0, 10, to_latin1(title))
        pdf.ln(5)
        
        # Extract main content
        content_div = soup.find("div", class_="entry-content") or soup.find("div", class_="content") or soup.find("main")
        if content_div:
            text_content = content_div.get_text(separator="\n", strip=True)
            pdf.set_font("Arial", size=10)
            # Clean and limit content
            lines = text_content.split("\n")[:50]  # Limit lines
            for line in lines:
                if line.strip():
                    pdf.multi_cell(0, 5, to_latin1(line.strip()[:100]))
        
        pdf.output(str(pdf_path))
        
    def _create_not_found_pdf(self, pdf_path, title, date_issued):
        """Create PDF for press release with 404/not found error"""
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=to_latin1(f"FDA Ghana Press Release - {date_issued}"), ln=True, align="C")
        pdf.ln(10)
        pdf.set_font("Arial", "B", 14)
        pdf.multi_cell(0, 10, to_latin1(title))
        pdf.ln(10)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 8, "Page not found for this press release")
        pdf.ln(5)
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 8, f"Date: {date_issued}")
        pdf.multi_cell(0, 8, "The linked PDF could not be accessed at this time.")
        pdf.output(str(pdf_path))
        
    def _create_fallback_press_release_pdf(self, pdf_path, title, date_issued):
        """Create fallback PDF for press release"""
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=to_latin1(f"FDA Ghana Press Release - {date_issued}"), ln=True, align="C")
        pdf.ln(10)
        pdf.set_font("Arial", "B", 14)
        pdf.multi_cell(0, 10, to_latin1(title))
        pdf.ln(5)
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 8, "Press release details were not directly accessible from the FDA Ghana website.")
        pdf.multi_cell(0, 8, f"Date: {date_issued}")
        pdf.output(str(pdf_path))

    def run(self):
        logging.info("Starting FDA Ghana Recall Scraper...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            try:
                page.goto(self.BASE_URL, timeout=60000)
                page.wait_for_load_state("networkidle")
                # Handle pagination: set filter to 'All' if possible
                try:
                    # Find the correct select for 'Show entries' (by label or proximity to table)
                    selects = page.query_selector_all('label select, select')
                    select = None
                    for s in selects:
                        label = s.evaluate('el => el.parentElement && el.parentElement.textContent')
                        if label and ("show" in label.lower() and "entries" in label.lower()):
                            select = s
                            break
                    if not select and selects:
                        select = selects[0]
                    if select:
                        options = select.query_selector_all("option")
                        all_option = None
                        max_val = 10
                        for option in options:
                            text = option.inner_text().strip().lower()
                            if text in ["all", "view all", "show all"]:
                                all_option = option
                            elif text.isdigit() and int(text) > max_val:
                                max_val = int(text)
                        if all_option:
                            select.select_option(value=all_option.get_attribute("value"))
                        else:
                            select.select_option(label=str(max_val))
                        # Wait for table to update: wait for more than 11 rows
                        page.wait_for_timeout(2000)
                        # Optionally, wait for table to have more than 11 rows
                        page.wait_for_function('() => document.querySelectorAll("table tbody tr").length > 11', timeout=10000)
                except Exception as e:
                    logging.warning(f"Could not set pagination to all: {e}")
                html = page.content()
            except PlaywrightTimeoutError:
                logging.error(f"Timeout loading {self.BASE_URL}")
                return
            except Exception as e:
                logging.error(f"Error loading {self.BASE_URL}: {e}")
                return
            finally:
                browser.close()
        soup = BeautifulSoup(html, "html.parser")
        table = self._find_main_table(soup)
        if not table:
            logging.error("Could not find main recall table on the page.")
            return
        rows = table.find_all("tr")[1:]  # skip header
        logging.info(f"Found {len(rows)} recall entries.")
        for row in tqdm(rows, desc="Processing recalls"):
            self._process_row(row)
        logging.info("Scraping complete.")

    def _find_main_table(self, soup: BeautifulSoup):
        # Try to find the main recall table by heuristics
        tables = soup.find_all("table")
        for table in tables:
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
            if "product name" in headers and "date recall was issued" in headers:
                return table
        return None

    def _process_row(self, row):
        cols = row.find_all(["td", "th"])
        fields = {
            "Date Recall was Issued": cols[0].get_text(strip=True) if len(cols) > 0 else "",
            "Product Name": cols[1].get_text(strip=True) if len(cols) > 1 else "",
            "Product Type": cols[2].get_text(strip=True) if len(cols) > 2 else "",
            "Manufacturer": cols[3].get_text(strip=True) if len(cols) > 3 else "",
            "Recalling Firm": cols[4].get_text(strip=True) if len(cols) > 4 else "",
            "Batch(es)": cols[5].get_text(strip=True) if len(cols) > 5 else "",
            "Manufacturing Date": cols[6].get_text(strip=True) if len(cols) > 6 else "",
            "Expiry Date": cols[7].get_text(strip=True) if len(cols) > 7 else "",
        }
        product_name = clean_filename(fields["Product Name"] or "Unknown_Product")
        link = cols[1].find("a")
        if link and link.has_attr("href"):
            href = link["href"]
            self._handle_redirect(href, product_name, fields)
        else:
            # No link, just save fallback PDF
            self._save_fallback_pdf(product_name, fields, reason=None, error="No detail link found.")

    def _handle_redirect(self, href: str, product_name: str, fields: Dict[str, str]):
        if href.lower().endswith(".pdf"):
            self._download_pdf(href, product_name)
        else:
            self._scrape_detail_page(href, product_name, fields)

    def _download_pdf(self, url: str, product_name: str):
        try:
            if not url.startswith("http"):
                url = requests.compat.urljoin(self.BASE_URL, url)
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            out_dir = self.output_dir / product_name
            out_dir.mkdir(parents=True, exist_ok=True)
            filename = url.split("/")[-1]
            out_path = out_dir / filename
            with open(out_path, "wb") as f:
                f.write(resp.content)
            logging.info(f"Downloaded PDF for {product_name}: {out_path}")
        except Exception as e:
            logging.error(f"Failed to download PDF for {product_name}: {e}")

    def _scrape_detail_page(self, url: str, group_folder: str, summary_fields: Dict[str, str]):
        try:
            if not url.startswith("http"):
                url = requests.compat.urljoin(self.BASE_URL, url)
            resp = self.session.get(url, timeout=30)
            if resp.status_code == 404:
                self._save_fallback_pdf(group_folder, summary_fields, reason=None, error="404 Not Found")
                return
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            # Try to extract reason for recall
            reason = self._extract_reason(soup)
            # Check for tables with multiple products
            tables = soup.find_all("table")
            if tables:
                for table in tables:
                    self._extract_table_products(table, group_folder, summary_fields, reason)
            else:
                # Single product, generate PDF
                self._save_fallback_pdf(group_folder, summary_fields, reason=reason)
        except Exception as e:
            logging.error(f"Failed to scrape detail page for {group_folder}: {e}")
            self._save_fallback_pdf(group_folder, summary_fields, reason=None, error=str(e))

    def _extract_reason(self, soup: BeautifulSoup) -> Optional[str]:
        # Try to find a reason for recall in the page, robustly and precisely
        reason_labels = ["reason for recall", "recall reason", "reason"]
        # 1. Look for a <th> or <td> with a reason label and get only the next cell
        for label in reason_labels:
            ths = soup.find_all(lambda tag: tag.name in ["th", "td"] and label in tag.get_text(strip=True).lower())
            for th in ths:
                td = th.find_next_sibling(["td", "th"])
                if td:
                    reason_text = td.get_text(separator=" ", strip=True)
                    # Only accept if it's not too long and doesn't contain unrelated content
                    if reason_text and not re.search(r"privacy|policy|footer|copyright", reason_text, re.I) and len(reason_text) < 500:
                        return reason_text
        # 2. Look for paragraphs/divs with reason label, but only extract the part after the label
        for label in reason_labels:
            ps = soup.find_all(lambda tag: tag.name in ["p", "div"] and label in tag.get_text(strip=True).lower())
            for p in ps:
                text = p.get_text(separator=" ", strip=True)
                idx = text.lower().find(label)
                if idx != -1:
                    reason_text = text[idx+len(label):].strip(" :-")
                    if reason_text and not re.search(r"privacy|policy|footer|copyright", reason_text, re.I) and len(reason_text) < 500:
                        return reason_text
        # 3. Fallback: search for any text node with the label, but only extract the part after the label
        for label in reason_labels:
            el = soup.find(string=re.compile(label, re.I))
            if el:
                text = el.strip()
                idx = text.lower().find(label)
                if idx != -1:
                    reason_text = text[idx+len(label):].strip(" :-")
                    if reason_text and not re.search(r"privacy|policy|footer|copyright", reason_text, re.I) and len(reason_text) < 500:
                        return reason_text
        return None

    def _extract_table_products(self, table, group_folder, summary_fields, reason):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        for row in table.find_all("tr")[1:]:
            cols = row.find_all(["td", "th"])
            # Start with summary fields, but override with row fields for product-specific data
            fields = summary_fields.copy()
            for i, col in enumerate(cols):
                if i < len(headers):
                    col_val = col.get_text(strip=True)
                    header = headers[i]
                    # Map table headers to correct PDF fields
                    if header.lower() in ["product description", "product name"]:
                        fields["Product Name"] = col_val
                    elif header.lower() in ["batch(es)", "batch numbers", "batch number"]:
                        fields["Batch(es)"] = col_val
                    elif header.lower() in ["manufacturing date", "manufacturing dates"]:
                        fields["Manufacturing Date"] = col_val
                    elif header.lower() in ["expiry date", "expiry dates"]:
                        fields["Expiry Date"] = col_val
                    else:
                        fields[header] = col_val
            if reason:
                fields["Reason for Recall"] = reason
            prod_name = clean_filename(fields.get("Product Name") or group_folder)
            pdf_name = f"Recall_Summary_{prod_name}.pdf"
            out_path = self.output_dir / group_folder / pdf_name
            save_pdf(out_path, f"Recall Summary: {prod_name}", fields)
            logging.info(f"Saved PDF for {prod_name}: {out_path}")
            
            # Create text content from fields
            all_text = f"Recall Summary: {prod_name}\n"
            for key, value in fields.items():
                if value:
                    all_text += f"{key}: {value}\n"
            
            # Insert into DB with extracted text
            self._insert_db(fields, str(out_path), source_url=None, all_text=all_text)

    def _save_fallback_pdf(self, product_name, fields, reason=None, error=None):
        if reason:
            fields["Reason for Recall"] = reason
        # Only include error if it's a real HTTP error, not a parsing/Unicode error
        if error and ("404" in str(error) or "not found" in str(error).lower()):
            fields["Error"] = error
        elif "Error" in fields:
            del fields["Error"]
        pdf_name = f"Recall_Summary_{product_name}.pdf"
        out_path = self.output_dir / product_name / pdf_name
        save_pdf(out_path, f"Recall Summary: {product_name}", fields)
        logging.info(f"Saved fallback PDF for {product_name}: {out_path}")
        
        # Create text content from fields
        all_text = f"Recall Summary: {product_name}\n"
        for key, value in fields.items():
            if value:
                all_text += f"{key}: {value}\n"
        
        # Insert into DB with extracted text
        self._insert_db(fields, str(out_path), source_url=None, all_text=all_text)



def parse_args():
    parser = argparse.ArgumentParser(description="FDA Ghana Recall, Alert & Press Release Scraper CLI")
    parser.add_argument("--output-dir", type=str, default="./recalls", help="Output directory for recall/alert PDFs")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser in headless mode (default: True)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--skip-recalls", action="store_true", help="Skip scraping recalls")
    parser.add_argument("--skip-alerts", action="store_true", help="Skip scraping alerts")
    parser.add_argument("--skip-press", action="store_true", help="Skip scraping press releases")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    output_dir = Path(args.output_dir)
    scraper = FDARecallScraper(output_dir=output_dir, headless=args.headless, verbose=args.verbose)
    
    if not args.skip_recalls:
        scraper.run()
    
    if not args.skip_alerts:
        scraper.scrape_alerts()
    
    if not args.skip_press:
        scraper.scrape_press_releases()
        
    logging.info("FDA Ghana scraping complete for all enabled sections.")
