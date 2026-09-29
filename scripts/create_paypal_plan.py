"""Creates the PayPal product and subscription plan for JurisMon.

PayPal plans cannot be edited once they have subscribers, so this prints the
plan for confirmation and only creates it when you pass --confirm.

Usage:
    # See exactly what would be created
    python scripts/create_paypal_plan.py --price 29 --interval MONTH --trial-days 7

    # Create it for real
    python scripts/create_paypal_plan.py --price 29 --interval MONTH --trial-days 7 --confirm

Credentials come from .env: PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, PAYPAL_MODE.
On success the plan id is printed - put it in .env as PAYPAL_PLAN_ID.
"""

import os
import sys
import json
import argparse
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import requests
from dotenv import load_dotenv

load_dotenv()


def base_url(mode: str) -> str:
    return (
        "https://api-m.sandbox.paypal.com"
        if mode == "sandbox"
        else "https://api-m.paypal.com"
    )


def access_token(mode: str, client_id: str, secret: str) -> str:
    res = requests.post(
        f"{base_url(mode)}/v1/oauth2/token",
        auth=(client_id, secret),
        headers={"Accept": "application/json"},
        data={"grant_type": "client_credentials"},
        timeout=20,
    )
    if res.status_code != 200:
        sys.exit(f"PayPal auth failed ({res.status_code}): {res.text[:300]}")
    return res.json()["access_token"]


def create_product(mode: str, token: str) -> str:
    res = requests.post(
        f"{base_url(mode)}/v1/catalogs/products",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "name": "JurisMon",
            "description": "Municipal and statutory regulatory drift monitoring",
            "type": "SERVICE",
            "category": "SOFTWARE",
        },
        timeout=20,
    )
    if res.status_code not in (200, 201):
        sys.exit(f"Product creation failed ({res.status_code}): {res.text[:300]}")
    return res.json()["id"]


def build_plan(product_id: str, price: str, currency: str, interval: str,
               trial_days: int, name: str) -> dict:
    cycles = []

    if trial_days > 0:
        cycles.append({
            "frequency": {"interval_unit": "DAY", "interval_count": trial_days},
            "tenure_type": "TRIAL",
            "sequence": 1,
            "total_cycles": 1,
            "pricing_scheme": {"fixed_price": {"value": "0", "currency_code": currency}},
        })

    cycles.append({
        "frequency": {"interval_unit": interval, "interval_count": 1},
        "tenure_type": "REGULAR",
        "sequence": len(cycles) + 1,
        "total_cycles": 0,  # 0 means until cancelled
        "pricing_scheme": {"fixed_price": {"value": price, "currency_code": currency}},
    })

    return {
        "product_id": product_id,
        "name": name,
        "description": f"JurisMon subscription - {price} {currency} per {interval.lower()}",
        "billing_cycles": cycles,
        "payment_preferences": {
            "auto_bill_outstanding": True,
            "setup_fee_failure_action": "CONTINUE",
            "payment_failure_threshold": 3,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price", required=True, help="e.g. 29 or 29.00")
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--interval", default="MONTH", choices=["DAY", "WEEK", "MONTH", "YEAR"])
    parser.add_argument("--trial-days", type=int, default=0,
                        help="length of the free trial in days; 0 for none")
    parser.add_argument("--name", default="JurisMon Standard")
    parser.add_argument("--product-id", default=None,
                        help="reuse an existing PayPal product instead of creating one")
    parser.add_argument("--confirm", action="store_true",
                        help="actually create the plan (otherwise this is a preview)")
    args = parser.parse_args()

    client_id = os.getenv("PAYPAL_CLIENT_ID", "").strip()
    secret = os.getenv("PAYPAL_CLIENT_SECRET", "").strip()
    mode = os.getenv("PAYPAL_MODE", "sandbox").strip().lower()

    # Only --confirm talks to PayPal, so a preview must work before the
    # client has sent any credentials.
    if args.confirm and (not client_id or not secret or client_id.startswith("your-paypal")):
        sys.exit("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be set in .env")

    price = f"{float(args.price):.2f}"

    print(f"\nMode      : {mode}  ({base_url(mode)})")
    print(f"Plan name : {args.name}")
    print(f"Price     : {price} {args.currency} per {args.interval.lower()}")
    print(f"Trial     : {args.trial_days} day(s) free" if args.trial_days else "Trial     : none")

    if not args.confirm:
        preview = build_plan(args.product_id or "<product-created-on-confirm>",
                             price, args.currency, args.interval,
                             args.trial_days, args.name)
        print("\nPlan payload that would be sent:\n")
        print(json.dumps(preview, indent=2))
        print("\nPreview only. Re-run with --confirm to create it.")
        print("A plan cannot be edited once it has subscribers, so check the figures above.")
        return

    token = access_token(mode, client_id, secret)

    product_id = args.product_id or create_product(mode, token)
    print(f"\nProduct id: {product_id}")

    plan = build_plan(product_id, price, args.currency, args.interval,
                      args.trial_days, args.name)

    res = requests.post(
        f"{base_url(mode)}/v1/billing/plans",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        json=plan,
        timeout=20,
    )
    if res.status_code not in (200, 201):
        sys.exit(f"Plan creation failed ({res.status_code}): {res.text[:500]}")

    data = res.json()
    print(f"\nPlan created: {data['id']}  (status {data.get('status')})")
    print("\nAdd this line to .env:")
    print(f"    PAYPAL_PLAN_ID={data['id']}")


if __name__ == "__main__":
    main()
