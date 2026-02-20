"""Selenium-based trade executor — places orders via the Polymarket browser UI."""
import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from bot.selenium_auth import save_cookies, load_cookies, extract_magic_link_from_imap
from bot.selenium_pages.login_page import LoginPage
from bot.selenium_pages.market_page import MarketPage
from config.settings import Settings
from monitoring.logger import get_logger

logger = get_logger("selenium.executor")


class SeleniumExecutor:
    """Executes trades on Polymarket using browser automation.

    Lifecycle:
        1. __init__ — launches Chrome, loads cookies, checks login
        2. execute_trade() — called per signal by the orchestrator
        3. close() — saves cookies, quits browser
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._base_url = settings.selenium_base_url
        self._cookie_file = settings.selenium_cookie_file

        # Launch Chrome
        self._driver = self._create_driver()

        # Navigate to domain so cookies can be set
        self._driver.get(self._base_url)
        time.sleep(1)

        # Try to restore session from cookies
        load_cookies(self._driver, self._cookie_file)
        self._driver.refresh()
        time.sleep(2)

        # Page objects
        self._login_page = LoginPage(
            self._driver,
            timeout=settings.selenium_timeout,
            selectors_path=settings.selenium_selectors_file,
        )
        self._market_page = MarketPage(
            self._driver,
            base_url=self._base_url,
            timeout=settings.selenium_timeout,
            selectors_path=settings.selenium_selectors_file,
        )

        # Ensure logged in
        self._ensure_logged_in()
        logger.info("SeleniumExecutor initialized")

    def _create_driver(self):
        """Create and configure a Chrome WebDriver instance."""
        options = Options()

        if self._settings.selenium_headless:
            options.add_argument("--headless=new")

        # Use persistent Chrome profile if configured
        if self._settings.selenium_chrome_profile_dir:
            profile_dir = os.path.abspath(self._settings.selenium_chrome_profile_dir)
            options.add_argument(f"--user-data-dir={profile_dir}")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # Reasonable window size for the trade panel
        options.add_argument("--window-size=1280,900")

        driver = webdriver.Chrome(options=options)

        # Remove webdriver flag to reduce detection
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )

        return driver

    def _ensure_logged_in(self):
        """Check session; if expired, attempt login via cookies or magic link."""
        if self._login_page.is_logged_in():
            logger.info("Session active (cookies valid)")
            return

        logger.info("Session expired — attempting re-login")

        email = self._settings.selenium_email
        if not email:
            logger.error(
                "SELENIUM_EMAIL not configured. Run scripts/selenium_login.py for manual login."
            )
            return

        # Navigate to login page
        self._driver.get(f"{self._base_url}/login")
        time.sleep(2)

        # Enter email to trigger magic link
        self._login_page.login_with_email(email)

        # Attempt automatic magic link extraction via IMAP
        imap_host = self._settings.selenium_imap_host
        imap_user = self._settings.selenium_imap_user
        imap_password = self._settings.selenium_imap_password

        if imap_host and imap_user and imap_password:
            logger.info("Attempting automatic magic link login via IMAP...")
            link = extract_magic_link_from_imap(
                imap_host=imap_host,
                imap_user=imap_user,
                imap_password=imap_password,
                max_wait=90,
            )
            if link:
                self._driver.get(link)
                time.sleep(3)
                if self._login_page.is_logged_in():
                    logger.info("IMAP magic link login successful")
                    save_cookies(self._driver, self._cookie_file)
                    return
                else:
                    logger.warning("Magic link opened but session not active")
            else:
                logger.warning("IMAP magic link extraction failed")

        # Fallback: wait for manual login
        logger.info(
            "Waiting for manual login — click the magic link in your email. "
            f"Timeout: {self._settings.selenium_timeout}s"
        )
        if self._login_page.wait_for_login_complete(timeout=self._settings.selenium_timeout):
            save_cookies(self._driver, self._cookie_file)
        else:
            logger.error("Login timed out. Bot will retry on next trade attempt.")

    def execute_trade(self, signal, size_usd):
        """Execute a single trade via the browser UI.

        Args:
            signal: strategies.base.Signal instance.
                    signal.metadata must contain 'slug' and optionally 'is_yes'.
            size_usd: dollar amount to trade.

        Returns:
            dict with 'success' (bool) and 'message' (str)
        """
        # Verify session is still active
        self._ensure_logged_in()

        slug = signal.metadata.get("slug")
        if not slug:
            logger.error("Signal missing 'slug' in metadata — cannot execute via Selenium")
            return {"success": False, "message": "Missing slug"}

        # Determine outcome side: metadata['is_yes'] or infer from token position
        is_yes = signal.metadata.get("is_yes", True)
        side = signal.side  # "BUY" or "SELL"
        price = signal.suggested_price
        amount = round(size_usd, 2)

        logger.info(
            f"Selenium trade: {side} {'Yes' if is_yes else 'No'} "
            f"@ {price:.4f} ${amount:.2f} on {slug}"
        )

        try:
            result = self._market_page.place_trade(
                slug=slug,
                side=side,
                is_yes=is_yes,
                price=price,
                amount=amount,
            )

            if not result["success"] and self._settings.selenium_screenshot_on_error:
                self._market_page._take_screenshot(f"trade_error_{slug}")

            return result

        except Exception as e:
            logger.error(f"Selenium trade failed: {e}")
            if "tab crashed" in str(e).lower() or "session" in str(e).lower():
                logger.info("Detected browser crash — auto-restarting Chrome...")
                try:
                    self.restart_driver()
                except Exception as re:
                    logger.error(f"Auto-restart failed: {re}")
            else:
                if self._settings.selenium_screenshot_on_error:
                    try:
                        self._market_page._take_screenshot(f"trade_exception_{slug}")
                    except Exception:
                        pass
            return {"success": False, "message": str(e)}

    def restart_driver(self):
        """Save cookies, quit browser, launch a fresh Chrome instance."""
        logger.info("Restarting Chrome to prevent memory leaks...")
        self.close()
        time.sleep(2)

        self._driver = self._create_driver()
        self._driver.get(self._base_url)
        time.sleep(1)

        load_cookies(self._driver, self._cookie_file)
        self._driver.refresh()
        time.sleep(2)

        # Rebuild page objects with new driver
        self._login_page = LoginPage(
            self._driver,
            timeout=self._settings.selenium_timeout,
            selectors_path=self._settings.selenium_selectors_file,
        )
        self._market_page = MarketPage(
            self._driver,
            base_url=self._base_url,
            timeout=self._settings.selenium_timeout,
            selectors_path=self._settings.selenium_selectors_file,
        )

        self._ensure_logged_in()
        logger.info("Chrome restarted successfully")

    def close(self):
        """Save cookies and quit the browser."""
        try:
            save_cookies(self._driver, self._cookie_file)
        except Exception as e:
            logger.warning(f"Failed to save cookies on close: {e}")

        try:
            self._driver.quit()
            logger.info("Browser closed")
        except Exception as e:
            logger.warning(f"Failed to close browser: {e}")
