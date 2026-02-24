"""Minimal test: create and post a single order following the exact Polymarket docs flow."""
import os
import sys
import json
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv()

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY

PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY", "")
CHAIN_ID = int(os.getenv("CHAIN_ID", "137"))
FUNDER_ADDRESS = os.getenv("FUNDER_ADDRESS", "")
HOST = "https://clob.polymarket.com"

# First, find a valid token_id from the Gamma API (same as the bot uses)
print("Fetching markets from Gamma API...")
resp = requests.get(
    "https://gamma-api.polymarket.com/markets",
    params={"closed": "false", "limit": 5},
)
gamma_markets = resp.json()
token_id = None
condition_id = None
for m in gamma_markets:
    tokens = json.loads(m.get("clobTokenIds", "[]"))
    if tokens:
        token_id = tokens[0]
        condition_id = m.get("conditionId", "")
        print(f"  Market: {m.get('question', 'unknown')[:60]}")
        print(f"  Token ID: {token_id[:30]}...")
        break

if not token_id:
    print("No market found!")
    sys.exit(1)

# Get tick_size and neg_risk from CLOB
print("\nFetching market info from CLOB...")
try:
    resp2 = requests.get(f"{HOST}/markets/{condition_id}")
    clob_market = resp2.json()
    print(f"  CLOB response keys: {list(clob_market.keys())[:10]}")
except Exception:
    clob_market = {}

# Test all three signature types
for sig_type in [1, 0, 2]:
    print(f"\n{'='*60}")
    print(f"Testing SIGNATURE_TYPE = {sig_type}")
    print(f"{'='*60}")

    funder = FUNDER_ADDRESS if sig_type in (1, 2) else None

    # Step 1: Init basic client
    client = ClobClient(HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID)

    # Step 2: Derive API creds
    try:
        creds = client.create_or_derive_api_creds()
        print(f"  Derived creds OK")
    except Exception as e:
        print(f"  Failed to derive creds: {e}")
        continue

    # Step 4: Reinitialize with full auth
    client = ClobClient(
        HOST,
        key=PRIVATE_KEY,
        chain_id=CHAIN_ID,
        creds=creds,
        signature_type=sig_type,
        funder=funder,
    )

    print(f"  Builder sig_type={client.builder.sig_type} funder={client.builder.funder} signer={client.builder.signer.address()}")

    # Step 5: Try to place a tiny order at minimum price
    try:
        order_args = OrderArgs(
            price=0.01,
            size=10.0,
            side=BUY,
            token_id=token_id,
        )
        signed_order = client.create_order(order_args)
        print(f"  Order signed OK")
        result = client.post_order(signed_order, OrderType.GTC)
        print(f"  SUCCESS! Result: {result}")
        try:
            client.cancel_all()
            print(f"  Cancelled all orders")
        except Exception:
            pass
        break
    except Exception as e:
        print(f"  FAILED: {e}")
