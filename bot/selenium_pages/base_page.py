"""Base page object with shared Selenium helpers."""
import os
import time

import yaml
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from monitoring.logger import get_logger

logger = get_logger("selenium.base_page")

_SELECTORS_CACHE = None


def load_selectors(path=None):
    """Load UI selectors from YAML, cached after first call."""
    global _SELECTORS_CACHE
    if _SELECTORS_CACHE is not None:
        return _SELECTORS_CACHE

    if path is None:
        path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "selectors.yaml")
    path = os.path.abspath(path)
    with open(path, "r") as f:
        _SELECTORS_CACHE = yaml.safe_load(f)
    return _SELECTORS_CACHE


class BasePage:
    """Shared helpers for all page objects."""

    def __init__(self, driver, timeout=15, selectors_path=None):
        self.driver = driver
        self.timeout = timeout
        self.selectors = load_selectors(selectors_path)

    def _by_for(self, selector_str):
        """Return the appropriate By strategy for a selector string."""
        if selector_str.startswith("//") or selector_str.startswith("(//"):
            return By.XPATH
        return By.CSS_SELECTOR

    def _find_with_fallback(self, selector_list, timeout=None):
        """Try multiple selectors in order, return the first visible element found."""
        timeout = timeout or self.timeout
        for selector in selector_list:
            by = self._by_for(selector)
            try:
                element = WebDriverWait(self.driver, timeout / len(selector_list)).until(
                    EC.visibility_of_element_located((by, selector))
                )
                return element
            except Exception:
                continue
        raise TimeoutError(
            f"None of the selectors matched within {timeout}s: {selector_list}"
        )

    def _wait_and_click(self, selector_list, timeout=None):
        """Wait for element to be clickable, then click it."""
        timeout = timeout or self.timeout
        for selector in selector_list:
            by = self._by_for(selector)
            try:
                element = WebDriverWait(self.driver, timeout / len(selector_list)).until(
                    EC.element_to_be_clickable((by, selector))
                )
                element.click()
                return element
            except Exception:
                continue
        raise TimeoutError(
            f"None of the selectors were clickable within {timeout}s: {selector_list}"
        )

    def _wait_for_visible(self, selector_list, timeout=None):
        """Wait until at least one selector matches a visible element."""
        return self._find_with_fallback(selector_list, timeout)

    def _safe_send_keys(self, selector_list, text, clear_first=True):
        """Find input element and type text into it."""
        element = self._find_with_fallback(selector_list)
        if clear_first:
            element.clear()
        element.send_keys(text)
        return element

    def _take_screenshot(self, name="error"):
        """Save a screenshot to the screenshots directory."""
        screenshots_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "screenshots"
        )
        os.makedirs(screenshots_dir, exist_ok=True)
        ts = int(time.time())
        path = os.path.join(screenshots_dir, f"{name}_{ts}.png")
        try:
            self.driver.save_screenshot(path)
            logger.info(f"Screenshot saved: {path}")
        except Exception as e:
            logger.warning(f"Failed to save screenshot: {e}")
        return path

    def _get_selectors(self, section, element):
        """Retrieve selector list from the loaded YAML config."""
        return self.selectors.get(section, {}).get(element, [])
