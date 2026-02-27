import re
from datetime import datetime, timezone

import httpx

from bot.config import settings
from bot.services.chains.base import AddressInfo, BaseChainAnalyzer

# Etherscan V2 unified API — single endpoint for all EVM chains
ETHERSCAN_V2_URL = "https://api.etherscan.io/v2/api"

# Supported EVM networks
EVM_NETWORKS = {
    "ethereum": {
        "chainid": 1,
        "api_key": lambda: settings.etherscan_api_key,
        "symbol": "ETH",
        "decimals": 18,
    },
    "bsc": {
        "chainid": 56,
        "api_key": lambda: settings.bscscan_api_key or settings.etherscan_api_key,
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
        self.api_url = ETHERSCAN_V2_URL
        self.chainid = net_config["chainid"]
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

        base_params = {
            "chainid": self.chainid,
            "apikey": self.api_key,
        }

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                # Fetch balance
                balance_resp = await client.get(
                    self.api_url,
                    params={
                        **base_params,
                        "module": "account",
                        "action": "balance",
                        "address": address,
                        "tag": "latest",
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
                        **base_params,
                        "module": "account",
                        "action": "txlist",
                        "address": address,
                        "startblock": 0,
                        "endblock": 99999999,
                        "page": 1,
                        "offset": 5,
                        "sort": "asc",
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
                        **base_params,
                        "module": "proxy",
                        "action": "eth_getTransactionCount",
                        "address": address,
                        "tag": "latest",
                    },
                )
                txcount_data = txcount_resp.json()
                result = txcount_data.get("result", "")
                if result and result.startswith("0x"):
                    info.tx_count = int(result, 16)

                # Get last tx for last_active
                last_tx_resp = await client.get(
                    self.api_url,
                    params={
                        **base_params,
                        "module": "account",
                        "action": "txlist",
                        "address": address,
                        "page": 1,
                        "offset": 1,
                        "sort": "desc",
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
                        **base_params,
                        "module": "proxy",
                        "action": "eth_getCode",
                        "address": address,
                        "tag": "latest",
                    },
                )
                code_data = code_resp.json()
                code_result = code_data.get("result", "")
                if code_result and code_result.startswith("0x") and code_result != "0x":
                    info.is_contract = True
                    info.labels.append("contract")

            except httpx.HTTPError as e:
                info.error = f"API request failed: {e}"

        return info
