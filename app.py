from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS, cross_origin
from bs4 import BeautifulSoup as bs
import csv, os, time, re
# import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)
CORS(app)

CSV_FOLDER = "csv_exports"
os.makedirs(CSV_FOLDER, exist_ok=True)


def get_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    import os
    
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-dev-tools")
    options.add_argument("--disable-crash-reporter")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-in-process-stack-traces")
    options.add_argument("--disable-logging")
    options.add_argument("--log-level=3")
    
    # Set Chrome binary location
    chrome_bin = os.environ.get('CHROME_BIN', '/usr/bin/chromium-browser')
    options.binary_location = chrome_bin
    
    # Set ChromeDriver path
    chromedriver_path = os.environ.get('CHROMEDRIVER_PATH', '/usr/local/bin/chromedriver')
    
    try:
        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(60)
        return driver
    except Exception as e:
        print(f"Error creating driver: {e}")
        # Fallback: try without specifying path (let selenium find it)
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)
        return driver

        
def safe_get(driver, url, timeout=30):
    try:
        driver.get(url)
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(2)
        return True
    except:
        return False


def dismiss_popup(driver):
    for xpath in ["//button[contains(text(),'✕')]", "//button[contains(@class,'_2KpZ6l')]"]:
        try:
            btn = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.XPATH, xpath)))
            btn.click()
            time.sleep(1)
            break
        except:
            pass


def find_product_url(soup):
    for a in soup.find_all("a", href=True):
        href = a['href']
        if '/p/' in href and href.startswith('/'):
            return "https://www.flipkart.com" + href.split('?')[0]
    return None


