import re
from datetime import datetime, timezone

import httpx

from bot.services.chains.base import AddressInfo, BaseChainAnalyzer

# Tron addresses start with T and are 34 characters
TRON_ADDRESS_RE = re.compile(r"^T[a-zA-Z0-9]{33}$")

TRONGRID_API = "https://api.trongrid.io"


class TronAnalyzer(BaseChainAnalyzer):
    chain_name = "tron"

    def is_valid_address(self, address: str) -> bool:
        return bool(TRON_ADDRESS_RE.match(address))

    async def get_address_info(self, address: str) -> AddressInfo:
        info = AddressInfo(address=address, chain="tron")

        if not self.is_valid_address(address):
            info.error = "Invalid Tron address format"
            return info

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                # Get account info
                acct_resp = await client.get(
                    f"{TRONGRID_API}/v1/accounts/{address}",
                )
                acct_data = acct_resp.json()

                if acct_data.get("data"):
                    acct = acct_data["data"][0]

                    balance_sun = acct.get("balance", 0)
                    info.balance = f"{balance_sun / 1e6:.6f} TRX"

                    # Created time
                    create_time = acct.get("create_time")
                    if create_time:
                        info.first_seen = datetime.fromtimestamp(
                            create_time / 1000, tz=timezone.utc
                        )

                    # Check if contract
                    if acct.get("trc20") or acct.get("assetV2"):
                        info.labels.append("token-holder")

                # Get transactions
                tx_resp = await client.get(
                    f"{TRONGRID_API}/v1/accounts/{address}/transactions",
                    params={"limit": 5, "order_by": "block_timestamp,desc"},
                )
                tx_data = tx_resp.json()

                if tx_data.get("data"):
                    txs = tx_data["data"]
                    info.tx_count = tx_data.get("meta", {}).get("total", len(txs))

                    if txs:
                        info.last_tx_hash = txs[0].get("txID")
                        last_ts = txs[0].get("block_timestamp", 0)
                        if last_ts:
                            info.last_active = datetime.fromtimestamp(
                                last_ts / 1000, tz=timezone.utc
                            )

            except httpx.HTTPError as e:
                info.error = f"API request failed: {e}"

        return info
