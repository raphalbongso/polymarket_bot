"""Derive Polymarket CLOB API credentials and save them to .env."""
import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from py_clob_client.client import ClobClient

load_dotenv()

PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY", "")
CHAIN_ID = int(os.getenv("CHAIN_ID", "137"))
SIGNATURE_TYPE = int(os.getenv("SIGNATURE_TYPE", "2"))
FUNDER_ADDRESS = os.getenv("FUNDER_ADDRESS", "")
CLOB_URL = "https://clob.polymarket.com"

if not PRIVATE_KEY:
    print("ERROR: POLYMARKET_PRIVATE_KEY not set in .env")
    sys.exit(1)

print(f"Connecting to {CLOB_URL}")
print(f"  chain_id={CHAIN_ID}, signature_type={SIGNATURE_TYPE}, funder={FUNDER_ADDRESS}")

client = ClobClient(
    CLOB_URL,
    key=PRIVATE_KEY,
    chain_id=CHAIN_ID,
    signature_type=SIGNATURE_TYPE,
    funder=FUNDER_ADDRESS or None,
)

print("Deriving API credentials...")
creds = client.create_or_derive_api_creds()
print(f"  api_key:    {creds.api_key}")
print(f"  api_secret: {creds.api_secret}")
print(f"  passphrase: {creds.api_passphrase}")

# Update .env file
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
env_path = os.path.normpath(env_path)

with open(env_path, "r") as f:
    content = f.read()

replacements = {
    "POLYMARKET_API_KEY": creds.api_key,
    "POLYMARKET_API_SECRET": creds.api_secret,
    "POLYMARKET_PASSPHRASE": creds.api_passphrase,
}

for key, value in replacements.items():
    content = re.sub(rf"^{key}=.*$", f"{key}={value}", content, flags=re.MULTILINE)

with open(env_path, "w") as f:
    f.write(content)

print(f"\n.env updated at {env_path}")
