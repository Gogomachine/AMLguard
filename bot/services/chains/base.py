from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod


@dataclass
class AddressInfo:
    address: str
    chain: str
    balance: str = "0"
    tx_count: int = 0
    first_seen: datetime | None = None
    last_active: datetime | None = None
    labels: list[str] = field(default_factory=list)
    token_transfers: int = 0
    is_contract: bool = False
    error: str | None = None


class BaseChainAnalyzer(ABC):
    """Base class for blockchain address analyzers."""

    chain_name: str = "unknown"

    @abstractmethod
    async def get_address_info(self, address: str) -> AddressInfo:
        """Fetch basic info about an address."""

    @abstractmethod
    def is_valid_address(self, address: str) -> bool:
        """Validate address format for this chain."""
