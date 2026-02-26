"""
Multi-chain address analyzer — detects chain and fetches data.
"""

from bot.services.chains.base import AddressInfo, BaseChainAnalyzer
from bot.services.chains.evm import EVMAnalyzer, EVM_ADDRESS_RE
from bot.services.chains.bitcoin import BitcoinAnalyzer, BTC_ADDRESS_RE
from bot.services.chains.solana import SolanaAnalyzer, SOL_ADDRESS_RE
from bot.services.chains.tron import TronAnalyzer, TRON_ADDRESS_RE


def detect_chain(address: str) -> str | None:
    """Detect which blockchain an address belongs to based on format."""
    if EVM_ADDRESS_RE.match(address):
        return "ethereum"
    if BTC_ADDRESS_RE.match(address):
        return "bitcoin"
    if TRON_ADDRESS_RE.match(address):
        return "tron"
    if SOL_ADDRESS_RE.match(address):
        return "solana"
    return None


def get_analyzer(chain: str) -> BaseChainAnalyzer:
    """Get the appropriate analyzer for a chain."""
    analyzers: dict[str, BaseChainAnalyzer] = {
        "ethereum": EVMAnalyzer("ethereum"),
        "bsc": EVMAnalyzer("bsc"),
        "bitcoin": BitcoinAnalyzer(),
        "solana": SolanaAnalyzer(),
        "tron": TronAnalyzer(),
    }
    return analyzers.get(chain)


async def analyze_address(address: str, chain: str | None = None) -> AddressInfo:
    """
    Analyze a crypto address. Auto-detects chain if not specified.
    """
    address = address.strip()

    if chain is None:
        chain = detect_chain(address)

    if chain is None:
        return AddressInfo(
            address=address,
            chain="unknown",
            error="Could not detect blockchain. Please specify the chain.",
        )

    analyzer = get_analyzer(chain)
    if analyzer is None:
        return AddressInfo(
            address=address,
            chain=chain,
            error=f"Chain '{chain}' is not supported yet.",
        )

    return await analyzer.get_address_info(address)
