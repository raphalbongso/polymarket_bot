"""Check USDC balance and allowance for EOA on Polymarket exchange."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()

from web3 import Web3
from eth_account import Account

w3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))

PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY", "")
eoa = Account.from_key(PRIVATE_KEY)
eoa_cs = Web3.to_checksum_address(eoa.address)

# USDCe on Polygon
USDC = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")
# USDC (native) on Polygon
USDC_NATIVE = Web3.to_checksum_address("0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359")
# Polymarket CTF Exchange
EXCHANGE = Web3.to_checksum_address("0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E")
# Polymarket Neg Risk CTF Exchange
NEG_RISK_EXCHANGE = Web3.to_checksum_address("0xC5d563A36AE78145C45a50134d48A1215220f80a")

erc20_abi = [
    {"inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
]

print(f"EOA: {eoa.address}\n")

for label, token_addr in [("USDCe (bridged)", USDC), ("USDC (native)", USDC_NATIVE)]:
    token = w3.eth.contract(address=token_addr, abi=erc20_abi)
    balance = token.functions.balanceOf(eoa_cs).call()
    print(f"{label} balance: ${balance / 1e6:.2f}")
    for ex_label, ex_addr in [("CTF Exchange", EXCHANGE), ("Neg Risk Exchange", NEG_RISK_EXCHANGE)]:
        allowance = token.functions.allowance(eoa_cs, ex_addr).call()
        print(f"  Allowance for {ex_label}: ${allowance / 1e6:.2f}")
    print()
