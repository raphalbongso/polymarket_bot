"""Find Polymarket proxy wallet for an EOA using both factory contracts."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()

from web3 import Web3

w3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))

METAMASK = "0x73235cb60da4e03781ff9b242daab4c53110a839"
EOA_FROM_KEY = "0x931d952B1d48CfD6dc5b8B0cAe3Bd8AcA3111e0a"

# Gnosis Safe factory (MetaMask users)
GNOSIS_FACTORY = "0xaacfeea03eb1561c4e67d661e40682bd20e3541b"
# Polymarket Proxy factory (MagicLink users)
PROXY_FACTORY = "0xaB45c5A4B0c941a2F231C04C3f49182e1A254052"

# Try multiple common function signatures for proxy lookup
SELECTORS = [
    {"name": "getProxy", "inputs": [{"name": "", "type": "address"}], "outputs": [{"name": "", "type": "address"}], "stateMutability": "view", "type": "function"},
    {"name": "proxyFor", "inputs": [{"name": "", "type": "address"}], "outputs": [{"name": "", "type": "address"}], "stateMutability": "view", "type": "function"},
    {"name": "proxies", "inputs": [{"name": "", "type": "address"}], "outputs": [{"name": "", "type": "address"}], "stateMutability": "view", "type": "function"},
]

for label, factory_addr in [("Gnosis Safe Factory", GNOSIS_FACTORY), ("Polymarket Proxy Factory", PROXY_FACTORY)]:
    print(f"\n{label} ({factory_addr}):")
    factory_cs = Web3.to_checksum_address(factory_addr)

    for addr_label, addr in [("MetaMask", METAMASK), ("EOA from key", EOA_FROM_KEY)]:
        addr_cs = Web3.to_checksum_address(addr)
        for sel in SELECTORS:
            try:
                contract = w3.eth.contract(address=factory_cs, abi=[sel])
                fn = getattr(contract.functions, sel["name"])
                result = fn(addr_cs).call()
                if result != "0x0000000000000000000000000000000000000000":
                    print(f"  {sel['name']}({addr_label}) = {result}")
                else:
                    print(f"  {sel['name']}({addr_label}) = (zero address)")
            except Exception as e:
                err = str(e)[:80]
                print(f"  {sel['name']}({addr_label}) failed: {err}")

# Also check contract code size of both addresses
print(f"\nContract code check:")
for label, addr in [("MetaMask", METAMASK), ("EOA from key", EOA_FROM_KEY)]:
    code = w3.eth.get_code(Web3.to_checksum_address(addr))
    print(f"  {label} ({addr}): {len(code)} bytes {'(contract)' if len(code) > 0 else '(EOA)'}")
