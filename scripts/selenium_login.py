"""Standalone script: open browser, log in manually, save cookies.

Usage:
    python scripts/selenium_login.py

Opens a Chrome window on polymarket.com. Log in manually (email + magic link).
Once logged in, cookies are saved for the bot to reuse.
"""
import os
import sys
import time

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.settings import load_settings
from bot.selenium_auth import save_cookies

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def main():
    settings = load_settings()
    cookie_file = settings.selenium_cookie_file
    base_url = settings.selenium_base_url

    print(f"Cookie file: {cookie_file}")
    print(f"Base URL:    {base_url}")
    print()

    options = Options()
    # Use persistent profile if configured
    if settings.selenium_chrome_profile_dir:
        profile_dir = os.path.abspath(settings.selenium_chrome_profile_dir)
        options.add_argument(f"--user-data-dir={profile_dir}")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,900")

    # Anti-detection flags (match selenium_executor.py)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)

    # Remove webdriver flag to reduce detection
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )

    try:
        driver.get(f"{base_url}/login")
        print("Browser opened. Please log in manually.")
        print("  1. Enter your email address")
        print("  2. Click the magic link in your inbox")
        print("  3. Wait for the dashboard to load")
        print()

        # Poll until URL changes away from /login or user confirms
        max_wait = 300  # 5 minutes
        start = time.time()
        while time.time() - start < max_wait:
            try:
                current_url = driver.current_url
            except Exception:
                print("Browser was closed manually.")
                return
            # Logged in if we're no longer on /login
            if "/login" not in current_url and base_url in current_url:
                print(f"Login detected! Current URL: {current_url}")
                break
            time.sleep(2)
        else:
            print(f"Timeout after {max_wait}s. Saving cookies anyway.")

        save_cookies(driver, cookie_file)
        print(f"\nCookies saved to {cookie_file}")
        print("You can now start the bot with TRADING_MODE=selenium")

        # Keep browser open briefly so user can verify
        print("\nBrowser will close in 5 seconds...")
        time.sleep(5)

    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
