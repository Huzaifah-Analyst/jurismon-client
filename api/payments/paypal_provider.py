"""JurisMon PayPal Payment Provider.

Implements PayPal Subscriptions API integration, OAuth2 token generation,
subscription status tracking, and webhook event processing.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
import requests
from api.payments.base import PaymentProvider, SubscriptionDetails, SubscriptionRequest

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

        subscriber = resource.get("subscriber") or {}
        email = subscriber.get("email_address")

        # PayPal splits the name, and business accounts may send only a
        # business_name, so fall back through what is actually present.
        name_parts = subscriber.get("name") or {}
        full_name = " ".join(
            part for part in (name_parts.get("given_name"), name_parts.get("surname")) if part
        ).strip()
        subscriber_name = full_name or subscriber.get("business_name") or None

        next_billing = (resource.get("billing_info") or {}).get("next_billing_time")

        custom_id = resource.get("custom_id")

        return {
            "event_type": event_type,
            "subscription_id": sub_id,
            "status": normalized_status,
            "email": email,
            "subscriber_name": subscriber_name,
            "next_billing_at": next_billing,
            "plan_id": resource.get("plan_id"),
            "custom_id": custom_id,
            "raw": payload,
        }

    def create_subscription(
        self,
        plan_id: str,
        return_url: str,
        cancel_url: str,
        subscriber_email: Optional[str] = None,
        custom_id: Optional[str] = None,
    ) -> Optional[SubscriptionRequest]:
        """Starts a PayPal subscription and returns the approval URL.

        Nothing is charged here. The customer authorises payment at the returned
        URL, and only then does PayPal send BILLING.SUBSCRIPTION.ACTIVATED - so
        the webhook, not this call, is what marks a subscriber active.
        """
        if not plan_id:
            logger.error("Cannot create a subscription without a plan id.")
            return None

        payload: Dict[str, Any] = {
            "plan_id": plan_id,
            "application_context": {
                "brand_name": "JurisMon",
                "user_action": "SUBSCRIBE_NOW",
                "shipping_preference": "NO_SHIPPING",
                "return_url": return_url,
                "cancel_url": cancel_url,
            },
        }
        if custom_id:
            payload["custom_id"] = str(custom_id)
        if subscriber_email:
            payload["subscriber"] = {"email_address": subscriber_email}

        try:
            token = self._get_access_token()
            res = requests.post(
                f"{self.base_url}/v1/billing/subscriptions",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation",
                },
                json=payload,
                timeout=20,
            )
            res.raise_for_status()
            data = res.json()

            approval = next(
                (l.get("href") for l in data.get("links", []) if l.get("rel") == "approve"),
                None,
            )
            if not approval:
                logger.error("PayPal returned no approval link for plan %s.", plan_id)

            return SubscriptionRequest(
                id=data.get("id", ""),
                status=str(data.get("status", "")).lower(),
                approval_url=approval,
            )
        except Exception as e:
            logger.error(f"Error creating PayPal subscription for {plan_id}: {e}")
            return None

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
            return res.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Error cancelling PayPal subscription {subscription_id}: {e}")
            return False

    def suspend_subscription(self, subscription_id: str, reason: str = "Customer requested pause") -> bool:
        """Suspends (pauses) subscription on PayPal."""
        try:
            token = self._get_access_token()
            url = f"{self.base_url}/v1/billing/subscriptions/{subscription_id}/suspend"
            res = requests.post(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"reason": reason},
                timeout=10,
            )
            return res.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Error suspending PayPal subscription {subscription_id}: {e}")
            return False

    def activate_subscription(self, subscription_id: str, reason: str = "Customer requested resume") -> bool:
        """Activates (resumes) a suspended subscription on PayPal."""
        try:
            token = self._get_access_token()
            url = f"{self.base_url}/v1/billing/subscriptions/{subscription_id}/activate"
            res = requests.post(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"reason": reason},
                timeout=10,
            )
            return res.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Error activating PayPal subscription {subscription_id}: {e}")
            return False

    def get_plan_details(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Fetches live billing plan details from PayPal (GET /v1/billing/plans/{plan_id})."""
        try:
            token = self._get_access_token()
            url = f"{self.base_url}/v1/billing/plans/{plan_id}"
            res = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=10,
            )
            res.raise_for_status()
            data = res.json()
            cycles = data.get("billing_cycles") or []
            regular_cycle = next(
                (c for c in cycles if c.get("tenure_type") == "REGULAR"),
                cycles[-1] if cycles else {},
            )
            pricing_scheme = regular_cycle.get("pricing_scheme") or {}
            fixed_price = pricing_scheme.get("fixed_price") or {}
            frequency = regular_cycle.get("frequency") or {}

            raw_val = fixed_price.get("value")
            price_val = float(raw_val) if raw_val is not None else 0.0
            currency = fixed_price.get("currency_code", "")
            interval_unit = str(frequency.get("interval_unit", "")).lower()

            return {
                "id": data.get("id", plan_id),
                "name": data.get("name"),
                "status": data.get("status"),
                "price": price_val,
                "currency": currency,
                "interval": interval_unit,
                "raw": data,
            }
        except Exception as e:
            logger.error(f"Error fetching PayPal plan {plan_id}: {e}")
            return None


