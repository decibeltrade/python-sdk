# Decibel Python SDK Specification

> **Version:** 1.0.0
> **Date:** 2026-04-07
> **Source:** https://docs.decibel.trade (OpenAPI 3.1.0 + AsyncAPI 3.0.0)

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Configuration](#3-configuration)
4. [Authentication](#4-authentication)
5. [Common Structures](#5-common-structures)
6. [Error Handling](#6-error-handling)
7. [Feature Specifications](#7-feature-specifications)
8. [Assumptions & Preferences](#8-assumptions--preferences)

---

## 1. Overview

The Decibel Python SDK provides a client library for interacting with the Decibel perpetual futures exchange built on the Aptos blockchain. The SDK SHALL support:

- **REST API** (read-only): Market data, account data, analytics, vaults, referrals
- **WebSocket API** (real-time): Streaming market data and account updates
- **On-Chain Transactions** (write): Order placement, account management, vault operations via Aptos blockchain transactions

### Terminology

| Term | Definition |
|------|-----------|
| **SHALL** | Required behavior |
| **SHOULD** | Preferred behavior |
| **COULD** | Optional behavior |
| **NOT** | Negation of SHALL/SHOULD/COULD |

---

## 2. Architecture

### 2.1 SDK Components

```
DecibelSDK
├── DecibelReadDex          # REST API + WebSocket subscriptions (async)
│   ├── Reader components   # 23 domain-specific readers
│   └── WebSocket client    # Real-time subscriptions
├── DecibelWriteDex         # On-chain transaction building + submission (async)
├── DecibelWriteDexSync     # Synchronous variant of write operations
├── DecibelAdminDex         # Protocol admin operations (async)
├── DecibelAdminDexSync     # Synchronous variant of admin operations
└── OrderStatusClient       # Order status polling
```

### 2.2 Component Interaction Diagram

```
┌─────────────┐     REST (GET)      ┌──────────────────────┐
│  ReadDex    │ ──────────────────> │  Trading HTTP Server  │
│  (readers)  │ <────────────────── │  /api/v1/*            │
└─────────────┘     JSON Response   └──────────────────────┘

┌─────────────┐     WSS             ┌──────────────────────┐
│  ReadDex    │ ──────────────────> │  WebSocket Server     │
│  (ws)       │ <────────────────── │  /ws                  │
└─────────────┘  subscribe/data     └──────────────────────┘

┌─────────────┐     Aptos Tx        ┌──────────────────────┐
│  WriteDex   │ ──────────────────> │  Aptos Fullnode       │
│             │ <────────────────── │  /v1/*                │
└─────────────┘  build/sign/submit  └──────────────────────┘

┌─────────────┐     REST (POST)     ┌──────────────────────┐
│  WriteDex   │ ──────────────────> │  Gas Station          │
│  (fee pay)  │ <────────────────── │  /submit              │
└─────────────┘  fee-payer tx       └──────────────────────┘
```

---

## 3. Configuration

### 3.1 Network Environments

The SDK SHALL support the following network configurations:

| Network | Chain ID | Fullnode URL | Trading HTTP URL | Trading WS URL |
|---------|----------|-------------|------------------|----------------|
| **Mainnet** | 1 | `https://api.mainnet.aptoslabs.com/v1` | `https://api.mainnet.aptoslabs.com/decibel` | `wss://api.mainnet.aptoslabs.com/decibel/ws` |
| **Testnet** | 2 | `https://api.testnet.aptoslabs.com/v1` | `https://api.testnet.aptoslabs.com/decibel` | `wss://api.testnet.aptoslabs.com/decibel/ws` |
| **Custom** | varies | user-provided | user-provided | user-provided |

### 3.2 DecibelConfig Structure

```python
class DecibelConfig:
    network: Network            # MAINNET | TESTNET | CUSTOM
    fullnode_url: str           # Aptos RPC endpoint
    trading_http_url: str       # REST API base URL
    trading_ws_url: str         # WebSocket endpoint
    gas_station_url: str | None # Optional fee payer service
    gas_station_api_key: str | None
    deployment: Deployment      # Package addresses
    chain_id: int | None
    compat_version: CompatVersion
```

### 3.3 Deployment Addresses

Each network has a `Deployment` with:
- `package`: Main smart contract address
- `usdc`: USDC token contract address
- `testc`: Test collateral address (testnet only)
- `perp_engine_global`: Global perp engine address

---

## 4. Authentication

### 4.1 REST API Authentication

The REST API SHALL require Bearer token authentication.

**Required Headers:**

| Header | Value | Required |
|--------|-------|----------|
| `Authorization` | `Bearer <API_KEY>` | YES |

The API key SHALL be obtained from the Geomi service (https://geomi.dev).

### 4.2 WebSocket Authentication

WebSocket connections SHALL authenticate via the `Sec-Websocket-Protocol` header:

```
Sec-Websocket-Protocol: decibel, <API_KEY>
```

### 4.3 On-Chain Authentication

On-chain transactions SHALL be signed with an Aptos Ed25519 private key. The SDK SHALL support:
- Direct account signing
- Delegated trading (signing on behalf of another account)
- Fee payer transactions (gas station)

---

## 5. Common Structures

### 5.1 Pagination

Paginated endpoints SHALL use the following query parameters:

```json
{
  "limit": { "type": "integer", "minimum": 0, "maximum": 1000 },
  "offset": { "type": "integer", "minimum": 0, "maximum": 10000 }
}
```

Paginated responses SHALL return:

```json
{
  "items": [ ... ],
  "total_count": 42
}
```

### 5.2 Sorting

Sortable endpoints SHALL accept:

```json
{
  "sort_key": "string",
  "sort_dir": "ASC" | "DESC" | null
}
```

### 5.3 History Filtering

History endpoints SHALL accept timestamp range filters:

```json
{
  "from": 1634567890000,
  "to": 1634654290000
}
```

Timestamps SHALL be in Unix milliseconds (int64).

### 5.4 Side Filter

Side filter values:
- `"buy"` — Maps to OpenLong/CloseShort
- `"sell"` — Maps to CloseLong/OpenShort

### 5.5 Aptos Address Format

All addresses SHALL be 66-character hex strings: `0x` followed by 64 hex characters.
Example: `0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef`

### 5.6 Numeric Precision

- Prices and sizes in API responses: `float64` (JSON `number`)
- On-chain prices/sizes: integer chain units (6 decimal places for USDC)
- Conversion: `chain_units = amount * 10^decimals`

---

## 6. Error Handling

### 6.1 REST API Error Response Format

All error responses SHALL follow this structure:

```json
{
  "status": "failed" | "timeout" | "notFound",
  "message": "Human-readable error description"
}
```

### 6.2 HTTP Status Codes

| Code | Condition |
|------|-----------|
| 200 | Successful request |
| 400 | Invalid or missing parameters |
| 401 | Authentication token missing/invalid |
| 403 | Token lacks necessary permissions |
| 404 | Resource doesn't exist |
| 429 | Rate limit exceeded |
| 500 | Server-side error |
| 504 | Query timeout |

### 6.3 SDK Exception Types

The SDK SHALL define:

- `FetchError(status, status_text, response_message)` — HTTP errors from REST API
- `TxnSubmitError` — Transaction submission failed (safe to retry)
- `TxnConfirmError(tx_hash, message)` — Transaction submitted but confirmation failed (may be on-chain; check status before retry)

### 6.4 Retry Strategy

- The SDK SHOULD implement exponential backoff for 500/504 responses
- The SDK SHALL NOT automatically retry on 400/401/403/404 errors
- For `TxnSubmitError`, the SDK COULD retry automatically
- For `TxnConfirmError`, the SDK SHALL NOT retry without checking transaction status first

---

## 7. Feature Specifications

Detailed API specifications are in the following documents:

- **[SPEC-REST.md](./SPEC-REST.md)** — REST API endpoints, request/response shapes, query parameters
- **[SPEC-WEBSOCKET.md](./SPEC-WEBSOCKET.md)** — WebSocket protocol, channels, message schemas

---

## 8. Assumptions & Preferences

### 8.1 Language & Runtime
- Python 3.11+ (matches `requires-python = ">=3.11"` in pyproject.toml)
- Async-first design using `asyncio` with synchronous wrappers
- `httpx` for HTTP client (async + sync support)
- `websockets` for WebSocket connections
- `pydantic` for data validation and serialization

### 8.2 SDK Design Preferences
- The SDK SHALL provide both async and sync interfaces for write operations
- The SDK SHALL use Pydantic BaseModel for all API response types
- Reader components SHALL be lazy-initialized on first access
- WebSocket subscriptions SHALL support both async and sync callbacks
- The SDK SHOULD handle BigInt JSON values (numbers exceeding JS safe integer range) via custom JSON parsing

### 8.3 Naming Conventions
- Python module names: `snake_case`
- Class names: `PascalCase`
- Method names: `snake_case`
- Private modules/functions: prefixed with `_`
- API field names: match server JSON keys exactly (snake_case)

### 8.4 Thread Safety
- Async clients are NOT required to be thread-safe (single event loop)
- Sync clients SHOULD be usable from any thread
- WebSocket subscriptions SHALL manage their own connection lifecycle

### 8.5 Deprecated Endpoints
The SDK SHOULD NOT implement deprecated endpoints. The following are deprecated:
- `/api/v1/user_fund_history` → use `/api/v1/account_fund_history`
- `/api/v1/user_positions` → use `/api/v1/account_positions`
- `/api/v1/user_owned_vaults` → use `/api/v1/account_owned_vaults`
- `/api/v1/user_vault_performance` → use `/api/v1/account_vault_performance`
