import os
import re
import csv
import time
import json
import base64
import requests
import urllib3
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import msvcrt

# Disable insecure request warnings from urllib3 when using verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DOWNLOAD_DIR = "downloads"
CSV_FILE = os.path.join("csv_raw", "tram_thu_phi.csv")
PROGRESS_FILE = "crawled_progress.json"
MAPS_ZOOM = "17z" # 2D Map Zoom. Default is 3z. Use 17z or 18z to zoom in close to the streets.

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"completed_urls": []}

def save_progress(progress):
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[Crawler] Error saving progress: {e}")

def sanitize_filename(filename, max_length=150):
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', filename)
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    return sanitized

def extract_panoid(url):
    match = re.search(r'panoid=([a-zA-Z0-9_\-]+)', url)
    if match:
        return match.group(1)
    return None

def extract_params(url):
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return {k: v[0] for k, v in params.items()}

def save_data(filepath, content):
    if not content:
        return False
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(content)
        print(f"[Downloader] Saved: {filepath}")
        return True
    except Exception as e:
        print(f"[Downloader] Error saving file to {filepath}: {e}")
    return False

def fetch_body_via_cdp(driver, request_id):
    try:
        res = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
        body = res.get('body', '')
        is_base64 = res.get('base64Encoded', False)
        if is_base64:
            return base64.b64decode(body)
        else:
            return body.encode('utf-8') if isinstance(body, str) else body
    except Exception:
        return None

