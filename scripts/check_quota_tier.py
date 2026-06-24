#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "azure-identity",
#   "requests",
#   "tabulate",
# ]
# ///
"""
check_quota_tier.py
Check Azure AI Foundry (OpenAI) subscription quota tier via the Control Plane API.

Usage:
    python check_quota_tier.py --subscription-id <YOUR_SUBSCRIPTION_ID>
    python check_quota_tier.py          # lists available subscriptions to choose from

Authentication:
    Uses DefaultAzureCredential — any of the following work:
      • az login  (Azure CLI)
      • Environment variables AZURE_CLIENT_ID / AZURE_CLIENT_SECRET / AZURE_TENANT_ID
      • Managed Identity (when running on Azure)

Requirements:
    pip install azure-identity requests tabulate
"""

import argparse
import sys
import requests
from datetime import datetime, timezone

try:
    from azure.identity import DefaultAzureCredential
except ImportError:
    sys.exit("azure-identity not installed. Run: pip install azure-identity")

try:
    from tabulate import tabulate
except ImportError:
    sys.exit("tabulate not installed. Run: pip install tabulate")


API_VERSION = "2025-10-01-preview"
USAGES_API_VERSION = "2023-05-01"
MANAGEMENT_BASE = "https://management.azure.com"

# Canonical model names as listed in the quota-tier docs
VALID_MODELS: set[str] = {
    "codex-mini",
    "computer-use-preview",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4o",
    "gpt-4o-audio-preview",
    "gpt-4o-mini",
    "gpt-4o-mini-audio-preview",
    "gpt-4o-mini-realtime-preview",
    "gpt-4o-realtime-preview",
    "gpt-5",
    "gpt-5-chat",
    "gpt-5-codex",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-5-pro",
    "gpt-5.1",
    "gpt-5.1-chat",
    "gpt-5.1-codex",
    "gpt-5.1-codex-max",
    "gpt-5.1-codex-mini",
    "gpt-5.2",
    "gpt-5.2-chat",
    "gpt-5.2-codex",
    "gpt-5.3-chat",
    "gpt-5.3-codex",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "gpt-5.4-pro",
    "gpt-5.5",
    "gpt-audio",
    "gpt-chat-latest",
    "gpt-image-1",
    "gpt-image-1-mini",
    "gpt-image-1.5",
    "gpt-image-2",
    "gpt-realtime",
    "model-router",
    "o1",
    "o3",
    "o3-deep-research",
    "o3-mini",
    "o3-pro",
    "o4-mini",
    "text-embedding-3-large",
    "text-embedding-3-small",
}

# Azure regions with Azure OpenAI availability
AZURE_OPENAI_REGIONS: list[str] = [
    "australiaeast",
    "brazilsouth",
    "canadaeast",
    "eastasia",
    "eastus",
    "eastus2",
    "francecentral",
    "germanywestcentral",
    "japaneast",
    "koreacentral",
    "northcentralus",
    "northeurope",
    "norwayeast",
    "polandcentral",
    "southafricanorth",
    "southcentralus",
    "southeastasia",
    "southindia",
    "spaincentral",
    "swedencentral",
    "switzerlandnorth",
    "uaenorth",
    "uksouth",
    "westeurope",
    "westus",
    "westus3",
]


def get_access_token() -> str:
    credential = DefaultAzureCredential()
    token = credential.get_token("https://management.azure.com/.default")
    return token.token


def list_subscriptions(token: str) -> list[dict]:
    """Return all accessible subscriptions for the authenticated identity."""
    url = f"{MANAGEMENT_BASE}/subscriptions?api-version=2022-12-01"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.get(url, headers=headers, timeout=30)
    if not resp.ok:
        sys.exit(f"Failed to list subscriptions ({resp.status_code}): {resp.text}")
    return resp.json().get("value", [])


