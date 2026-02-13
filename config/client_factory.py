"""Factory for creating authenticated Polymarket CLOB clients."""
from config.settings import Settings

try:
    from py_clob_client.client import ClobClient
    HAS_CLOB = True
except ImportError:
    HAS_CLOB = False


def create_clob_client(settings: Settings):
    """Create and authenticate a ClobClient from Settings.

    Returns None if py-clob-client is not installed.
    """
    if not HAS_CLOB:
        return None

    client = ClobClient(
        settings.clob_url,
        key=settings.private_key,
        chain_id=settings.chain_id,
    )

    if settings.api_key and settings.api_secret and settings.passphrase:
        client.set_api_creds(
            client.create_or_derive_api_creds()
            if not settings.api_key
            else {
                "apiKey": settings.api_key,
                "secret": settings.api_secret,
                "passphrase": settings.passphrase,
            }
        )
    else:
        try:
            creds = client.create_or_derive_api_creds()
            client.set_api_creds(creds)
        except Exception:
            pass  # Will operate in read-only mode

    return client
