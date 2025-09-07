# FDA Ghana Recall Scraper

A CLI tool to scrape all product recall entries from the official Ghana Food and Drugs Authority recalls page.

## Features
- Scrapes all recall entries from https://fdaghana.gov.gh/newsroom/product-recalls-and-alerts/
- Handles PDF and webpage recall details, downloads or generates PDFs per product
- Handles broken/missing pages and logs errors
- Organizes output by product name
- CLI with progress bar, headless mode, output directory, and verbose logging

## Usage

```bash
python fda_recall_scraper.py --output-dir ./recalls --headless --verbose
```

### Arguments
- `--output-dir`   Output folder for recall PDFs (default: `./recalls`)
- `--headless`     Run browser in headless mode (default: True)
- `--verbose`      Enable verbose logging

## Requirements
- Python 3.10+
- See `requirements.txt`

Install dependencies:

```bash
pip install -r requirements.txt
playwright install
```

## Future Scope
- Database upload
- Scheduling/automation
- Email error reports
