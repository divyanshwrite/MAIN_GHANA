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

    def __init__(self, output_dir: Path, headless: bool = True, verbose: bool = False):
        self.output_dir = output_dir
        self.headless = headless
        self.verbose = verbose
        setup_logging(verbose, output_dir)
        self.session = requests.Session()
        # DB connection params (edit as needed or use env vars)
        self.db_params = {
            'dbname': os.environ.get('FDA_DB_NAME', 'main'),
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

    def _insert_db(self, fields: dict, pdf_path: str, source_url: str = None):
        if not self.db_conn:
            return
        def parse_date(val):
            if not val:
                return None
            val = val.strip()
            # Try DD/MM/YYYY or DD-MM-YYYY
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"):
                try:
                    return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
                except Exception:
                    continue
            # If only year, or year-month
            for fmt in ("%Y", "%Y-%m"):
                try:
                    return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
                except Exception:
                    continue
            return None
        try:
            with self.db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    INSERT INTO public.fda_recalls (
                        date_recall_issued, product_name, product_type, manufacturer, recalling_firm,
                        batch_numbers, manufacturing_date, expiry_date, reason_for_recall, source_url, pdf_path
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    pdf_path
                ])
                self.db_conn.commit()
        except Exception as e:
            logging.error(f"Failed to insert into DB: {e}")
            try:
                self.db_conn.rollback()
            except Exception:
                pass

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
            # Insert into DB
            self._insert_db(fields, str(out_path), source_url=None)

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
        # Insert into DB
        self._insert_db(fields, str(out_path), source_url=None)


def parse_args():
    parser = argparse.ArgumentParser(description="FDA Ghana Recall Scraper CLI")
    parser.add_argument("--output-dir", type=str, default="./recalls", help="Output directory for recall PDFs")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser in headless mode (default: True)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    output_dir = Path(args.output_dir)
    scraper = FDARecallScraper(output_dir=output_dir, headless=args.headless, verbose=args.verbose)
    scraper.run()
