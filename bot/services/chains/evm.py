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


# Known risky contract addresses (Tornado Cash, etc.)
KNOWN_RISKY = {
    "0xd90e2f925da726b50c4ed8d0fb90ad053324f31b": "Tornado Cash: Router",
    "0x722122df12d4e14e13ac3b6895a86e84145b6967": "Tornado Cash: Proxy",
    "0x12d66f87a04a9e220743712ce6d9bb1b5616b8fc": "Tornado Cash: 0.1 ETH",
    "0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936": "Tornado Cash: 1 ETH",
    "0x910cbd523d972eb0a6f4cae4618ad62622b39dbf": "Tornado Cash: 10 ETH",
    "0xa160cdab225685da1d56aa342ad8841c3b53f291": "Tornado Cash: 100 ETH",
    "0xd4b88df4d29f5cedd6857912842cff3b20c8cfa3": "Tornado Cash: DAI",
    "0xfd8610d20aa15b7b2e3be39b396a1bc3516c7144": "Tornado Cash: cDAI",
    "0xba214c1c1928a32bffe790263e38b4af9bfcd659": "Tornado Cash: WBTC",
    "0x169ad27a470d064dede56a2d3ff727986b15d52b": "FixedFloat",
    "0xb4955c2e7f0e09fa4feefc9fc8c62e6344b2b619": "Fake_Phishing",
}


async def _get_address_name_tag(
    client: httpx.AsyncClient, address: str,
) -> str | None:
    """Try to get Etherscan name tag by scraping the address page."""
    try:
        resp = await client.get(
            f"https://etherscan.io/address/{address}",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
            },
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        # Etherscan shows name tag in span.hash-tag
        tag = soup.select_one("span.hash-tag.text-truncate")
        if tag:
            return tag.get_text(strip=True)
        # Also check for warning banners (exploit, phishing)
        for alert in soup.select(".alert-warning, .alert-danger"):
            text = alert.get_text(" ", strip=True).lower()
            for keyword in ("exploit", "hack", "phish", "stolen", "heist", "scam"):
                if keyword in text:
                    return f"⚠️ {alert.get_text(' ', strip=True)[:100]}"
    except Exception:
        pass
    return None


async def _check_counterparty_labels(
    client: httpx.AsyncClient,
    api_url: str,
    base_params: dict,
    addresses: list[str],
) -> list[str]:
    """Check if any counterparty addresses are known risky entities."""
    found: list[str] = []
    for addr in addresses:
        label = KNOWN_RISKY.get(addr.lower())
        if label:
            found.append(f"{addr[:8]}...{addr[-4:]} → {label}")
    return found


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

                # Fetch more transactions to analyze counterparties
                full_tx_resp = await client.get(
                    self.api_url,
                    params={
                        **base_params,
                        "module": "account",
                        "action": "txlist",
                        "address": address,
                        "page": 1,
                        "offset": 50,
                        "sort": "desc",
                    },
                )
                full_tx_data = full_tx_resp.json()
                if full_tx_data.get("status") == "1" and full_tx_data.get("result"):
                    counterparty_addrs = set()
                    for tx in full_tx_data["result"]:
                        # Collect unique counterparty addresses
                        from_addr = tx.get("from", "").lower()
                        to_addr = tx.get("to", "").lower()
                        if from_addr and from_addr != address.lower():
                            counterparty_addrs.add(from_addr)
                        if to_addr and to_addr != address.lower():
                            counterparty_addrs.add(to_addr)
                    # Check counterparties for known labels via Etherscan
                    info.counterparties = await _check_counterparty_labels(
                        client, self.api_url, base_params, list(counterparty_addrs)[:20]
                    )

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

                # Try to get Etherscan name tag / warning labels
                name_tag = await _get_address_name_tag(client, address)
                if name_tag:
                    info.name_tag = name_tag
                    tag_lower = name_tag.lower()
                    for keyword in ("phish", "hack", "exploit", "scam", "steal", "heist", "fake"):
                        if keyword in tag_lower:
                            info.labels.append(name_tag)
                            break
                    for keyword in ("tornado", "mixer"):
                        if keyword in tag_lower:
                            info.labels.append(name_tag)
                            break

            except httpx.HTTPError as e:
                info.error = f"API request failed: {e}"

        return info
