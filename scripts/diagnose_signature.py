"""Diagnose invalid signature issue for Polymarket CLOB."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY", "")
SIGNATURE_TYPE = int(os.getenv("SIGNATURE_TYPE", "2"))
FUNDER_ADDRESS = os.getenv("FUNDER_ADDRESS", "")
CHAIN_ID = int(os.getenv("CHAIN_ID", "137"))

# 1. Derive EOA address from private key
from eth_account import Account

eoa = Account.from_key(PRIVATE_KEY)
print(f"EOA address (from private key): {eoa.address}")
print(f"Funder address (Gnosis Safe):   {FUNDER_ADDRESS}")
print(f"Signature type:                 {SIGNATURE_TYPE}")
print()

# 2. Check if EOA is owner of the Gnosis Safe
try:
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))
    safe_addr = Web3.to_checksum_address(FUNDER_ADDRESS)

    # Gnosis Safe ABI - isOwner and getOwners
    abi = [
        {
            "inputs": [{"name": "owner", "type": "address"}],
            "name": "isOwner",
            "outputs": [{"name": "", "type": "bool"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "getOwners",
            "outputs": [{"name": "", "type": "address[]"}],
            "stateMutability": "view",
            "type": "function",
        },
    ]

    safe = w3.eth.contract(address=safe_addr, abi=abi)

    try:
        is_owner = safe.functions.isOwner(Web3.to_checksum_address(eoa.address)).call()
        print(f"Is EOA an owner of the Safe? {is_owner}")
    except Exception as e:
        print(f"isOwner check failed: {e}")
        print("(This address may not be a Gnosis Safe)")

    try:
        owners = safe.functions.getOwners().call()
        print(f"Safe owners: {owners}")
    except Exception as e:
        print(f"getOwners failed: {e}")

except ImportError:
    print("web3 not installed, skipping on-chain check")

print()

# 3. Test order creation (without posting)
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

api_key = os.getenv("POLYMARKET_API_KEY", "")
api_secret = os.getenv("POLYMARKET_API_SECRET", "")
passphrase = os.getenv("POLYMARKET_PASSPHRASE", "")

creds = None
if api_key and api_secret and passphrase:
    creds = ApiCreds(api_key=api_key, api_secret=api_secret, api_passphrase=passphrase)
    print(f"Using explicit API creds (key={api_key[:8]}...)")
else:
    print("No explicit API creds, will try to derive")

client = ClobClient(
    "https://clob.polymarket.com",
    key=PRIVATE_KEY,
    chain_id=CHAIN_ID,
    creds=creds,
    signature_type=SIGNATURE_TYPE,
    funder=FUNDER_ADDRESS or None,
)

if not creds:
    try:
        derived = client.create_or_derive_api_creds()
        client.set_api_creds(derived)
        print(f"Derived API creds OK (key={derived.api_key[:8]}...)")
    except Exception as e:
        print(f"Failed to derive API creds: {e}")

print(f"Client mode: L{client.mode}")
print(f"Builder sig_type: {client.builder.sig_type}")
print(f"Builder funder: {client.builder.funder}")
print(f"Builder signer: {client.builder.signer.address()}")
