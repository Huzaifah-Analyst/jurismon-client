"""JurisMon PayPal Payment Provider.

Implements PayPal Subscriptions API integration, OAuth2 token generation,
subscription status tracking, and webhook event processing.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
import requests
from api.payments.base import PaymentProvider, SubscriptionDetails

logger = logging.getLogger("jurismon.paypal")


class PayPalProvider(PaymentProvider):
    """PayPal Subscriptions API provider."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        mode: Optional[str] = None,
        webhook_id: Optional[str] = None,
    ):
        self.client_id = client_id or os.getenv("PAYPAL_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("PAYPAL_CLIENT_SECRET", "")
        self.mode = mode or os.getenv("PAYPAL_MODE", "sandbox")
        self.webhook_id = webhook_id or os.getenv("PAYPAL_WEBHOOK_ID", "")
        
        self.base_url = (
            "https://api-m.sandbox.paypal.com"
            if self.mode == "sandbox"
            else "https://api-m.paypal.com"
        )
        self._access_token: Optional[str] = None

    def _get_access_token(self) -> str:
        """Retrieves or refreshes PayPal OAuth2 Bearer token."""
        if not self.client_id or not self.client_secret:
            raise ValueError("PayPal Client ID and Secret must be configured.")

        url = f"{self.base_url}/v1/oauth2/token"
        headers = {"Accept": "application/json", "Accept-Language": "en_US"}
        data = {"grant_type": "client_credentials"}

        res = requests.post(
            url, auth=(self.client_id, self.client_secret), headers=headers, data=data, timeout=10
        )
        res.raise_for_status()
        token_data = res.json()
        self._access_token = token_data["access_token"]
        return self._access_token

    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        """Verifies webhook signature with PayPal API."""
        if not self.webhook_id:
            # Returning True here would let anyone forge a subscription-activated
            # event, so an unconfigured webhook rejects every delivery instead.
            logger.error(
                "PAYPAL_WEBHOOK_ID is not configured - rejecting webhook. "
                "Set it to the Webhook ID shown in the PayPal developer dashboard."
            )
            return False

        try:
            token = self._get_access_token()
            verify_url = f"{self.base_url}/v1/notifications/verify-webhook-signature"
            verify_payload = {
                "auth_algo": headers.get("paypal-auth-algo"),
                "cert_url": headers.get("paypal-cert-url"),
                "transmission_id": headers.get("paypal-transmission-id"),
                "transmission_sig": headers.get("paypal-transmission-sig"),
                "transmission_time": headers.get("paypal-transmission-time"),
                "webhook_id": self.webhook_id,
                "webhook_event": json.loads(body.decode("utf-8")),
            }
            res = requests.post(
                verify_url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=verify_payload,
                timeout=10,
            )
            res.raise_for_status()
            data = res.json()
            return data.get("verification_status") == "SUCCESS"
        except Exception as e:
            logger.error(f"Error verifying PayPal webhook: {e}")
            return False

    def process_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Maps PayPal subscription events to internal status."""
        event_type = payload.get("event_type", "")
        resource = payload.get("resource", {})
        
        status_map = {
            "BILLING.SUBSCRIPTION.ACTIVATED": "active",
            "BILLING.SUBSCRIPTION.CANCELLED": "cancelled",
            "BILLING.SUBSCRIPTION.SUSPENDED": "suspended",
            "BILLING.SUBSCRIPTION.EXPIRED": "expired",
            "PAYMENT.SALE.COMPLETED": "active",
        }

        normalized_status = status_map.get(event_type, "unknown")
        sub_id = resource.get("id") or resource.get("billing_agreement_id", "")
        email = resource.get("subscriber", {}).get("email_address")

        return {
            "event_type": event_type,
            "subscription_id": sub_id,
            "status": normalized_status,
            "email": email,
            "raw": payload,
        }

    def get_subscription(self, subscription_id: str) -> Optional[SubscriptionDetails]:
        """Fetches live subscription info from PayPal."""
        try:
            token = self._get_access_token()
            url = f"{self.base_url}/v1/billing/subscriptions/{subscription_id}"
            res = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=10,
            )
            res.raise_for_status()
            data = res.json()
            return SubscriptionDetails(
                id=data.get("id"),
                status=data.get("status", "").lower(),
                plan_id=data.get("plan_id", ""),
                subscriber_email=data.get("subscriber", {}).get("email_address"),
                current_period_end=data.get("billing_info", {}).get("next_billing_time"),
            )
        except Exception as e:
            logger.error(f"Error fetching PayPal subscription {subscription_id}: {e}")
            return None

    def cancel_subscription(self, subscription_id: str, reason: str = "Client requested") -> bool:
        """Cancels subscription on PayPal."""
        try:
            token = self._get_access_token()
            url = f"{self.base_url}/v1/billing/subscriptions/{subscription_id}/cancel"
            res = requests.post(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"reason": reason},
                timeout=10,
            )
            return res.status_code == 204
        except Exception as e:
            logger.error(f"Error cancelling PayPal subscription {subscription_id}: {e}")
            return False