def download_url_via_requests(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
        "Referer": "https://www.google.com/"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.content
        else:
            print(f"[Downloader] Failed to fetch {url[:60]}... Status: {response.status_code}")
    except Exception as e:
        print(f"[Downloader] Error fetching url {url[:60]}... : {e}")
    return None

def handle_cookie_consent(driver):
    try:
        current_url = driver.current_url
    except Exception:
        return False
    if "consent.google.com" in current_url:
        print("[Crawler] Google Cookie Consent Page detected. Attempting to accept cookies automatically...")
        time.sleep(2)
        selectors = [
            "//button[contains(text(), 'Godta alle')]",
            "//button[contains(text(), 'Accept all')]",
            "//button[contains(text(), 'Đồng ý')]",
            "//button[contains(text(), 'Tôi đồng ý')]",
            "//button[contains(text(), 'I agree')]",
            "//button[contains(text(), 'Agree')]",
            "button.QS5gu.sy4vM",
            "form button"
        ]
        for sel in selectors:
            try:
                if sel.startswith("//"):
                    btn = driver.find_element("xpath", sel)
                else:
                    btn = driver.find_element("css selector", sel)
                
                if btn.is_displayed():
                    btn.click()
                    print(f"[Crawler] Clicked consent button via: {sel}")
                    time.sleep(2)
                    return True
            except Exception:
                pass
        print("[Crawler] Automatic consent click failed. Please click 'Accept all' / 'Godta alle' manually in the Chrome window.")
    return False

def download_all_pano_tiles(panoid, zooms=[3, 4]):
    # 1. Download thumbnail first
    thumbnail_url = f"https://streetviewpixels-pa.googleapis.com/v1/thumbnail?panoid={panoid}&cb_client=search.gws-prod.gps&w=400&h=300"
    thumbnail_path = os.path.join(DOWNLOAD_DIR, panoid, "thumbnail.jpg")
    if not os.path.exists(thumbnail_path):
        content = download_url_via_requests(thumbnail_url)
        if content:
            save_data(thumbnail_path, content)
            print(f"[Downloader] Downloaded thumbnail for {panoid}")

    # 2. Download grid of tiles
    for zoom in zooms:
        width = 2 ** zoom
        height = max(1, 2 ** (zoom - 1))
        
        print(f"[Downloader] Downloading Pano ID {panoid} at zoom {zoom} ({width}x{height} tiles)...")
        tiles_saved = 0
        for x in range(width):
            for y in range(height):
                filepath = os.path.join(DOWNLOAD_DIR, panoid, f"zoom_{zoom}", f"tile_{x}_{y}.jpg")
                if os.path.exists(filepath):
                    continue
                
                url = f"https://streetviewpixels-pa.googleapis.com/v1/tile?cb_client=maps_sv.tactile&panoid={panoid}&x={x}&y={y}&zoom={zoom}&nbt=1&fover=2"
                content = download_url_via_requests(url)
                if content:
                    if save_data(filepath, content):
                        tiles_saved += 1
                        time.sleep(0.05) # Small cooldown between tile requests to prevent proxy bans
        if tiles_saved > 0:
            print(f"[Downloader] Successfully downloaded {tiles_saved} tiles for {panoid} at zoom {zoom}")

def main():
    if not os.path.exists(CSV_FILE):
        print(f"[Crawler] Error: CSV file '{CSV_FILE}' not found.")
        return

    # Load progress
    progress = load_progress()
    completed_urls = set(progress.get("completed_urls", []))

    # 1. Configure Selenium Chrome Options (no proxy)
    options = webdriver.ChromeOptions()
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--allow-insecure-localhost')
    options.add_argument('--start-maximized')

    print("[Crawler] Launching Chrome...")
    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd('Network.enable', {})

    # Read rows from CSV
    rows_to_process = []
    with open(CSV_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows_to_process.append(row)

    print(f"[Crawler] Found {len(rows_to_process)} locations in CSV. Starting process...")

    try:
        for idx, row in enumerate(rows_to_process, 1):
            name = row.get("google_name")
            lat = row.get("google_latitude")
            lng = row.get("google_longitude")
            map_url = row.get("google_maps_url")

            if not lat or not lng or not map_url:
                continue

            if map_url in completed_urls:
                # print(f"[Crawler] [{idx}/{len(rows_to_process)}] Skipping already completed location: {name}")
                continue

            print("\n" + "="*80)
            print(f"[{idx}/{len(rows_to_process)}] PROCESSING LOCATION: {name}")
            print(f"Coordinates: {lat}, {lng}")
            print("="*80)

            # Build direct 2D map coordinate URL at high zoom
            sv_url = f"https://www.google.com/maps/@{lat},{lng},{MAPS_ZOOM}"
            print(f"[Crawler] Loading Google Maps: {sv_url}")
            driver.get(sv_url)
            handle_cookie_consent(driver)

            # Focus browser body to allow keyboard arrow keys
            try:
                time.sleep(3)
                body = driver.find_element("tag name", "body")
                body.click()
            except Exception:
                pass

            current_row_panoids = set()
            start_time = time.time()

            print("[Crawler] Manual interaction enabled. Please locate the 360 Panorama in Chrome.")
            print("          Press ENTER or SPACE key in this terminal to skip to the next location manually.")

            # Navigation Loop: Wait for manual user interactions and count pano IDs
            while len(current_row_panoids) < 5:
                time.sleep(0.5)
                try:
                    curr_url = driver.current_url
                except Exception:
                    curr_url = ""
                if "consent.google.com" in curr_url:
                    handle_cookie_consent(driver)
                
                # Extract Pano ID directly from the active browser URL (highly reliable as user moves)
                if "google.com/maps" in curr_url:
                    match = re.search(r'!1s([a-zA-Z0-9_\-]{22})(?:!2e|/|\b)', curr_url)
                    if match:
                        panoid = match.group(1)
                        if panoid not in current_row_panoids:
                            current_row_panoids.add(panoid)
                            print(f"[Crawler] Discovered Pano ID from browser URL: {panoid} (Total: {len(current_row_panoids)}/5)")

                # Check for manual skip keys in terminal
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key in [b'\r', b'\n', b' ']:
                        print("\n[Crawler] Skip key detected. Moving to next location...")
                        break

                # Read performance logs to find intercepted Pano IDs
                try:
                    logs = driver.get_log("performance")
                except Exception:
                    # Browser window closed
                    break

                for entry in logs:
                    try:
                        log_message = json.loads(entry["message"])["message"]
                        method = log_message.get("method")
                        if method == "Network.requestWillBeSent":
                            url = log_message.get("params", {}).get("request", {}).get("url", "")
                            
                            # Filter and save protobuf streams on the fly
                            if "google.com/maps/vt/stream" in url and "pb=" in url:
                                params_dict = extract_params(url)
                                pb_val = params_dict.get("pb", "")
                                if pb_val:
                                    filename = f"pb_{sanitize_filename(pb_val)}.bin"
                                    filepath = os.path.join(DOWNLOAD_DIR, "metadata", filename)
                                    if not os.path.exists(filepath):
                                        req_id = log_message.get("params", {}).get("requestId")
                                        content = fetch_body_via_cdp(driver, req_id)
                                        if not content:
                                            content = download_url_via_requests(url)
                                        if content:
                                            save_data(filepath, content)

                            # Identify Pano IDs from streetview tile/thumbnail requests
                            if "streetviewpixels-pa.googleapis.com" in url:
                                panoid = extract_panoid(url)
                                if panoid and panoid not in current_row_panoids:
                                    current_row_panoids.add(panoid)
                                    print(f"[Crawler] Discovered Pano ID: {panoid} (Total: {len(current_row_panoids)}/5)")
                    except Exception:
                        pass

                # Check if we have collected 5 unique Pano IDs
                if len(current_row_panoids) >= 5:
                    print(f"\n[Crawler] Successfully collected 5 unique Pano IDs: {list(current_row_panoids)}")
                    for countdown in range(5, 0, -1):
                        print(f"[Crawler] Switching to next location in {countdown} seconds...", end="\r")
                        time.sleep(1.0)
                    print("\n[Crawler] Transitioning...")
                    break

            # 4. Trigger download grid API for all collected Pano IDs at this location
            if current_row_panoids:
                print(f"[Crawler] Starting grid downloads for {len(current_row_panoids)} Pano IDs...")
                for p_id in current_row_panoids:
                    download_all_pano_tiles(p_id, zooms=[3, 4])
            
            # Save progress
            completed_urls.add(map_url)
            progress["completed_urls"] = list(completed_urls)
            save_progress(progress)

    except KeyboardInterrupt:
        print("[Crawler] Process stopped by user.")
    finally:
        print("[Crawler] Cleaning up resources...")
        try:
            driver.quit()
        except Exception:
            pass
        print("[Crawler] Terminated.")

if __name__ == "__main__":
    main()
