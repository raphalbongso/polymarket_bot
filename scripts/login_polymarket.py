"""Open Chrome zodat je kunt inloggen op Polymarket."""
import os
import sys
import time
import json

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

print()
print("  ========================================")
print("  POLYMARKET LOGIN")
print("  ========================================")
print()
print("  Chrome opent zo. Log in op Polymarket.")
print("  Sluit dit venster als je klaar bent.")
print()

opts = Options()
opts.add_argument("--user-data-dir=" + os.path.abspath("chrome_profile_bot"))
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--disable-blink-features=AutomationControlled")
opts.add_experimental_option("excludeSwitches", ["enable-automation"])
opts.add_experimental_option("useAutomationExtension", False)
opts.add_argument("--window-size=1400,900")

driver = webdriver.Chrome(options=opts)
driver.execute_cdp_cmd(
    "Page.addScriptToEvaluateOnNewDocument",
    {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
)
driver.get("https://polymarket.com")
print("  Chrome is open. Log in en druk ENTER als je klaar bent...")

input()

# Save cookies
cookies = driver.get_cookies()
os.makedirs("cookies", exist_ok=True)
with open("cookies/polymarket_cookies.json", "w") as f:
    json.dump(cookies, f)
print(f"  {len(cookies)} cookies opgeslagen!")

driver.quit()
print("  Klaar!")