def pick_subscription(token: str) -> str:
    """List subscriptions and prompt the user to select one."""
    subs = list_subscriptions(token)
    if not subs:
        sys.exit("No subscriptions found for the authenticated account.")

    if len(subs) == 1:
        sub = subs[0]
        print(f"[*] Using subscription: {sub['displayName']} ({sub['subscriptionId']})")
        return sub["subscriptionId"]

    print()
    print(tabulate(
        [[i + 1, s["displayName"], s["subscriptionId"], s.get("state", "—")]
         for i, s in enumerate(subs)],
        headers=["#", "Name", "Subscription ID", "State"],
        tablefmt="simple",
    ))
    print()

    while True:
        try:
            choice = input(f"Select a subscription [1-{len(subs)}]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(subs):
                return subs[idx]["subscriptionId"]
        except (ValueError, KeyboardInterrupt):
            pass
        print(f"  Please enter a number between 1 and {len(subs)}.")


def fetch_quota_tiers(subscription_id: str, token: str) -> dict:
    url = (
        f"{MANAGEMENT_BASE}/subscriptions/{subscription_id}"
        f"/providers/Microsoft.CognitiveServices/quotaTiers"
        f"?api-version={API_VERSION}"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code == 401:
        sys.exit("Authentication failed. Run 'az login' or set service-principal env vars.")
    if resp.status_code == 403:
        sys.exit("Access denied. Ensure your account has 'Reader' or higher on the subscription.")
    if not resp.ok:
        sys.exit(f"API error {resp.status_code}: {resp.text}")
    return resp.json()


def format_date(iso_str: str) -> str:
    """Convert ISO 8601 UTC string to a readable local date."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M %Z")
    except Exception:
        return iso_str


def print_summary_table(items: list[dict], subscription_id: str) -> None:
    print(f"\n{'='*70}")
    print(f"  Azure AI Foundry — Quota Tier Summary")
    print(f"  Subscription : {subscription_id}")
    print(f"  Queried at   : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*70}\n")

    rows = []
    for item in items:
        props = item.get("properties", {})
        rows.append({
            "Resource Name": item.get("name", "—"),
            "Resource ID": item.get("id", "—"),
            "Current Tier": props.get("currentTierName", "—"),
            "Assigned On": format_date(props.get("assignmentDate", "")) if props.get("assignmentDate") else "—",
            "Upgrade Policy": props.get("tierUpgradePolicy", "—"),
        })

    if not rows:
        print("  No quota tier data returned for this subscription.\n")
        return

    # Summary table
    print(tabulate(
        [[r["Resource Name"], r["Current Tier"], r["Upgrade Policy"], r["Assigned On"]] for r in rows],
        headers=["Resource Name", "Current Tier", "Upgrade Policy", "Assigned On"],
        tablefmt="fancy_grid",
    ))

    print()

    # Detailed table (full resource IDs)
    if any(r["Resource ID"] != "—" for r in rows):
        print("  Full Resource IDs:")
        print(tabulate(
            [[r["Resource Name"], r["Resource ID"]] for r in rows],
            headers=["Resource Name", "Resource ID"],
            tablefmt="simple",
        ))
        print()

    # Tier upgrade policy legend
    print("  Upgrade Policy values:")
    policies = {
        "OnceUpgradeIsAvailable": "Automatically upgrade when a higher tier is available.",
        "NoAutoUpgrade":          "Locked to current tier; no automatic upgrades.",
    }
    for k, v in policies.items():
        print(f"    {k:<30}  {v}")
    print()


def pick_model() -> str:
    """Print a numbered list of models and return the selected model name."""
    sorted_models = sorted(VALID_MODELS)
    print()
    print(tabulate(
        [[i + 1, m] for i, m in enumerate(sorted_models)],
        headers=["#", "Model"],
        tablefmt="simple",
    ))
    print()

    while True:
        try:
            raw = input(f"Select a model [1-{len(sorted_models)}]: ").strip()
        except KeyboardInterrupt:
            print()
            sys.exit(0)
        # Accept a number
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(sorted_models):
                return sorted_models[idx]
            print(f"  Please enter a number between 1 and {len(sorted_models)}.")
            continue
        # Also accept typing the name directly
        name = raw.lower()
        if name in VALID_MODELS:
            return name
        suggestions = [m for m in VALID_MODELS if name in m]
        if suggestions:
            print(f"  '{raw}' not recognised. Did you mean: {', '.join(sorted(suggestions))}?")
        else:
            print(f"  '{raw}' is not valid. Enter a number from the list or a model name.")


def pick_region() -> str:
    """Present a numbered list of Azure OpenAI regions and return the chosen one."""
    print()
    print(tabulate(
        [[i + 1, r] for i, r in enumerate(AZURE_OPENAI_REGIONS)],
        headers=["#", "Region"],
        tablefmt="simple",
    ))
    print()
    while True:
        try:
            choice = input(f"Select a region [1-{len(AZURE_OPENAI_REGIONS)}]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(AZURE_OPENAI_REGIONS):
                return AZURE_OPENAI_REGIONS[idx]
        except (ValueError, KeyboardInterrupt):
            pass
        print(f"  Please enter a number between 1 and {len(AZURE_OPENAI_REGIONS)}.")


def fetch_model_quota(subscription_id: str, location: str, token: str) -> list[dict]:
    """Call the CognitiveServices Usages API for a given subscription + region."""
    url = (
        f"{MANAGEMENT_BASE}/subscriptions/{subscription_id}"
        f"/providers/Microsoft.CognitiveServices/locations/{location}"
        f"/usages?api-version={USAGES_API_VERSION}"
    )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code == 404:
        return []  # region not enabled / no OpenAI resources
    if not resp.ok:
        print(f"  Warning: could not fetch usages for {location} ({resp.status_code})")
        return []
    return resp.json().get("value", [])


def print_model_quota_table(usages: list[dict], model: str, location: str, subscription_id: str) -> None:
    # Filter entries whose name contains the model (case-insensitive)
    matches = [
        u for u in usages
        if model.lower() in u.get("name", {}).get("value", "").lower()
        or model.lower() in u.get("name", {}).get("localizedValue", "").lower()
    ]

    print(f"\n{'='*70}")
    print(f"  Model Quota — {model}")
    print(f"  Subscription : {subscription_id}")
    print(f"  Region       : {location}")
    print(f"  Queried at   : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*70}\n")

    if not matches:
        print(f"  No quota entries found for '{model}' in {location}.")
        print("  The model may not be available in this region, or no quota has been allocated.\n")
        print("  ── How to request quota ──────────────────────────────────────────────")
        print("  1. Open the Azure AI Foundry quota request form:")
        print("       https://aka.ms/oai/stuquotarequest")
        print("  2. Sign in with the account that owns the subscription.")
        print("  3. Select your Subscription, Region, and Model.")
        print("  4. Enter the TPM / RPM amount you need and a business justification.")
        print("  5. Submit — approved requests are usually processed within 1–3 business days.")
        print()
        print("  Tips:")
        print("  • Check model regional availability before requesting:")
        print("      https://learn.microsoft.com/azure/ai-services/openai/concepts/models")
        print("  • Quota increases are more likely to be approved when existing quota")
        print("    is already being actively used.")
        print("  • Enterprise / EA customers are eligible for higher tiers automatically.")
        print()
        return

    rows = []
    for u in matches:
        limit = u.get("limit", 0) or 0
        current = u.get("currentValue", 0) or 0
        unit = u.get("unit", "")
        pct = f"{current / limit * 100:.1f}%" if limit else "—"
        rows.append([
            u.get("name", {}).get("localizedValue", u.get("name", {}).get("value", "—")),
            f"{current:,}",
            f"{limit:,}",
            pct,
            unit,
        ])

    print(tabulate(
        rows,
        headers=["Quota Name", "Used", "Limit", "Used %", "Unit"],
        tablefmt="fancy_grid",
    ))
    print()

    # Guidance when all matched entries have a limit of zero
    if all((u.get("limit") or 0) == 0 for u in matches):
        print("  ⚠  All quota limits for this model are set to 0 in this region.")
        print("  ── How to request quota ──────────────────────────────────────────────")
        print("  1. Open the Azure AI Foundry quota request form:")
        print("       https://aka.ms/oai/stuquotarequest")
        print("  2. Sign in with the account that owns the subscription.")
        print("  3. Select your Subscription, Region, and Model.")
        print("  4. Enter the TPM / RPM amount you need and a business justification.")
        print("  5. Submit — approved requests are usually processed within 1–3 business days.")
        print()
        print("  Tips:")
        print("  • Check model regional availability before requesting:")
        print("      https://learn.microsoft.com/azure/ai-services/openai/concepts/models")
        print("  • Quota increases are more likely to be approved when existing quota")
        print("    is already being actively used.")
        print("  • Enterprise / EA customers are eligible for higher tiers automatically.")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check Azure AI Foundry quota tier for an Azure subscription.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--subscription-id", "-s",
        required=False,
        metavar="SUBSCRIPTION_ID",
        help="Azure subscription ID (GUID). If omitted, available subscriptions are listed for selection.",
    )
    args = parser.parse_args()

    print("[*] Acquiring access token via DefaultAzureCredential…")
    token = get_access_token()

    if args.subscription_id:
        subscription_id = args.subscription_id.strip()
    else:
        print("[*] No subscription ID provided — fetching available subscriptions…")
        subscription_id = pick_subscription(token)

    print(f"[*] Fetching quota tiers for subscription: {subscription_id}…")
    data = fetch_quota_tiers(subscription_id, token)

    items = data.get("value", [])
    print_summary_table(items, subscription_id)

    # ── Optional: per-model quota lookup ─────────────────────────────────────
    try:
        answer = input("Check quota for a specific model? [y/N]: ").strip().lower()
    except KeyboardInterrupt:
        print()
        sys.exit(0)

    if answer == "y":
        model = pick_model()
        print("\n[*] Select a region to query:")
        region = pick_region()
        print(f"[*] Fetching model quota for '{model}' in {region}…")
        usages = fetch_model_quota(subscription_id, region, token)
        print_model_quota_table(usages, model, region, subscription_id)


if __name__ == "__main__":
    main()