def parse_reviews(html):
    """
    Parse reviews from the new Flipkart reviews page structure.
    Customer name pattern: text content followed by ", Location"
    Review comment: in <span class="css-1qaijid">
    """
    soup = bs(html, "html.parser")
    results = []
    seen = set()

    print(f"  Page HTML length: {len(html)} chars")

    # Strategy 1: Find "Verified Purchase" text nodes (each review has this)
    verified_nodes = soup.find_all(string=lambda t: t and 'Verified Purchase' in str(t))
    print(f"  Found {len(verified_nodes)} 'Verified Purchase' mentions")

    for vnode in verified_nodes:
        # Walk up to find the review container (usually 10-15 levels up)
        container = vnode.parent
        for _ in range(15):
            if container is None: break
            container = container.parent
            if container and container.name == 'div':
                text_len = len(container.get_text(strip=True))
                # Review containers are typically 200-3000 chars
                if 150 < text_len < 4000:
                    # Check if it contains rating/comment indicators
                    text = container.get_text()
                    if any(keyword in text for keyword in ['Helpful', 'Gold Reviewer', 'Silver Reviewer', 'Bronze Reviewer', 'Wonderful', 'Excellent']):
                        break

        if not container:
            continue

        # ---- Extract CUSTOMER NAME ----
        # Strategy 1: Look for text that appears right before ", Location"
        name = 'Anonymous'
        full_text = container.get_text(separator=' ', strip=True)
        
        # Pattern: "FirstName LastName , Location" where Location starts with capital letter
        # Example: "Abhishek Maurya , Jaunpur"
        import re
        name_location_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s*,\s*[A-Z][a-z]+'
        matches = re.findall(name_location_pattern, full_text)
        
        if matches:
            # Filter out common noise words
            noise_words = {'Helpful', 'Review', 'Gold', 'Silver', 'Bronze', 'Verified', 'Purchase'}
            for match in matches:
                if not any(noise in match for noise in noise_words):
                    name = match.strip()
                    break
        
        # Strategy 2: If regex fails, look for divs with customer name styling
        if name == 'Anonymous':
            name_divs = container.find_all('div', {'class': 'css-1rynq56'})
            for div in name_divs:
                text = div.get_text(strip=True)
                # Name should be 5-40 chars, no special keywords, has space (FirstName LastName)
                if (5 < len(text) < 40
                        and ' ' in text
                        and text[0].isupper()
                        and 'Reviewer' not in text
                        and 'ago' not in text
                        and 'Helpful' not in text
                        and 'Review' not in text):
                    # Check if followed by comma and location
                    parent_text = div.parent.get_text() if div.parent else ''
                    if ',' in parent_text:
                        name = text.strip()
                        break

        # ---- Extract COMMENT ----
        # Comment is in <span class="css-1qaijid">
        comment = None
        comment_spans = container.find_all('span', {'class': 'css-1qaijid'})
        for span in comment_spans:
            text = span.get_text(strip=True)
            if len(text) > 20:
                comment = text
                break

        # Fallback: Look for longest text block
        if not comment:
            segments = [s.strip() for s in full_text.split('|') if s.strip()]
            noise = {'Helpful', 'Verified Purchase', 'Gold Reviewer', 'Silver Reviewer', 'Bronze Reviewer', 'ago', 'months', 'days', 'Wonderful', 'Excellent', 'Good', 'Average', 'Poor'}
            best = ''
            for seg in segments:
                if (len(seg) > len(best)
                        and 30 < len(seg) < 1500
                        and not any(n in seg for n in noise)
                        and not seg[0].isdigit()):
                    best = seg
            if best:
                comment = best

        if not comment or len(comment) < 20:
            continue

        # Deduplicate
        key = comment.strip().lower()[:80]
        if key in seen:
            continue
        seen.add(key)

        results.append({'customer_name': name, 'comment': comment})
        print(f"  ✓ {name} | {comment[:60]}")

    return results


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/scrape', methods=['POST'])
@cross_origin()
def scrape():
    data = request.get_json()
    query = data.get('query', '').strip().replace(' ', '')
    if not query:
        return jsonify({'error': 'Please enter a product name'}), 400

    driver = None
    try:
        print(f"\n{'='*52}")
        print(f"[1] Query: {query}")
        driver = get_driver()

        # Homepage
        print(f"[1] Homepage...")
        safe_get(driver, "https://www.flipkart.com", timeout=20)
        dismiss_popup(driver)
        time.sleep(2)

        # Search
        print(f"[2] Searching...")
        safe_get(driver, f"https://www.flipkart.com/search?q={query}")
        dismiss_popup(driver)
        time.sleep(2)

        # Get product URL
        print(f"[3] Finding product...")
        product_url = None
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(@href,'/p/')]"))
            )
            links = driver.find_elements(By.XPATH, "//a[contains(@href,'/p/')]")
            if links:
                product_url = links[0].get_attribute('href')
                print(f"    URL: {product_url[:80]}")
        except:
            soup_tmp = bs(driver.page_source, "html.parser")
            product_url = find_product_url(soup_tmp)

        if not product_url:
            driver.quit()
            return jsonify({'error': 'No product found.'}), 404

        # Load product page briefly
        print(f"[4] Loading product page...")
        time.sleep(2)
        safe_get(driver, product_url, timeout=30)
        dismiss_popup(driver)

        # Build reviews URL
        print(f"[5] Building reviews URL...")
        product_id_match = re.search(r'/p/([^?]+)', product_url)
        
        if product_id_match:
            product_id = product_id_match.group(1)
            # Extract pid, lid, marketplace from product URL
            params = {}
            for param in ['pid', 'lid', 'marketplace']:
                match = re.search(rf'{param}=([^&]+)', product_url)
                if match:
                    params[param] = match.group(1)
            
            # Construct reviews URL
            reviews_url = product_url.split('/p/')[0] + f'/product-reviews/{product_id}'
            if params:
                query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
                reviews_url += '?' + query_string
            
            print(f"    Reviews URL: {reviews_url[:90]}")
            
            # Navigate to reviews page
            print(f"[6] Loading reviews page...")
            time.sleep(2)
            safe_get(driver, reviews_url, timeout=30)
            dismiss_popup(driver)
            print(f"    Title: {driver.title[:70]}")
            
            # Scroll to load all reviews
            print(f"[7] Scrolling to load reviews...")
            for i in range(30):
                driver.execute_script("window.scrollBy(0, 700);")
                time.sleep(1)
            
            # Extra scroll
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Count verified purchases
            verified_count = driver.page_source.count('Verified Purchase')
            print(f"    Found {verified_count} 'Verified Purchase' mentions")
        else:
            driver.quit()
            return jsonify({'error': 'Could not parse product ID from URL.'}), 500

        # Parse
        print(f"[8] Parsing reviews...")
        reviews = parse_reviews(driver.page_source)

        driver.quit()
        driver = None

        if not reviews:
            return jsonify({'error': 'No reviews found. Try a more popular product.'}), 404

        print(f"[9] Total: {len(reviews)} reviews")

        # Save CSV
        filename = f"{query}_reviews.csv"
        filepath = os.path.join(CSV_FOLDER, filename)
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['customer_name', 'comment'])
            writer.writeheader()
            writer.writerows(reviews)
        print(f"[10] Saved: {filepath}")

        return jsonify({'success': True, 'count': len(reviews), 'reviews': reviews, 'filename': filename})

    except Exception as e:
        if driver:
            try: driver.quit()
            except: pass
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/download/<filename>')
def download(filename):
    filepath = os.path.join(CSV_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, mimetype='text/csv')
    return jsonify({'error': 'File not found'}), 404


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
