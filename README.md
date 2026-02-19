# Flipkart Review Scraper — Dark Edition

A Flask + Selenium app that scrapes Flipkart product reviews and saves them to CSV.

## Structure
```
flipkart_dark/
├── app.py               # Flask backend + Selenium scraper
├── requirements.txt     # Dependencies
├── templates/
│   └── index.html       # Dark theme frontend
└── csv_exports/         # Auto-created, stores scraped CSVs
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run
python app.py

# 3. Open browser
http://127.0.0.1:8000
```

## How it works
1. Enter a product name (e.g. "iPhone 15 Plus")
2. Selenium launches headless Chrome, searches Flipkart, finds first product
3. Scrapes all review comments from the product page
4. Displays reviews as cards in the dark UI
5. Saves all reviews to `csv_exports/<product>_reviews.csv`
6. Click "Download CSV" to save the file

## CSV columns
| Column        | Description              |
|---------------|--------------------------|
| product       | Search term used         |
| customer_name | Reviewer's name          |
| rating        | Star rating (1–5)        |
| comment       | Full review comment text |

## Notes
- Chrome must be installed
- chromedriver is auto-managed via webdriver-manager
- If no reviews show, Flipkart may have updated their CSS — check terminal output
