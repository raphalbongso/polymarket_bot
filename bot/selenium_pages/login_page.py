"""Login page object for Polymarket."""
from selenium.webdriver.support.ui import WebDriverWait

from bot.selenium_pages.base_page import BasePage
from monitoring.logger import get_logger

logger = get_logger("selenium.login_page")


class LoginPage(BasePage):
    """Handles the Polymarket login flow."""

    def is_logged_in(self, timeout=5):
        """Check whether the browser session is already authenticated.

        Uses two strategies:
        1. Positive: look for logged-in-only elements (portfolio link, profile)
        2. Negative: if "Log In" / "Sign Up" buttons are visible, we're NOT logged in
        """
        # Strategy 1: positive indicator
        selectors = self._get_selectors("login", "logged_in_indicator")
        try:
            self._find_with_fallback(selectors, timeout=timeout)
            return True
        except (TimeoutError, Exception):
            pass

        # Strategy 2: negative indicator — if login buttons exist, not logged in
        not_logged_in = self._get_selectors("login", "not_logged_in_indicator")
        if not_logged_in:
            try:
                self._find_with_fallback(not_logged_in, timeout=2)
                return False  # Login button found = definitely not logged in
            except (TimeoutError, Exception):
                # No login button found either — might be logged in (SPA still loading)
                return True

        return False

    def login_with_email(self, email):
        """Enter email and click continue to trigger the magic link email.

        After calling this, the user must click the link in their inbox
        (or use IMAP auto-extraction) before calling wait_for_login_complete().
        """
        logger.info(f"Entering email: {email}")
        email_selectors = self._get_selectors("login", "email_input")
        self._safe_send_keys(email_selectors, email)

        continue_selectors = self._get_selectors("login", "continue_button")
        self._wait_and_click(continue_selectors)
        logger.info("Login email submitted, waiting for magic link...")

    def wait_for_login_complete(self, timeout=120):
        """Block until the logged-in indicator appears (magic link clicked)."""
        selectors = self._get_selectors("login", "logged_in_indicator")
        try:
            self._find_with_fallback(selectors, timeout=timeout)
            logger.info("Login confirmed — session active")
            return True
        except (TimeoutError, Exception):
            logger.warning(f"Login not completed within {timeout}s")
            return False
