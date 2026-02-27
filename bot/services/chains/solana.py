import re
from datetime import datetime, timezone

import httpx

from bot.services.chains.base import AddressInfo, BaseChainAnalyzer

# Solana addresses are base58-encoded, 32-44 chars
SOL_ADDRESS_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")

SOLANA_RPC = "https://api.mainnet-beta.solana.com"


class SolanaAnalyzer(BaseChainAnalyzer):
    chain_name = "solana"

    def is_valid_address(self, address: str) -> bool:
        return bool(SOL_ADDRESS_RE.match(address))

    async def get_address_info(self, address: str) -> AddressInfo:
        info = AddressInfo(address=address, chain="solana")

        if not self.is_valid_address(address):
            info.error = "Invalid Solana address format"
            return info

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                # Get balance via RPC
                balance_resp = await client.post(
                    SOLANA_RPC,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getBalance",
                        "params": [address],
                    },
                )
                balance_data = balance_resp.json()
                if "result" in balance_data:
                    lamports = balance_data["result"]["value"]
                    info.balance = f"{lamports / 1e9:.9f} SOL"

                # Get transaction signatures for activity info
                sigs_resp = await client.post(
                    SOLANA_RPC,
                    json={
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "getSignaturesForAddress",
                        "params": [address, {"limit": 5}],
                    },
                )
                sigs_data = sigs_resp.json()
                if "result" in sigs_data and sigs_data["result"]:
                    sigs = sigs_data["result"]
                    info.tx_count = len(sigs)  # Approximation from recent txs

                    # Last active from most recent signature
                    info.last_tx_hash = sigs[0].get("signature")
                    if sigs[0].get("blockTime"):
                        info.last_active = datetime.fromtimestamp(
                            sigs[0]["blockTime"], tz=timezone.utc
                        )

                    # First seen from oldest in batch
                    if sigs[-1].get("blockTime"):
                        info.first_seen = datetime.fromtimestamp(
                            sigs[-1]["blockTime"], tz=timezone.utc
                        )

                # Check if this is an executable (program) account
                acct_resp = await client.post(
                    SOLANA_RPC,
                    json={
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "getAccountInfo",
                        "params": [address, {"encoding": "jsonParsed"}],
                    },
                )
                acct_data = acct_resp.json()
                if "result" in acct_data and acct_data["result"]["value"]:
                    acct = acct_data["result"]["value"]
                    if acct.get("executable"):
                        info.is_contract = True
                        info.labels.append("program")
                    owner = acct.get("owner", "")
                    if owner == "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA":
                        info.labels.append("token-account")

            except httpx.HTTPError as e:
                info.error = f"API request failed: {e}"

        return info
