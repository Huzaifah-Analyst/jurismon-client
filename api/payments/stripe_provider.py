"""JurisMon Stripe Payment Provider (Pluggable Skeleton).

Ready to be activated if the client enables Stripe in South Sudan.
"""

import os
import logging
from typing import Dict, Any, Optional
from api.payments.base import PaymentProvider, SubscriptionDetails

logger = logging.getLogger("jurismon.stripe")


class StripeProvider(PaymentProvider):
    """Stripe Subscriptions Provider."""

    def __init__(self, api_key: Optional[str] = None, webhook_secret: Optional[str] = None):
        self.api_key = api_key or os.getenv("STRIPE_API_KEY", "")
        self.webhook_secret = webhook_secret or os.getenv("STRIPE_WEBHOOK_SECRET", "")

    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        logger.info("Stripe provider is inactive. Configure STRIPE_API_KEY to activate.")
        return False

    def process_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    def get_subscription(self, subscription_id: str) -> Optional[SubscriptionDetails]:
        return None

    def cancel_subscription(self, subscription_id: str, reason: str = "Client requested") -> bool:
        return False
