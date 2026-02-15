"""Factory for creating authenticated Polymarket CLOB clients."""
from config.settings import Settings

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds, BalanceAllowanceParams, AssetType
    HAS_CLOB = True
except ImportError:
    HAS_CLOB = False


def create_clob_client(settings: Settings):
    """Create and authenticate a ClobClient from Settings.

    Returns None if py-clob-client is not installed.
    """
    if not HAS_CLOB:
        return None

    # Build API creds object if provided
    creds = None
    if settings.api_key and settings.api_secret and settings.passphrase:
        creds = ApiCreds(
            api_key=settings.api_key,
            api_secret=settings.api_secret,
            api_passphrase=settings.passphrase,
        )

    client = ClobClient(
        settings.clob_url,
        key=settings.private_key,
        chain_id=settings.chain_id,
        creds=creds,
        signature_type=settings.signature_type,
        funder=settings.funder_address or None,
    )

    # If no explicit creds were provided, try to derive them
    if creds is None:
        try:
            derived = client.create_or_derive_api_creds()
            client.set_api_creds(derived)
        except Exception:
            pass  # Will operate in read-only mode

    return client


def fetch_usdc_balance(clob_client):
    """Fetch USDC collateral balance from Polymarket.

    For proxy wallets the CLOB API may report 0 even though USDC sits in the
    proxy wallet on-chain.  When a funder (proxy) address is configured we fall
    back to reading the on-chain USDC.e balance so the bot sees the real funds.
    """
    if not HAS_CLOB or clob_client is None:
        return None
    try:
        result = clob_client.get_balance_allowance(
            BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        )
        balance = int(result["balance"]) / 1e6
        if balance > 0:
            return balance
    except Exception:
        pass

    # Fallback: read on-chain USDC.e balance of proxy wallet
    funder = getattr(clob_client, "funder", None) or getattr(
        getattr(clob_client, "builder", None), "funder", None
    )
    if funder:
        try:
            from web3 import Web3

            w3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))
            usdc_addr = Web3.to_checksum_address(
                "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
            )
            abi = [
                {
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "type": "function",
                }
            ]
            usdc = w3.eth.contract(address=usdc_addr, abi=abi)
            raw = usdc.functions.balanceOf(
                Web3.to_checksum_address(funder)
            ).call()
            return raw / 1e6
        except Exception:
            pass
    return None
