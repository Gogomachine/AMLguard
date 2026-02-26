import re
from datetime import datetime, timezone

import httpx

from bot.config import settings
from bot.services.chains.base import AddressInfo, BaseChainAnalyzer

# Bitcoin address formats: legacy (1...), segwit (3...), bech32 (bc1...)
BTC_ADDRESS_RE = re.compile(r"^(1|3)[a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{39,59}$")


class BitcoinAnalyzer(BaseChainAnalyzer):
    chain_name = "bitcoin"

    def __init__(self):
        self.blockchair_key = settings.blockchair_api_key

    def is_valid_address(self, address: str) -> bool:
        return bool(BTC_ADDRESS_RE.match(address))

    async def get_address_info(self, address: str) -> AddressInfo:
        info = AddressInfo(address=address, chain="bitcoin")

        if not self.is_valid_address(address):
            info.error = "Invalid Bitcoin address format"
            return info

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                params = {}
                if self.blockchair_key:
                    params["key"] = self.blockchair_key

                resp = await client.get(
                    f"https://api.blockchair.com/bitcoin/dashboards/address/{address}",
                    params=params,
                )
                data = resp.json()

                if "data" in data and address in data["data"]:
                    addr_data = data["data"][address]["address"]

                    balance_sat = addr_data.get("balance", 0)
                    info.balance = f"{balance_sat / 1e8:.8f} BTC"

                    info.tx_count = addr_data.get("transaction_count", 0)

                    first_seen = addr_data.get("first_seen_receiving")
                    if first_seen:
                        info.first_seen = datetime.fromisoformat(
                            first_seen.replace("Z", "+00:00")
                        )

                    last_seen = addr_data.get("last_seen_receiving") or addr_data.get(
                        "last_seen_spending"
                    )
                    if last_seen:
                        info.last_active = datetime.fromisoformat(
                            last_seen.replace("Z", "+00:00")
                        )

                    # Check for known script types
                    script_type = addr_data.get("script_hex", "")
                    if addr_data.get("type"):
                        info.labels.append(f"type:{addr_data['type']}")

                else:
                    info.error = "Address not found or no data"

            except httpx.HTTPError as e:
                info.error = f"API request failed: {e}"

        return info
