"""JurisMon Payment Provider Interface.

Abstract base provider allowing PayPal (first) and Stripe (future) to be
swapped seamlessly without altering application logic.
"""

import abc
from typing import Dict, Any, Optional
from pydantic import BaseModel


class SubscriptionDetails(BaseModel):
    id: str
    status: str  # 'active', 'cancelled', 'suspended', 'expired'
    plan_id: str
    subscriber_email: Optional[str] = None
    current_period_end: Optional[str] = None


class PaymentProvider(abc.ABC):
    """Abstract interface for recurring subscription providers."""

    @abc.abstractmethod
    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        """Verifies signature of incoming payment webhook."""
        pass

    @abc.abstractmethod
    def process_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parses webhook event and returns normalized subscription/payment updates."""
        pass

    @abc.abstractmethod
    def get_subscription(self, subscription_id: str) -> Optional[SubscriptionDetails]:
        """Fetches subscription status from payment provider API."""
        pass

    @abc.abstractmethod
    def cancel_subscription(self, subscription_id: str, reason: str = "Client requested") -> bool:
        """Cancels an active subscription."""
        pass
