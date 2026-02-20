"""Market page object — navigates to a market and places trades."""
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

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
        # Wait for the trade panel to load
        time.sleep(3)

    def select_outcome(self, is_yes=True):
        """Click the Yes/Up or No/Down outcome button."""
        key = "yes_button" if is_yes else "no_button"
        selectors = self._get_selectors("market", key)
        self._wait_and_click(selectors)
        logger.info(f"Selected outcome: {'Yes/Up' if is_yes else 'No/Down'}")

    def select_buy_or_sell(self, side):
        """Click Buy or Sell tab in the trade panel.

        Args:
            side: "BUY" or "SELL"
        """
        key = "buy_button" if side.upper() == "BUY" else "sell_button"
        selectors = self._get_selectors("market", key)
        try:
            self._wait_and_click(selectors, timeout=5)
            logger.info(f"Selected side: {side}")
        except (TimeoutError, Exception):
            # Buy is the default tab — if we can't click it, continue anyway
            logger.info(f"Buy/Sell tab click skipped (likely already on {side} tab)")

    def enter_amount(self, amount):
        """Enter the dollar amount to trade.

        Tries the amount input field first. Falls back to clicking
        preset amount buttons (+$1, +$5, +$10, +$100) to reach
        the target amount.
        """
        amount = round(float(amount), 2)
        amount_selectors = self._get_selectors("market", "amount_input")

        try:
            element = self._find_with_fallback(amount_selectors, timeout=5)
            # Clear existing value and type the amount
            element.click()
            element.send_keys(Keys.CONTROL + "a")
            element.send_keys(str(int(amount)) if amount == int(amount) else str(amount))
            logger.info(f"Entered amount: ${amount}")
            return
        except (TimeoutError, Exception):
            logger.info("Amount input not found, using preset buttons")

        # Fallback: use preset buttons to build up the amount
        self._enter_amount_with_presets(amount)

    def _enter_amount_with_presets(self, amount):
        """Click preset amount buttons to reach the target dollar amount."""
        remaining = amount
        presets = [
            (100, "amount_100"),
            (10, "amount_10"),
            (5, "amount_5"),
            (1, "amount_1"),
        ]

        for value, selector_key in presets:
            selectors = self._get_selectors("market", selector_key)
            if not selectors:
                continue
            while remaining >= value:
                try:
                    self._wait_and_click(selectors, timeout=3)
                    remaining -= value
                    time.sleep(0.3)
                except (TimeoutError, Exception):
                    break

        if remaining > 0:
            logger.warning(f"Could not fully reach ${amount}, ${remaining:.2f} remaining")
        else:
            logger.info(f"Entered amount via presets: ${amount}")

    def enter_price(self, price):
        """Enter a limit price. Only applicable when in Limit order mode.

        For Market orders on Polymarket, there is no price input — the
        price is determined by the orderbook. This method is a no-op
        for market orders.
        """
        # Polymarket's market-order UI doesn't have a price input.
        # For limit orders, we'd need to switch the order type toggle first.
        logger.info(f"Price {price} noted (market orders use orderbook price)")

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
            logger.info("No confirmation dialog (may not be required)")
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
            logger.info(f"Order result: SUCCESS - {msg}")
            return {"success": True, "message": msg}
        except (TimeoutError, Exception):
            pass

        # Check for error
        try:
            el = self._find_with_fallback(error_selectors, timeout=3)
            msg = el.text if el.text else "Order failed"
            logger.warning(f"Order result: FAILED - {msg}")
            return {"success": False, "message": msg}
        except (TimeoutError, Exception):
            logger.warning("Order result: UNKNOWN - no success/error indicator found")
            return {"success": False, "message": "Unknown result"}

    def is_market_available(self):
        """Check if the market's submit button shows 'Unavailable'."""
        try:
            els = self.driver.find_elements(
                By.XPATH,
                "//button[contains(@class, 'trading-button')][contains(., 'Unavailable')]",
            )
            return len(els) == 0
        except Exception:
            return True

    def redeem_positions(self):
        """Navigate to portfolio and redeem any claimable/won positions.

        Returns:
            dict with 'redeemed' (int) count of positions redeemed
        """
        logger.info("Checking portfolio for redeemable positions...")
        self.driver.get(f"{self.base_url}/portfolio")
        time.sleep(3)

        redeemed = 0
        # Look for redeem/claim buttons
        redeem_xpaths = [
            "//button[contains(., 'Redeem')]",
            "//button[contains(., 'Claim')]",
            "//button[contains(., 'Cash Out')]",
            "//a[contains(., 'Redeem')]",
        ]

        for xpath in redeem_xpaths:
            try:
                buttons = self.driver.find_elements(By.XPATH, xpath)
                for btn in buttons:
                    try:
                        btn.click()
                        time.sleep(2)
                        redeemed += 1
                        logger.info(f"Redeemed position (via {xpath})")
                    except Exception:
                        pass
            except Exception:
                pass

        if redeemed > 0:
            logger.info(f"Redeemed {redeemed} positions")
            time.sleep(2)  # Wait for balance to update
        else:
            logger.info("No positions to redeem")

        return {"redeemed": redeemed}

    def place_trade(self, slug, side, is_yes, price, amount):
        """Full trade flow: navigate -> select side -> outcome -> amount -> submit.

        Args:
            slug: market slug (e.g., 'will-bitcoin-hit-100k')
            side: "BUY" or "SELL"
            is_yes: True for Yes/Up outcome, False for No/Down
            price: limit price (used for logging; market orders use orderbook price)
            amount: dollar amount to trade

        Returns:
            dict with 'success' and 'message'
        """
        self.navigate_to_market(slug)
        self.select_buy_or_sell(side)
        self.select_outcome(is_yes)
        self.enter_amount(amount)

        # Wait for UI to update totals and button state
        time.sleep(2)

        # Check availability right before submitting
        if not self.is_market_available():
            msg = "Market is unavailable for trading"
            logger.warning(msg)
            return {"success": False, "message": msg}

        self.submit_order()
        self.confirm_order(timeout=5)
        return self.check_order_result()
