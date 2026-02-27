import re
from datetime import datetime, timezone

import httpx

from bot.config import settings
from bot.services.chains.base import AddressInfo, BaseChainAnalyzer

# Supported EVM networks and their explorers
EVM_NETWORKS = {
    "ethereum": {
        "api_url": "https://api.etherscan.io/api",
        "api_key": lambda: settings.etherscan_api_key,
        "symbol": "ETH",
        "decimals": 18,
    },
    "bsc": {
        "api_url": "https://api.bscscan.com/api",
        "api_key": lambda: settings.bscscan_api_key,
        "symbol": "BNB",
        "decimals": 18,
    },
}

EVM_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


class EVMAnalyzer(BaseChainAnalyzer):
    chain_name = "ethereum"

    def __init__(self, network: str = "ethereum"):
        self.network = network
        net_config = EVM_NETWORKS.get(network, EVM_NETWORKS["ethereum"])
        self.api_url = net_config["api_url"]
        self.api_key = net_config["api_key"]()
        self.symbol = net_config["symbol"]
        self.decimals = net_config["decimals"]
        self.chain_name = network

    def is_valid_address(self, address: str) -> bool:
        return bool(EVM_ADDRESS_RE.match(address))

    async def get_address_info(self, address: str) -> AddressInfo:
        info = AddressInfo(address=address, chain=self.chain_name)

        if not self.is_valid_address(address):
            info.error = "Invalid EVM address format"
            return info

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                # Fetch balance
                balance_resp = await client.get(
                    self.api_url,
                    params={
                        "module": "account",
                        "action": "balance",
                        "address": address,
                        "tag": "latest",
                        "apikey": self.api_key,
                    },
                )
                balance_data = balance_resp.json()
                if balance_data.get("status") == "1":
                    wei = int(balance_data["result"])
                    info.balance = f"{wei / 10**self.decimals:.6f} {self.symbol}"

                # Fetch normal transactions (last few) to get first/last activity
                tx_resp = await client.get(
                    self.api_url,
                    params={
                        "module": "account",
                        "action": "txlist",
                        "address": address,
                        "startblock": 0,
                        "endblock": 99999999,
                        "page": 1,
                        "offset": 5,
                        "sort": "asc",
                        "apikey": self.api_key,
                    },
                )
                tx_data = tx_resp.json()
                if tx_data.get("status") == "1" and tx_data.get("result"):
                    txs = tx_data["result"]
                    first_ts = int(txs[0]["timeStamp"])
                    info.first_seen = datetime.fromtimestamp(first_ts, tz=timezone.utc)

                # Get total tx count
                txcount_resp = await client.get(
                    self.api_url,
                    params={
                        "module": "proxy",
                        "action": "eth_getTransactionCount",
                        "address": address,
                        "tag": "latest",
                        "apikey": self.api_key,
                    },
                )
                txcount_data = txcount_resp.json()
                if txcount_data.get("result"):
                    info.tx_count = int(txcount_data["result"], 16)

                # Get last tx for last_active
                last_tx_resp = await client.get(
                    self.api_url,
                    params={
                        "module": "account",
                        "action": "txlist",
                        "address": address,
                        "page": 1,
                        "offset": 1,
                        "sort": "desc",
                        "apikey": self.api_key,
                    },
                )
                last_tx_data = last_tx_resp.json()
                if last_tx_data.get("status") == "1" and last_tx_data.get("result"):
                    last_tx = last_tx_data["result"][0]
                    last_ts = int(last_tx["timeStamp"])
                    info.last_active = datetime.fromtimestamp(last_ts, tz=timezone.utc)
                    info.last_tx_hash = last_tx.get("hash")

                # Check if contract
                code_resp = await client.get(
                    self.api_url,
                    params={
                        "module": "proxy",
                        "action": "eth_getCode",
                        "address": address,
                        "tag": "latest",
                        "apikey": self.api_key,
                    },
                )
                code_data = code_resp.json()
                if code_data.get("result") and code_data["result"] != "0x":
                    info.is_contract = True
                    info.labels.append("contract")

            except httpx.HTTPError as e:
                info.error = f"API request failed: {e}"

        return info
