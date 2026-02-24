"""Check the relationship between EOA and proxy wallet on Polymarket."""
import os
import sys
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()

from eth_account import Account
from web3 import Web3

PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY", "")
FUNDER_ADDRESS = os.getenv("FUNDER_ADDRESS", "")

eoa = Account.from_key(PRIVATE_KEY)
print(f"EOA:    {eoa.address}")
print(f"Funder: {FUNDER_ADDRESS}")
print()

w3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))

# Check if funder is a contract or EOA
funder_cs = Web3.to_checksum_address(FUNDER_ADDRESS)
code = w3.eth.get_code(funder_cs)
print(f"Funder has contract code: {len(code) > 0} ({len(code)} bytes)")

eoa_cs = Web3.to_checksum_address(eoa.address)
code2 = w3.eth.get_code(eoa_cs)
print(f"EOA has contract code: {len(code2) > 0} ({len(code2)} bytes)")

# Check Polymarket proxy factory to find the real proxy for this EOA
# Polymarket proxy factory on Polygon
PROXY_FACTORY = "0xaB45c5A4B0c941a2F231C04C3f49182e1A254052"
abi = [
    {
        "inputs": [{"name": "", "type": "address"}],
        "name": "getProxy",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    }
]
factory = w3.eth.contract(address=Web3.to_checksum_address(PROXY_FACTORY), abi=abi)
try:
    proxy = factory.functions.getProxy(eoa_cs).call()
    print(f"\nProxy wallet for EOA (from factory): {proxy}")
    if proxy.lower() == FUNDER_ADDRESS.lower():
        print("  -> MATCH! Funder IS the proxy for this EOA")
    elif proxy == "0x0000000000000000000000000000000000000000":
        print("  -> No proxy registered for this EOA")
    else:
        print(f"  -> MISMATCH! Expected {FUNDER_ADDRESS}")
except Exception as e:
    print(f"\nProxy factory lookup failed: {e}")

# Also check via Polymarket's Data API
try:
    resp = requests.get(
        f"https://data-api.polymarket.com/profile/{eoa.address.lower()}"
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"\nPolymarket profile for EOA:")
        print(f"  proxy: {data.get('proxyWallet', 'N/A')}")
        print(f"  data: {data}")
    else:
        print(f"\nProfile lookup returned {resp.status_code}")
except Exception as e:
    print(f"\nProfile lookup failed: {e}")
