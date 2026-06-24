# Scripts

## check_quota_tier.py

Check the Azure AI Foundry quota tier (Free / Tier 0–6) for a subscription.  
Ref: [MS Docs](https://learn.microsoft.com/en-us/azure/foundry/openai/quotas-limits?tabs=python%2Ctier1#how-do-i-check-my-subscriptions-quota-tier)

### Requirements

- Python 3.10+, [uv](https://docs.astral.sh/uv/) (`brew install uv` / `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Azure subscription with Reader role
- `az login` (or service-principal env vars / Managed Identity)

Dependencies (`azure-identity`, `requests`, `tabulate`) are declared via PEP 723 inline metadata and installed automatically by `uv`.

### Run

```bash
# from repo root
az login
uv run scripts/check_quota_tier.py -s <SUBSCRIPTION_ID>
```

Service principal alternative:

```bash
export AZURE_TENANT_ID=… AZURE_CLIENT_ID=… AZURE_CLIENT_SECRET=…
uv run scripts/check_quota_tier.py -s <SUBSCRIPTION_ID>
```

### Sample output

```
╒═════════════════╤════════════════╤══════════════════════════╤═══════════════════════╕
│ Resource Name   │ Current Tier   │ Upgrade Policy           │ Assigned On           │
╞═════════════════╪════════════════╪══════════════════════════╪═══════════════════════╡
│ default         │ Tier 1         │ OnceUpgradeIsAvailable   │ 2025-10-18 05:09 UTC  │
╘═════════════════╧════════════════╧══════════════════════════╧═══════════════════════╛
```
