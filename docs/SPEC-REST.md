# Decibel Python SDK — REST API Specification

> **Source:** OpenAPI 3.1.0 spec at `https://docs.decibel.trade/api-reference/openapi.json`
> **Base URLs:**
> - Mainnet: `https://api.mainnet.aptoslabs.com/decibel`
> - Testnet: `https://api.testnet.aptoslabs.com/decibel`

## Table of Contents

1. [Transport & Headers](#1-transport--headers)
2. [Market Data Endpoints](#2-market-data-endpoints)
3. [Account Endpoints](#3-account-endpoints)
4. [User Endpoints](#4-user-endpoints)
5. [TWAP Endpoints](#5-twap-endpoints)
6. [Bulk Order Endpoints](#6-bulk-order-endpoints)
7. [Vault Endpoints](#7-vault-endpoints)
8. [Analytics Endpoints](#8-analytics-endpoints)
9. [Referral Endpoints](#9-referral-endpoints)
10. [Predeposit Endpoints](#10-predeposit-endpoints)
11. [Shared Data Schemas](#11-shared-data-schemas)

---

## 1. Transport & Headers

### 1.1 Protocol

All REST endpoints SHALL use HTTPS GET requests. There are no POST/PUT/DELETE endpoints in the read API (writes go on-chain).

**Exception:** Subaccount rename uses PATCH (see Section 4).

### 1.2 Required Headers

| Header | Value | Required |
|--------|-------|----------|
| `Authorization` | `Bearer <API_KEY>` | YES |
| `Origin` | e.g. `https://app.decibel.trade` | YES |
| `Content-Type` | `application/json` | For PATCH only |

### 1.3 Response Format

All successful responses SHALL return JSON with `Content-Type: application/json`.

### 1.4 Query Parameter Encoding

- Pagination parameters SHALL be sent as flat query params: `?limit=10&offset=0`
- Sorting parameters SHALL be sent as: `?sort_key=volume&sort_dir=DESC`
- Filter parameters SHALL be sent as: `?from=1634567890000&to=1634654290000`

---

## 2. Market Data Endpoints

### 2.1 Get Market Prices

Retrieve current prices for one or all markets.

```
GET /api/v1/prices
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `market` | string | No | Market address. Use `"all"` or omit for all markets. |

**Response:** `200 OK`
```json
[
  {
    "market": "0x...",
    "oracle_px": 50125.75,
    "mark_px": 50120.5,
    "mid_px": 50122.25,
    "funding_rate_bps": 5.0,
    "is_funding_positive": true,
    "transaction_unix_ms": 1699564800000,
    "open_interest": 125000.5
  }
]
```

**Schema:** Array of `PriceDto`

**Edge behaviors:**
- `funding_rate_bps` from REST is the raw (unsmoothed) on-chain value. WebSocket provides EMA-smoothed values.
- Returns `404` if a specific market address is not found.

---

### 2.2 Get All Available Markets

```
GET /api/v1/markets
```

**Query Parameters:** None

**Response:** `200 OK`
```json
[
  {
    "market_addr": "0x...",
    "market_name": "BTC-PERP",
    "sz_decimals": 4,
    "max_leverage": 50,
    "tick_size": 100,
    "min_size": 1000,
    "lot_size": 100,
    "max_open_interest": 1000000.0,
    "px_decimals": 1,
    "mode": "Open",
    "unrealized_pnl_haircut_bps": 1000
  }
]
```

**Schema:** Array of `MarketDto`

**Notes:**
- `tick_size`, `min_size`, `lot_size` are in chain units (integers)
- `mode` values: `"Open"`, `"ReduceOnly"`, `"CloseOnly"`
- `unrealized_pnl_haircut_bps`: basis points (1000 = 10%)

---

### 2.3 Get Candlestick (OHLC) Data

```
GET /api/v1/candlesticks
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `market` | string | Yes | Market address |
| `interval` | string | Yes | One of: `1m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `1d`, `1w`, `1mo` |
| `startTime` | int64 | Yes | Start time in Unix milliseconds |
| `endTime` | int64 | Yes | End time in Unix milliseconds |

**Response:** `200 OK`
```json
[
  {
    "t": 1761588000000,
    "T": 1761591599999,
    "o": 100.0,
    "h": 102.0,
    "l": 98.0,
    "c": 100.0,
    "v": 1000.0,
    "i": "1h"
  }
]
```

**Schema:** Array of `CandlestickResponseItemDto`

| Field | Description |
|-------|-------------|
| `t` | Open time (Unix ms) |
| `T` | Close time (Unix ms) |
| `o` | Open price |
| `h` | High price |
| `l` | Low price |
| `c` | Close price |
| `v` | Volume |
| `i` | Interval string |

**Edge behaviors:**
- Maximum 1000 candles per request. Returns `400` if exceeded.
- Returns `400` if `startTime > endTime`.
- Returns `404` if market not found.
- Missing intervals are interpolated using last known close price.

---

### 2.4 Get Trades (Market)

```
GET /api/v1/trades
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `market` | string | Yes | Market address |
| `order_id` | string | No | Filter by specific order ID |
| `limit` | int32 | Yes* | Max results (0–1000) |
| `offset` | int32 | Yes* | Pagination offset (0–10000) |

**Response:** `200 OK` — `PaginatedResponse<TradeDto>`

```json
{
  "items": [
    {
      "account": "0x...",
      "market": "0x...",
      "action": "Open Long",
      "source": "OrderFill",
      "trade_id": "3647276",
      "size": 1.5,
      "price": 50125.75,
      "is_profit": true,
      "realized_pnl_amount": 187.5,
      "realized_funding_amount": -12.3,
      "is_rebate": true,
      "fee_amount": 25.06,
      "order_id": "45678",
      "client_order_id": "order_123",
      "transaction_unix_ms": 1699564800000,
      "transaction_version": 3647276285
    }
  ],
  "total_count": 1
}
```

**Notes:**
- `action` values: `"Open Long"`, `"Close Long"`, `"Open Short"`, `"Close Short"`
- `source` values: `"OrderFill"`, `"MarginCall"`, `"BackStopLiquidation"`, `"ADL"`, `"MarketDelisted"`
- Results ordered by most recent first.

---

### 2.5 Get Asset Contexts

```
GET /api/v1/asset_contexts
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `market` | string | No | Filter by market address |

**Response:** `200 OK`
```json
[
  {
    "market": "0x...",
    "volume_24h": 5000000.0,
    "open_interest": 125000.5,
    "mark_price": 50120.5,
    "mid_price": 50122.25,
    "oracle_price": 50125.75,
    "previous_day_price": 49800.0,
    "price_change_pct_24h": 0.65
  }
]
```

**Schema:** Array of `AssetContextDto`

---

## 3. Account Endpoints

### 3.1 Get Account Overview

```
GET /api/v1/account_overviews
```

**Query Parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `account` | string | Yes | — | Subaccount address |
| `volume_window` | string | No | — | `"7d"`, `"14d"`, `"30d"`, or `"90d"` |
| `include_performance` | bool | No | `false` | Include historical return metrics |
| `performance_lookback_days` | int32 | No | `90` | Lookback window in days |

**Response:** `200 OK`
```json
{
  "perp_equity_balance": 10064.88,
  "unrealized_pnl": 154.0,
  "realized_pnl": 1250.5,
  "unrealized_funding_cost": -87.84,
  "cross_margin_ratio": 0.01,
  "maintenance_margin": 115.29,
  "cross_account_leverage_ratio": 40.99,
  "total_margin": 9998.72,
  "usdc_cross_withdrawable_balance": 9843.79,
  "usdc_isolated_withdrawable_balance": 0.0,
  "margin_deficit": -12.06,
  "volume": null,
  "all_time_return": null,
  "pnl_90d": null,
  "sharpe_ratio": null,
  "max_drawdown": null,
  "weekly_win_rate_12w": null,
  "average_cash_position": null,
  "average_leverage": null,
  "cross_account_position": null,
  "vault_equity": 259.73,
  "net_deposits": 30277044.96,
  "liquidation_fees_paid": 45.5,
  "liquidation_losses": null
}
```

**Schema:** `AccountOverviewDto`

**Required fields:** `perp_equity_balance`, `unrealized_pnl`, `unrealized_funding_cost`, `cross_margin_ratio`, `maintenance_margin`, `cross_account_leverage_ratio`, `total_margin`, `usdc_cross_withdrawable_balance`, `usdc_isolated_withdrawable_balance`, `margin_deficit`

**Nullable fields:** `all_time_return`, `average_cash_position`, `average_leverage`, `cross_account_position`, `liquidation_fees_paid`, `liquidation_losses`, `max_drawdown`, `net_deposits`, `pnl_90d`, `realized_pnl`, `sharpe_ratio`, `vault_equity`, `volume`, `weekly_win_rate_12w`

**Edge behaviors:**
- `margin_deficit`: 0 when healthy, negative when account has margin hole
- `liquidation_losses`: null for regular users (only vault/BLP accounts)
- Performance fields are null unless `include_performance=true`
- `volume` is null unless `volume_window` is provided

---

### 3.2 Get Account Positions

```
GET /api/v1/account_positions
```

**Query Parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `account` | string | Yes | — | Subaccount address |
| `limit` | int32 | No | `500` | Max results |
| `include_deleted` | bool | No | `false` | Include closed positions |
| `market_address` | string | No | — | Filter by market |

**Response:** `200 OK`
```json
[
  {
    "market": "0x...",
    "user": "0x...",
    "size": 2.5,
    "user_leverage": 10,
    "entry_price": 49800.0,
    "is_isolated": false,
    "is_deleted": false,
    "unrealized_funding": -25.5,
    "estimated_liquidation_price": 45000.0,
    "transaction_version": 12345681,
    "has_fixed_sized_tpsls": false,
    "tp_order_id": "tp_001",
    "tp_trigger_price": 52000.0,
    "tp_limit_price": 51900.0,
    "sl_order_id": "sl_001",
    "sl_trigger_price": 48000.0,
    "sl_limit_price": null
  }
]
```

**Schema:** Array of `PositionDto`

**Notes:**
- `size` > 0 = long, `size` < 0 = short
- TP/SL fields are nullable (null when no TP/SL set)
- `tp_trigger_price` and `sl_trigger_price` are in human-readable price format (float)

---

### 3.3 Get Account's Open Orders

```
GET /api/v1/open_orders
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | Subaccount address |
| `limit` | int32 | Yes | Max results (0–1000) |
| `offset` | int32 | Yes | Pagination offset (0–10000) |

**Response:** `200 OK` — `PaginatedResponse<OrderDto>`

---

### 3.4 Get User Order History

```
GET /api/v1/order_history
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | Subaccount address |
| `limit` | int32 | Yes | Max results |
| `offset` | int32 | Yes | Pagination offset |
| `from` | int64 | Yes | Start timestamp (Unix ms) |
| `to` | int64 | Yes | End timestamp (Unix ms) |
| `sort_key` | string | Yes | Sort field (e.g. `"timestamp"`) |
| `sort_dir` | string | No | `"ASC"` or `"DESC"` |
| `market` | string | No | Filter by market address |
| `order_type` | string | No | `"Limit"`, `"Market"`, `"Stop Limit"`, `"Stop Market"` |
| `status` | string | No | `"Open"`, `"Filled"`, `"Cancelled"`, `"Expired"` |
| `side` | string | No | `"buy"` or `"sell"` |
| `reduce_only` | bool | No | Filter reduce-only orders |

**Response:** `200 OK` — `PaginatedResponse<OrderDto>`

**Note:** Page size capped at 200.

---

### 3.5 Get User Trade History

```
GET /api/v1/trade_history
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | Subaccount address |
| `limit` | int32 | Yes | Max results |
| `offset` | int32 | Yes | Pagination offset |
| `from` | int64 | Yes | Start timestamp (Unix ms) |
| `to` | int64 | Yes | End timestamp (Unix ms) |
| `sort_key` | string | Yes | Sort field |
| `sort_dir` | string | No | `"ASC"` or `"DESC"` |
| `market` | string | No | Filter by market |
| `order_id` | string | No | Filter by order ID (requires `market`) |
| `side` | string | No | `"buy"` or `"sell"` |

**Response:** `200 OK` — `PaginatedResponse<TradeDto>`

**Edge behaviors:**
- Returns `400` if `order_id` provided without `market`.
- Page size capped at 200.

---

### 3.6 Get User Funding Rate History

```
GET /api/v1/funding_rate_history
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | Subaccount address |
| `limit` | int32 | Yes | Max results |
| `offset` | int32 | Yes | Pagination offset |
| `from` | int64 | Yes | Start timestamp |
| `to` | int64 | Yes | End timestamp |
| `sort_key` | string | Yes | Sort field |
| `sort_dir` | string | No | Direction |
| `market` | string | No | Filter by market |
| `side` | string | No | `"buy"` or `"sell"` |

**Response:** `200 OK` — `PaginatedResponse<FundingRateHistory>`

```json
{
  "items": [
    {
      "market": "0x...",
      "action": "Close Long",
      "size": 1.0,
      "realized_funding_amount": -15.5,
      "is_rebate": false,
      "fee_amount": 5.15,
      "transaction_unix_ms": 1735758000000
    }
  ],
  "total_count": 1
}
```

**Notes:**
- `realized_funding_amount`: negative = trader PAID funding, positive = trader RECEIVED funding

---

### 3.7 Get Subaccounts

```
GET /api/v1/subaccounts
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `owner` | string | Yes | Owner wallet address |

**Response:** `200 OK`
```json
[
  {
    "subaccount_address": "0x...",
    "subaccount_name": "Primary",
    "subaccount_number": 0,
    "is_active": true
  }
]
```

**Schema:** Array of `SubaccountDto`

---

## 4. User Endpoints

### 4.1 Get Single Order Details

```
GET /api/v1/orders
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `market` | string | Yes | Market address |
| `account` | string | Yes | Subaccount address |
| `order_id` | string | No* | Order ID (provide one of `order_id` or `client_order_id`) |
| `client_order_id` | string | No* | Client order ID |

**Response:** `200 OK`
```json
{
  "status": "Filled",
  "details": "",
  "order": { ... }
}
```

**Schema:** `OrderUpdate`

**Error responses:**
```json
{
  "status": "notFound",
  "message": "Order with order_id: 123 not found"
}
```

**Order Details Field Values:**

| Details Value | Explanation |
|--------------|-------------|
| `PostOnlyViolation` | Would take liquidity but was marked post-only |
| `IOCViolation` | IOC order could not be fully executed |
| `PositionUpdateViolation` | Violates position update constraints |
| `ReduceOnlyViolation` | Reduce-only order would increase position |
| `ClearinghouseSettleViolation` | Conflicts with clearinghouse settlement |
| `MaxFillLimitViolation` | Exceeds maximum fill limit |
| `DuplicateClientOrderIdViolation` | Client order ID already exists |
| `OrderPreCancelled` | Cancelled before execution |
| `PlaceMakerOrderViolation` | Maker order placement rules violated |
| `DeadMansSwitchExpired` | Dead man's switch timeout |
| `DisallowedSelfTrading` | Self-trading not permitted |
| `OrderCancelledByUser` | User cancelled |
| `OrderCancelledBySystem` | System auto-cancelled |
| `OrderCancelledBySystemDueToError` | System cancelled due to error |

---

### 4.2 Get Delegations

```
GET /api/v1/delegations
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `subaccount` | string | Yes | Subaccount address |

**Response:** `200 OK`
```json
[
  {
    "delegated_account": "0x...",
    "permission_type": "TradePerpsAllMarkets",
    "expiration_time_s": 1736326800000
  }
]
```

**Schema:** Array of `DelegationDto`

---

### 4.3 Get User Fund History

```
GET /api/v1/account_fund_history
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | Subaccount address |
| `limit` | int32 | Yes | Max results |
| `offset` | int32 | Yes | Pagination offset |
| `from` | int64 | Yes | Start timestamp |
| `to` | int64 | Yes | End timestamp |
| `sort_key` | string | Yes | Sort field |
| `sort_dir` | string | No | Direction |

**Response:** `200 OK` — `UserFundHistoryResponse`

Fund movement types: `"deposit"`, `"withdrawal"`

---

## 5. TWAP Endpoints

### 5.1 Get Active TWAP Orders

```
GET /api/v1/active_twaps
```

**Query Parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `account` | string | Yes | — | Subaccount address |
| `limit` | int32 | No | `10` | Max results |

**Response:** `200 OK`
```json
[
  {
    "market": "0x...",
    "is_buy": true,
    "order_id": "78901",
    "is_reduce_only": false,
    "start_unix_ms": 1699564800000,
    "frequency_s": 300,
    "duration_s": 3600,
    "orig_size": 100.0,
    "remaining_size": 75.0,
    "status": "Open",
    "client_order_id": "twap_123",
    "transaction_unix_ms": 1699564800000,
    "transaction_version": 12345679
  }
]
```

**Schema:** Array of `TwapDto`

---

### 5.2 Get TWAP Order History

```
GET /api/v1/twap_history
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | Subaccount address |
| `limit` | int32 | Yes | Max results |
| `offset` | int32 | Yes | Pagination offset |
| `from` | int64 | Yes | Start timestamp |
| `to` | int64 | Yes | End timestamp |
| `sort_key` | string | Yes | Sort field |
| `sort_dir` | string | No | Direction |

**Response:** `200 OK` — `PaginatedResponse<TwapDto>`

---

## 6. Bulk Order Endpoints

### 6.1 Get Bulk Orders

```
GET /api/v1/bulk_orders
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | Subaccount address |
| `market` | string | No | Filter by market |

**Response:** `200 OK`
```json
[
  {
    "market": "0x...",
    "user": "0x...",
    "sequence_number": 12345,
    "previous_seq_num": 12344,
    "bid_prices": [50000, 49900],
    "bid_sizes": [1.0, 2.0],
    "ask_prices": [50100, 50200],
    "ask_sizes": [1.5, 2.5],
    "cancelled_bid_prices": [],
    "cancelled_bid_sizes": [],
    "cancelled_ask_prices": [],
    "cancelled_ask_sizes": [],
    "cancellation_reason": "",
    "transaction_version": 12345678,
    "transaction_unix_ms": 1699564800000,
    "event_uid": "123456789012345678901234567890123456"
  }
]
```

**Schema:** Array of `BulkOrderDto`

**Notes:**
- Returns one bulk order per market (latest)
- `event_uid` is a u128 represented as a string

---

### 6.2 Get Bulk Order Status

```
GET /api/v1/bulk_order_status
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | Subaccount address |
| `market` | string | Yes | Market address |
| `sequence_number` | int64 | Yes | Bulk order sequence number |

**Response:** `200 OK` — `BulkOrderStatusResponse`

Status values: `"Placed"`, `"Rejected"`, `"notFound"`

---

### 6.3 Get Bulk Order Fills

```
GET /api/v1/bulk_order_fills
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | Subaccount address |
| `market` | string | No | Filter by market |
| `sequence_number` | int64 | No | Single sequence number |
| `start_sequence_number` | int64 | No | Range start |
| `end_sequence_number` | int64 | No | Range end (requires `start_sequence_number`) |
| `limit` | int32 | No | Max results |
| `offset` | int32 | No | Pagination offset |

**Response:** `200 OK`
```json
[
  {
    "market": "0x...",
    "sequence_number": 12345,
    "user": "0x...",
    "filled_size": 1.5,
    "price": 50000.0,
    "is_bid": true,
    "trade_id": "3647276",
    "transaction_unix_ms": 1699564800000,
    "transaction_version": 12345682,
    "event_uid": "123456789012345678901234567890123456"
  }
]
```

**Schema:** Array of `BulkOrderFillDto`

---

## 7. Vault Endpoints

### 7.1 Get Public Vaults

```
GET /api/v1/vaults
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `limit` | int32 | Yes | Max results |
| `offset` | int32 | Yes | Pagination offset |
| `sort_key` | string | Yes | One of: `tvl`, `age`, `pnl`, `sharpe_ratio`, `weekly_win_rate`, `max_drawdown` |
| `sort_dir` | string | No | `"ASC"` or `"DESC"` |
| `status` | string | No | `"created"`, `"active"`, `"inactive"` |
| `vault_type` | string | No | `"user"` or `"protocol"` |
| `vault_address` | string | No | Exact vault address |
| `search` | string | No | Case-insensitive search on address/name/manager |

**Response:** `200 OK` — `PublicVaultsResponse`

---

### 7.2 Get Account-Owned Vaults

```
GET /api/v1/account_owned_vaults
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | Owner address |
| `limit` | int32 | Yes | Max results |
| `offset` | int32 | Yes | Pagination offset |

**Response:** `200 OK` — `PaginatedResponse<VaultDto>`

---

### 7.3 Get Account Vault Performance

```
GET /api/v1/account_vault_performance
```

**Query Parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `account` | string | Yes | — | Account address |
| `limit` | int64 | No | `20` | Max results (0–1000) |
| `offset` | int64 | No | `0` | Pagination offset (0–10000) |

**Response:** `200 OK`
```json
[
  {
    "vault": { ... },
    "account_address": "0x...",
    "total_deposited": 10000.0,
    "total_withdrawn": 2000.0,
    "current_value_of_shares": 9500.0,
    "current_num_shares": 9500000000,
    "share_price": 1.05,
    "locked_amount": 1000.0,
    "all_time_earned": 1500.0,
    "all_time_return": 15.0,
    "unrealized_pnl": 500.0,
    "volume": 50000.0,
    "weekly_win_rate_12w": 0.65,
    "deposits": [ ... ],
    "withdrawals": [ ... ]
  }
]
```

**Schema:** Array of `AccountVaultPerformanceDto`

---

## 8. Analytics Endpoints

### 8.1 Get Leaderboard

```
GET /api/v1/leaderboard
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `limit` | int32 | Yes | Max results (default 100) |
| `offset` | int32 | Yes | Pagination offset |
| `sort_key` | string | Yes | `"account_value"`, `"realized_pnl"`, `"volume"`, `"roi"` |
| `sort_dir` | string | No | `"ASC"` or `"DESC"` |
| `search_term` | string | No | Filter by account address prefix |

**Response:** `200 OK` — `PaginatedResponse<LeaderboardEntryDto>`

```json
{
  "items": [
    {
      "rank": 1,
      "account": "0x...",
      "account_value": 1000000.0,
      "realized_pnl": 50000.0,
      "roi": 25.5,
      "volume": 5000000.0
    }
  ],
  "total_count": 100
}
```

---

### 8.2 Get Points Leaderboard

```
GET /api/v1/points_leaderboard
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `limit` | int32 | Yes | Max results |
| `offset` | int32 | Yes | Pagination offset |
| `sort_key` | string | Yes | `"total_amps"` or `"realized_pnl"` |
| `sort_dir` | string | No | Direction |
| `search_term` | string | No | Filter by owner address prefix |
| `tier` | string | No | `"top20"`, `"diamond"`, `"doublePlatinum"`, `"gold"` |

**Response:** `200 OK` — `PaginatedResponse<PointsLeaderboardEntryDto>`

---

### 8.3 Get Portfolio Chart Data

```
GET /api/v1/portfolio_chart
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | Subaccount address |
| `range` | string | Yes | Time range enum |
| `data_type` | string | Yes | `"pnl"` or `"account_value"` |

**Response:** `200 OK`
```json
[
  {
    "timestamp": 1699564800000,
    "data_points": 10500.0,
    "vault_equity": 259.73
  }
]
```

**Schema:** Array of `PortfolioPointDto`

**Notes:**
- `vault_equity` is null for users with no vault deposits or when `data_type` is `"pnl"`

---

## 9. Referral Endpoints

### 9.1 Get Referral Info

```
GET /api/v1/referrals/account/{account}
```

**Path Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | Wallet address (not subaccount) |

**Response:** `200 OK` — `AccountReferralInfo`

---

### 9.2 Get Referrer Statistics

```
GET /api/v1/referrals/stats/{account}
```

**Path Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | Referrer wallet address |

**Response:** `200 OK` — `ReferrerStatsDto`

---

### 9.3 Get Users Referred by Referrer

```
GET /api/v1/referrals/users
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `referrer_account` | string | Yes | Referrer wallet address |
| `limit` | int32 | Yes | Max results |
| `offset` | int32 | Yes | Pagination offset |

**Response:** `200 OK` — Array of `UserReferralInfo`

---

## 10. Predeposit Endpoints

### 10.1 Get S0 Predeposit USDC Reward

```
GET /api/v1/predeposits/rewards
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | Account address |

**Response:** `200 OK`
```json
{
  "account": "0x...",
  "usdc_reward": 100.0
}
```

---

## 11. Shared Data Schemas

### 11.1 PriceDto

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `market` | string | Yes | Market address |
| `oracle_px` | float64 | Yes | Oracle price |
| `mark_px` | float64 | Yes | Mark price |
| `mid_px` | float64 | Yes | Mid price |
| `funding_rate_bps` | float64 | Yes | Funding rate in basis points |
| `is_funding_positive` | bool | Yes | Funding direction |
| `transaction_unix_ms` | int64 | Yes | Last update timestamp |
| `open_interest` | float64 | Yes | Open interest |

### 11.2 OrderDto

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `parent` | string | Yes | Parent account address |
| `market` | string | Yes | Market address |
| `client_order_id` | string | Yes | Client-specified ID |
| `order_id` | string | Yes | Server-assigned ID |
| `status` | string | Yes | `"Open"`, `"Filled"`, `"Cancelled"`, `"Expired"`, `"Rejected"` |
| `order_type` | string | Yes | `"Limit"`, `"Market"`, `"Stop Limit"`, `"Stop Market"` |
| `trigger_condition` | string | Yes | `"None"`, `"Above"`, `"Below"` |
| `order_direction` | string | Yes | `"Open Long"`, `"Close Long"`, `"Open Short"`, `"Close Short"` |
| `is_buy` | bool | Yes | Buy side flag |
| `is_reduce_only` | bool | Yes | Reduce-only flag |
| `is_tpsl` | bool | Yes | Is TP/SL order |
| `cancellation_reason` | string | Yes | Reason for cancellation (empty if not cancelled) |
| `details` | string | Yes | Additional details (violation reasons) |
| `transaction_version` | uint64 | Yes | Aptos transaction version |
| `unix_ms` | uint64 | Yes | Timestamp |
| `orig_size` | float64? | No | Original order size |
| `remaining_size` | float64? | No | Remaining unfilled size |
| `size_delta` | float64? | No | Size change |
| `price` | float64? | No | Order price |
| `tp_order_id` | string? | No | Take-profit order ID |
| `tp_trigger_price` | float64? | No | TP trigger price |
| `tp_limit_price` | float64? | No | TP limit price |
| `sl_order_id` | string? | No | Stop-loss order ID |
| `sl_trigger_price` | float64? | No | SL trigger price |
| `sl_limit_price` | float64? | No | SL limit price |

### 11.3 PositionDto

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `market` | string | Yes | Market address |
| `user` | string | Yes | Subaccount address |
| `size` | float64 | Yes | Position size (>0=long, <0=short) |
| `user_leverage` | uint32 | Yes | User-selected leverage |
| `entry_price` | float64 | Yes | Average entry price |
| `is_isolated` | bool | Yes | Isolated margin flag |
| `is_deleted` | bool | Yes | Position closed flag |
| `unrealized_funding` | float64 | Yes | Unrealized funding |
| `estimated_liquidation_price` | float64 | Yes | Estimated liquidation price |
| `transaction_version` | uint64 | Yes | Transaction version |
| `has_fixed_sized_tpsls` | bool | Yes | Has fixed-size TP/SL |
| `tp_order_id` | string? | No | TP order ID |
| `tp_trigger_price` | float64? | No | TP trigger price |
| `tp_limit_price` | float64? | No | TP limit price |
| `sl_order_id` | string? | No | SL order ID |
| `sl_trigger_price` | float64? | No | SL trigger price |
| `sl_limit_price` | float64? | No | SL limit price |

### 11.4 TradeDto

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | User's subaccount address |
| `market` | string | Yes | Market address |
| `action` | string | Yes | Trade action type |
| `source` | string | Yes | Trade source |
| `trade_id` | string | Yes | Trade ID |
| `size` | float64 | Yes | Trade size |
| `price` | float64 | Yes | Trade price |
| `is_profit` | bool | Yes | Profitable trade flag |
| `realized_pnl_amount` | float64 | Yes | Realized PnL |
| `realized_funding_amount` | float64 | Yes | Realized funding |
| `is_rebate` | bool | Yes | Rebate flag |
| `fee_amount` | float64 | Yes | Fee amount |
| `order_id` | string | Yes | Associated order ID |
| `client_order_id` | string | Yes | Client order ID |
| `transaction_unix_ms` | int64 | Yes | Timestamp |
| `transaction_version` | uint64 | Yes | Transaction version |

### 11.5 TwapDto

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `market` | string | Yes | Market address |
| `is_buy` | bool | Yes | Buy direction |
| `order_id` | string | Yes | TWAP order ID |
| `is_reduce_only` | bool | Yes | Reduce-only flag |
| `start_unix_ms` | int64 | Yes | TWAP start time |
| `frequency_s` | uint64 | Yes | Order frequency in seconds |
| `duration_s` | uint64 | Yes | Total duration in seconds |
| `orig_size` | float64 | Yes | Original total size |
| `remaining_size` | float64 | Yes | Remaining size |
| `status` | string | Yes | Order status |
| `client_order_id` | string | Yes | Client order ID |
| `transaction_unix_ms` | int64 | Yes | Timestamp |
| `transaction_version` | uint64 | Yes | Transaction version |

### 11.6 MarketDto

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `market_addr` | string | Yes | Market address |
| `market_name` | string | Yes | Human-readable name (e.g., `"BTC-PERP"`) |
| `sz_decimals` | uint32 | Yes | Size decimal precision |
| `max_leverage` | uint32 | Yes | Maximum allowed leverage |
| `tick_size` | uint64 | Yes | Minimum price increment (chain units) |
| `min_size` | uint64 | Yes | Minimum order size (chain units) |
| `lot_size` | uint64 | Yes | Size increment (chain units) |
| `max_open_interest` | float64 | Yes | Maximum open interest |
| `px_decimals` | uint32 | Yes | Price decimal precision |
| `mode` | string | Yes | Market mode: `"Open"`, `"ReduceOnly"`, `"CloseOnly"` |
| `unrealized_pnl_haircut_bps` | uint32 | Yes | PnL haircut in basis points |

### 11.7 BulkOrderDto

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `market` | string | Yes | Market address |
| `user` | string | Yes | User address |
| `sequence_number` | uint64 | Yes | Sequence number |
| `previous_seq_num` | uint64? | No | Previous sequence number |
| `bid_prices` | float64[] | Yes | Bid price levels |
| `bid_sizes` | float64[] | Yes | Bid sizes per level |
| `ask_prices` | float64[] | Yes | Ask price levels |
| `ask_sizes` | float64[] | Yes | Ask sizes per level |
| `cancelled_bid_prices` | float64[] | Yes | Cancelled bid prices |
| `cancelled_bid_sizes` | float64[] | Yes | Cancelled bid sizes |
| `cancelled_ask_prices` | float64[] | Yes | Cancelled ask prices |
| `cancelled_ask_sizes` | float64[] | Yes | Cancelled ask sizes |
| `cancellation_reason` | string | Yes | Reason for cancellation |
| `transaction_version` | uint64 | Yes | Transaction version |
| `transaction_unix_ms` | int64 | Yes | Timestamp |
| `event_uid` | string (u128) | Yes | Event unique identifier |

### 11.8 PaginatedResponse\<T\>

```json
{
  "items": [ T, ... ],
  "total_count": 42
}
```

All paginated responses SHALL include `items` (array) and `total_count` (int32).

### 11.9 Enum Types

**Interval:** `"1m"`, `"5m"`, `"15m"`, `"30m"`, `"1h"`, `"2h"`, `"4h"`, `"1d"`, `"1w"`, `"1mo"`

**SortDir:** `"ASC"`, `"DESC"`

**SideFilter:** `"buy"`, `"sell"`

**VaultStatus:** `"created"`, `"active"`, `"inactive"`

**VaultSortKey:** `"tvl"`, `"age"`, `"pnl"`, `"sharpe_ratio"`, `"weekly_win_rate"`, `"max_drawdown"`

**LeaderboardSortKey:** `"account_value"`, `"realized_pnl"`, `"volume"`, `"roi"`

**PointsLeaderboardSortKey:** `"total_amps"`, `"realized_pnl"`

**PointsLeaderboardTier:** `"top20"`, `"diamond"`, `"doublePlatinum"`, `"gold"`

**FundMovementType:** `"deposit"`, `"withdrawal"`

**NotificationType:** `"MarketOrderPlaced"`, `"LimitOrderPlaced"`, `"StopMarketOrderPlaced"`, `"StopMarketOrderTriggered"`, `"StopLimitOrderPlaced"`, `"StopLimitOrderTriggered"`, `"OrderPartiallyFilled"`, `"OrderFilled"`, `"OrderSizeReduced"`, `"OrderCancelled"`, `"OrderRejected"`, `"OrderErrored"`, `"TwapOrderPlaced"`, `"TwapOrderTriggered"`, `"TwapOrderCompleted"`, `"TwapOrderCancelled"`, `"TwapOrderErrored"`, `"AccountDeposit"`, `"AccountWithdrawal"`, `"TpSlSet"`, `"TpHit"`, `"SlHit"`, `"TpCancelled"`, `"SlCancelled"`
