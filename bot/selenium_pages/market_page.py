"""Market page object — navigates to a market and places trades."""
import time

from bot.selenium_pages.base_page import BasePage
from monitoring.logger import get_logger

logger = get_logger("selenium.market_page")


class MarketPage(BasePage):
    """Automates the Polymarket trade panel UI."""

    def __init__(self, driver, base_url="https://polymarket.com", **kwargs):
        super().__init__(driver, **kwargs)
        self.base_url = base_url.rstrip("/")

    def navigate_to_market(self, slug):
        """Open the market page by slug."""
        url = f"{self.base_url}/event/{slug}"
        logger.info(f"Navigating to {url}")
        self.driver.get(url)
        # Wait for the trade panel to be interactive
        time.sleep(2)

    def select_outcome(self, is_yes=True):
        """Click the Yes or No outcome button."""
        key = "yes_button" if is_yes else "no_button"
        selectors = self._get_selectors("market", key)
        self._wait_and_click(selectors)
        logger.info(f"Selected outcome: {'Yes' if is_yes else 'No'}")

    def select_buy_or_sell(self, side):
        """Click Buy or Sell in the trade panel.

        Args:
            side: "BUY" or "SELL"
        """
        key = "buy_button" if side.upper() == "BUY" else "sell_button"
        selectors = self._get_selectors("market", key)
        self._wait_and_click(selectors)
        logger.info(f"Selected side: {side}")

    def enter_price(self, price):
        """Type the limit price into the price input field."""
        selectors = self._get_selectors("market", "price_input")
        self._safe_send_keys(selectors, str(price))
        logger.info(f"Entered price: {price}")

    def enter_amount(self, amount):
        """Type the dollar amount into the amount input field."""
        selectors = self._get_selectors("market", "amount_input")
        self._safe_send_keys(selectors, str(amount))
        logger.info(f"Entered amount: {amount}")

    def submit_order(self):
        """Click the submit / place-order button."""
        selectors = self._get_selectors("market", "submit_button")
        self._wait_and_click(selectors)
        logger.info("Order submitted")

    def confirm_order(self, timeout=10):
        """Click the confirmation button if a confirm dialog appears."""
        selectors = self._get_selectors("market", "confirm_button")
        try:
            self._wait_and_click(selectors, timeout=timeout)
            logger.info("Order confirmed")
            return True
        except (TimeoutError, Exception):
            logger.info("No confirmation dialog found (may not be required)")
            return False

    def check_order_result(self, timeout=10):
        """Check whether the order succeeded or failed after submission.

        Returns:
            dict with keys 'success' (bool) and 'message' (str)
        """
        success_selectors = self._get_selectors("market", "order_success")
        error_selectors = self._get_selectors("market", "order_error")

        # Check for success first
        try:
            el = self._find_with_fallback(success_selectors, timeout=timeout)
            msg = el.text if el.text else "Order placed"
            logger.info(f"Order result: SUCCESS — {msg}")
            return {"success": True, "message": msg}
        except (TimeoutError, Exception):
            pass

        # Check for error
        try:
            el = self._find_with_fallback(error_selectors, timeout=3)
            msg = el.text if el.text else "Order failed"
            logger.warning(f"Order result: FAILED — {msg}")
            return {"success": False, "message": msg}
        except (TimeoutError, Exception):
            logger.warning("Order result: UNKNOWN — no success/error indicator found")
            return {"success": False, "message": "Unknown result"}

    def place_trade(self, slug, side, is_yes, price, amount):
        """Full trade flow: navigate → select outcome → buy/sell → price → amount → submit → confirm.

        Args:
            slug: market slug (e.g., 'will-bitcoin-hit-100k')
            side: "BUY" or "SELL"
            is_yes: True for Yes outcome, False for No
            price: limit price (0.01 – 0.99)
            amount: dollar amount to trade

        Returns:
            dict with 'success' and 'message'
        """
        self.navigate_to_market(slug)
        self.select_outcome(is_yes)
        self.select_buy_or_sell(side)
        self.enter_price(price)
        self.enter_amount(amount)
        self.submit_order()
        self.confirm_order()
        return self.check_order_result()
