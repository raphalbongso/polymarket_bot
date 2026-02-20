"""Cookie persistence and IMAP magic-link extraction for Selenium sessions."""
import email
import imaplib
import json
import os
import re
import time

from monitoring.logger import get_logger

logger = get_logger("selenium.auth")


def save_cookies(driver, path):
    """Save browser cookies to a JSON file."""
    cookies = driver.get_cookies()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(cookies, f, indent=2)
    logger.info(f"Saved {len(cookies)} cookies to {path}")


def load_cookies(driver, path, domain_filter="polymarket.com"):
    """Load cookies from a JSON file into the browser.

    The browser must first navigate to the domain before cookies can be set.

    Returns:
        True if cookies were loaded, False if file doesn't exist.
    """
    if not os.path.exists(path):
        logger.info(f"No cookie file found at {path}")
        return False

    with open(path, "r") as f:
        cookies = json.load(f)

    loaded = 0
    for cookie in cookies:
        # Only load cookies that match the target domain
        if domain_filter and domain_filter not in cookie.get("domain", ""):
            continue
        try:
            driver.add_cookie(cookie)
            loaded += 1
        except Exception as e:
            logger.debug(f"Skipped cookie {cookie.get('name')}: {e}")

    logger.info(f"Loaded {loaded}/{len(cookies)} cookies from {path}")
    return loaded > 0


def extract_magic_link_from_imap(
    imap_host,
    imap_user,
    imap_password,
    sender_filter="polymarket",
    poll_interval=5,
    max_wait=120,
    imap_port=993,
):
    """Poll an IMAP inbox for a Polymarket magic link email.

    Connects to the IMAP server, waits for a new email from Polymarket
    containing a magic link, and returns the URL.

    Args:
        imap_host: IMAP server hostname (e.g., 'imap.gmail.com')
        imap_user: Email address / username
        imap_password: Email password or app-specific password
        sender_filter: Filter emails by sender containing this string
        poll_interval: Seconds between inbox checks
        max_wait: Maximum seconds to wait before giving up
        imap_port: IMAP SSL port (default 993)

    Returns:
        The magic link URL, or None if not found within max_wait.
    """
    logger.info(f"Polling IMAP ({imap_host}) for magic link...")
    start = time.time()

    # Remember the latest email UID before we triggered the login
    try:
        mail = imaplib.IMAP4_SSL(imap_host, imap_port)
        mail.login(imap_user, imap_password)
    except Exception as e:
        logger.error(f"IMAP login failed: {e}")
        return None

    try:
        mail.select("INBOX")
        # Get current message count as baseline
        _, data = mail.search(None, "ALL")
        baseline_uids = set(data[0].split()) if data[0] else set()

        while time.time() - start < max_wait:
            time.sleep(poll_interval)
            mail.noop()  # Keep connection alive and trigger new mail check

            _, data = mail.search(None, "ALL")
            current_uids = set(data[0].split()) if data[0] else set()
            new_uids = current_uids - baseline_uids

            for uid in sorted(new_uids, reverse=True):
                _, msg_data = mail.fetch(uid, "(RFC822)")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                sender = msg.get("From", "").lower()
                if sender_filter.lower() not in sender:
                    continue

                # Extract magic link from email body
                body = _get_email_body(msg)
                link = _extract_polymarket_link(body)
                if link:
                    logger.info("Magic link found in email")
                    return link

        logger.warning(f"No magic link found within {max_wait}s")
        return None
    finally:
        try:
            mail.logout()
        except Exception:
            pass


def _get_email_body(msg):
    """Extract the text body from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type in ("text/plain", "text/html"):
                try:
                    return part.get_payload(decode=True).decode("utf-8", errors="replace")
                except Exception:
                    continue
    else:
        try:
            return msg.get_payload(decode=True).decode("utf-8", errors="replace")
        except Exception:
            return ""
    return ""


def _extract_polymarket_link(body):
    """Find a Polymarket magic/auth link in an email body."""
    # Match URLs like https://polymarket.com/auth?token=... or similar magic link patterns
    patterns = [
        r'https?://[^\s"<>]*polymarket\.com/auth[^\s"<>]*',
        r'https?://[^\s"<>]*polymarket\.com/[^\s"<>]*token=[^\s"<>]*',
        r'https?://auth\.magic\.link/[^\s"<>]*',
    ]
    for pattern in patterns:
        match = re.search(pattern, body)
        if match:
            return match.group(0)
    return None
