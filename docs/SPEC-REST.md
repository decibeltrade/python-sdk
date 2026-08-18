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
8. [Analytics, Points & Streaks Endpoints](#8-analytics-points--streaks-endpoints)
9. [Referral & Affiliate Endpoints](#9-referral--affiliate-endpoints)
10. [Rewards, Campaign & Predeposit Endpoints](#10-rewards-campaign--predeposit-endpoints)
11. [Shared Data Schemas](#11-shared-data-schemas)

---

## 1. Transport & Headers

### 1.1 Protocol

All REST endpoints SHALL use HTTPS. Reads are GET; trading writes go on-chain rather than through
this API.

**Exceptions:** subaccount rename uses PATCH (see Section 4), and referral-code redemption uses POST
(see Section 9.5).

### 1.2 Required Headers

| Header | Value | Required |
|--------|-------|----------|
| `Authorization` | `Bearer <API_KEY>` | YES |
| `Content-Type` | `application/json` | For PATCH and POST only |

> **Note:** The `Origin` header is required by the server for browser-based requests but the SDK does NOT send it. Server-side enforcement may vary by deployment.

### 1.3 Response Format

All successful responses SHALL return JSON with `Content-Type: application/json`.

### 1.4 Query Parameter Encoding

- Pagination parameters SHALL be sent as flat query params: `?limit=10&offset=0`
- Sorting parameters SHALL be sent as: `?sort_key=volume&sort_dir=DESC`
- Filter parameters SHALL be sent as: `?from=1634567890000&to=1634654290000`

### 1.5 Product Selection (`asset_type`)

Decibel serves two products from one API: **perp** and **spot**. Endpoints that can return rows for
either accept an `asset_type` query parameter:

| Value | Meaning |
|-------|---------|
| `perp` | Perp rows only |
| `spot` | Spot rows only |
| *(omitted)* | Both products, merged into one response |

The SDK models this as an `AssetTypeFilter` of `"perp" | "spot" | "all"`, where `"all"` means
**omit the parameter**. List readers default to `"perp"` so pre-spot consumers are unaffected.

Rows returned by dual-product endpoints carry an `asset_type` field for client-side demux. That
field is **absent** on API versions predating spot; a row with no `asset_type` SHALL be treated as
perp.

Market addresses already encode the product — a spot market address is derived from the spot engine,
a perp market address from the perp engine — so endpoints keyed by market address (depth, trades,
candlesticks) need no `asset_type` parameter.

**Endpoints accepting `asset_type`:** `/api/v1/open_orders`, `/api/v1/order_history`,
`/api/v1/trade_history`, `/api/v1/orders`, `/api/v1/bulk_orders`, `/api/v1/bulk_order_status`,
`/api/v1/bulk_order_fills`.

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

**Notes:**
- Perp markets only. Spot markets are served by Section 2.6.

---

### 2.6 Get Spot Asset Contexts

24h stats and a current price snapshot for every registered spot market. The spot counterpart of
Section 2.5; perp-only concepts (funding, open interest, mark/oracle prices) are absent.

```
GET /api/v1/spot/asset_contexts
```

**Query Parameters:** None

**Response:** `200 OK`
```json
[
  {
    "market_addr": "0x...",
    "name": "APT/USDC",
    "ticker_id": "APT_USDC",
    "base_asset_addr": "0xa",
    "quote_asset_addr": "0x...",
    "base_decimals": 8,
    "quote_decimals": 6,
    "last_price": 12.5,
    "mid": 12.51,
    "prev_day_price": 12.0,
    "volume_24h_base": 1000.0,
    "volume_24h_quote": 12500.0,
    "high_24h": 13.0,
    "low_24h": 11.5,
    "timestamp_unix_ms": 1699564800000
  }
]
```

**Schema:** Array of `SpotAssetContextDto` (Section 11.9)

**Null semantics:**
- `last_price`, `high_24h`, `low_24h` are null when the market had no trades in the last 24h
- `mid` is null unless both book sides have resting liquidity
- `prev_day_price` is null for markets that never traded before the 24h boundary — render 24h change
  as n/a rather than 0
- 24h change is derived client-side: `(last_price - prev_day_price) / prev_day_price`

**Notes:**
- `market_addr` matches the address derived from the market name and the spot engine; a client that
  derives addresses locally SHALL get the same value.

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
  "free_vault_equity": 120.0,
  "net_deposits": 30277044.96,
  "liquidation_fees_paid": 45.5,
  "liquidation_losses": null,
  "perp_equity_haircutted": 9950.0,
  "fee_income": null,
  "cross_available_to_trade": 9843.79,
  "secondary_collateral": [
    {
      "asset_type": "0x...",
      "amount": 3.0,
      "value_in_usdc": 30.0,
      "nav_per_unit": 11.0,
      "haircut_bps": 900.0,
      "withdrawable_amount": 1.0
    }
  ],
  "spot": {
    "positions": [
      {
        "asset_addr": "0xa",
        "asset_symbol": "APT",
        "amount": 10.0,
        "usd_value": 125.0,
        "entry_notional_usd": 120.0,
        "unrealized_pnl_usd": 5.0
      }
    ],
    "total_usd": 125.0,
    "in_flight_orders": [
      {
        "market_addr": "0x...",
        "order_id": "1",
        "is_bid": true,
        "reserved_asset": "0x...",
        "reserved_amount": 50.0,
        "reserved_usd_value": 50.0
      }
    ],
    "metrics": {
      "cumulative_volume_usd": 5000.0,
      "cumulative_taker_fees_usd": 1.7,
      "cumulative_maker_fees_usd": 0.55,
      "cumulative_realized_pnl_usd": 12.0
    }
  }
}
```

**Schema:** `AccountOverviewDto`

**Required fields:** `perp_equity_balance`, `unrealized_pnl`, `unrealized_funding_cost`, `cross_margin_ratio`, `maintenance_margin`, `cross_account_leverage_ratio`, `total_margin`, `usdc_cross_withdrawable_balance`, `usdc_isolated_withdrawable_balance`, `margin_deficit`

**Nullable fields:** `all_time_return`, `average_cash_position`, `average_leverage`, `cross_account_position`, `liquidation_fees_paid`, `liquidation_losses`, `max_drawdown`, `net_deposits`, `pnl_90d`, `realized_pnl`, `sharpe_ratio`, `vault_equity`, `volume`, `weekly_win_rate_12w`

**Optional fields (may be absent entirely):** `cross_available_to_trade`, `fee_income`, `free_vault_equity`, `margin_deficit`, `net_deposits`, `perp_equity_haircutted`, `secondary_collateral`, `spot`, `vault_equity`

**Edge behaviors:**
- `margin_deficit`: 0 when healthy, negative when account has margin hole
- `liquidation_losses`: null for regular users (only vault/BLP accounts)
- Performance fields are null unless `include_performance=true`
- `volume` is null unless `volume_window` is provided
- `fee_income`: non-trade protocol fee distributions (vault/BLP accounts only); not included in
  `realized_pnl`

**Spot & collateral blocks:**
- `spot` is null for wallet-only owners and when spot enrichment fails. `spot.metrics` is absent
  until the subaccount has traded spot.
- `spot.positions` covers assets held in the per-user fungible store, including USDC as a PnL-less
  position; `spot.in_flight_orders` covers amounts locked in open spot orders (quote for bids, base
  for asks). `spot.total_usd` counts both.
- `entry_notional_usd` is 0 when the asset was acquired without an on-book spot trade (e.g. an FA
  transfer in), so `unrealized_pnl_usd` then equals `usd_value`.
- `secondary_collateral` is null when no non-USDC collateral exists or oracle data is unavailable.
- `vault_equity` is display-only: do NOT sum it with `perp_equity_balance`, since the pledged portion
  is already counted there via `secondary_collateral`. Use `free_vault_equity` for total-wealth math.
- `cross_available_to_trade` is buying power across all collateral assets:
  `max(0, raw_free_collateral - order_margin)`.

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
| `asset_type` | string | No | `"perp"` or `"spot"`; omit for both (Section 1.5) |

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
| `asset_type` | string | No | `"perp"` or `"spot"`; omit for both (Section 1.5) |

**Response:** `200 OK` — `PaginatedResponse<OrderDto>`

**Note:** Page size capped at 200. `asset_type` scopes pagination as well as the rows, so paging
through `"all"` interleaves both products.

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
| `asset_type` | string | No | `"perp"` or `"spot"`; omit for both (Section 1.5) |

**Response:** `200 OK` — `PaginatedResponse<TradeDto>`

**Edge behaviors:**
- Returns `400` if `order_id` provided without `market`.
- Page size capped at 200.
- Spot rows report `action` as the side (`"Buy"` / `"Sell"`) rather than the perp position-centric
  values, carry `fee_asset`, and leave the perp-only PnL/funding fields at 0.

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

### 3.8 Get Withdrawal Queue

Withdrawals are queued on-chain and settled asynchronously. This endpoint serves the indexed
history of every queue event for an account.

```
GET /api/v1/withdraw_queue
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | Subaccount address |
| `status` | string | No | `"Queued"`, `"Processed"`, or `"Cancelled"` |
| `limit` | int32 | No | Max results |
| `offset` | int32 | No | Pagination offset |

**Response:** `200 OK`
```json
{
  "items": [
    {
      "user": "0x...",
      "recipient": "0x...",
      "market": null,
      "fungible_amount": 100.0,
      "processed_amount": 0.0,
      "request_id": "42",
      "status": "Queued",
      "cancel_reason": null,
      "timestamp_ms": 1699564800000,
      "queued_at_ms": 1699564800000,
      "transaction_version": 12345678
    }
  ],
  "total_count": 1
}
```

**Cancel reasons:** `"CancelledByUser"`, `"InsufficientWithdrawableBalance"`,
`"DepositCheckFailed"`. New reasons SHALL pass through unrecognized rather than fail validation.

**Edge behaviors:**
- `total_count` counts **event rows, not unique withdrawals**: with no `status` filter, a
  Queued-then-Processed withdrawal contributes two rows. Pass a `status` filter when using
  `total_count` for pagination.
- `request_id` is a u64 serialized as a decimal string.
- `processed_amount` is 0 on Queued and Cancelled rows. Partial fills each emit their own row under
  the same `request_id`.
- `queued_at_ms` may be null on replay-reordered rows and backfill timeouts. Do not fall back to
  `timestamp_ms` for display — that is the latest event's time, not the queue time.
- `cancel_reason` is only meaningful when `status == "Cancelled"`.
- Rows are merged client-side by `request_id`, applying an update only when its
  `transaction_version` is **strictly greater**: delivery is at-least-once, so `>=` would let a
  duplicate overwrite merged fields with nulls.

The on-chain view `{package}::async_withdraw_queue::get_pending_withdrawals` is available as a liveness-check
fallback. It returns only currently-Queued items in **raw chain units**, which are not comparable to
the normalized `fungible_amount` above; correlate the two by `request_id`.

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
| `client_order_id` | string | No* | Client order ID (perp only — spot orders carry none) |
| `asset_type` | string | No | `"perp"` or `"spot"`; omit to check perp then fall through to spot |

\* Exactly one of `order_id` / `client_order_id` SHALL be provided.

Unlike the list endpoints, the SDK leaves `asset_type` **unset** by default here: a point lookup by
id wants the server's perp-then-spot fallthrough rather than a product filter.

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

### 4.4 Get User Fee Rates

```
GET /api/v1/user_fee_rates
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | Subaccount address |

**Response:** `200 OK`
```json
{
  "account": "0x...",
  "fee_tier": 2,
  "user_taker_rate": 0.00034,
  "user_maker_rate": 0.00011,
  "active_referral_discount": 0.05,
  "daily_user_volume": [
    { "date": "2026-08-16", "volume": "125000", "maker_volume": "50000", "taker_volume": "75000" }
  ],
  "fee_schedule": {
    "taker": 0.00034,
    "maker": 0.00011,
    "referral_discount": 0.05,
    "tiers": {
      "vip": [{ "volume_threshold": "5000000", "taker": 0.0003, "maker": 0.00009 }],
      "market_maker": [{ "maker_fraction_threshold": "0.005", "maker": -0.00001 }]
    }
  },
  "perp": { "fee_tier": 2, "fee_schedule": { }, "user_taker_rate": 0.0003, "user_maker_rate": 0.00009, "daily_user_volume": [], "total_window_volume_usd": "5200000", "active_referral_discount": 0.05 },
  "spot": { "fee_tier": 1, "fee_schedule": { }, "user_taker_rate": 0.0004, "user_maker_rate": 0.0001, "daily_user_volume": [], "total_window_volume_usd": "300000", "active_referral_discount": 0.0 },
  "weighted_volume_usd": "5350000",
  "volume_weights": { "perp": 100.0, "spot": 50.0 }
}
```

**Notes:**
- Rates are decimals, not basis points: `0.000340` = 0.034%.
- Volumes are whole-dollar USD integers serialized as strings.
- Tier qualification is inclusive (`volume >= volume_threshold`), matching the on-chain `>=`.
- `tiers.market_maker` is empty when maker rebates are disabled. Rebate rates are negative.
- The fee tier is **cross-product**: computed from
  `perp_volume * volume_weights.perp + spot_volume * volume_weights.spot` (mirroring the on-chain
  `CrossProductVolumeWeights`, where 100 == 1.0x) and then indexed into each product's own ladder.
  Perp and spot can therefore sit at different tiers for the same user.
- `perp`, `spot`, `weighted_volume_usd` and `volume_weights` are optional — the per-product split is
  still rolling out server-side. The top-level rate fields remain perp-only aliases of `perp.*` for
  backward compatibility; new consumers SHALL read `perp` / `spot` explicitly.
- Spot has no referral program, so `spot.active_referral_discount` is always 0.

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
| `asset_type` | string | No | `"perp"` or `"spot"`; omit for both (Section 1.5) |

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
| `asset_type` | string | No | `"perp"` or `"spot"` |

**Response:** `200 OK` — `BulkOrderStatusResponse`

Status values: `"Placed"`, `"Rejected"`, `"notFound"`

**Note:** Bulk-order status is keyed per product — sequence numbers are per (account, market,
product) — so there is no merged view here. The SDK always sends `asset_type`, defaulting to
`"perp"`.

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
| `asset_type` | string | No | `"perp"` or `"spot"`; omit for both (Section 1.5) |

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

## 8. Analytics, Points & Streaks Endpoints

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

### 8.4 Get Points Tier

```
GET /api/v1/points/tier
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `owner` | string | Yes | Owner wallet address (not a subaccount) |

**Response:** `200 OK`
```json
{
  "owner": "0x...",
  "total_amps": 12500.0,
  "rank": 42,
  "current_tier": "gold",
  "tiers": [
    { "name": "gold", "hz_threshold": 10000.0, "progress": 1.0 },
    { "name": "doublePlatinum", "hz_threshold": 50000.0, "progress": 0.25 }
  ]
}
```

**Notes:**
- Thresholds are percentile-based, so they move as the population changes.
- `rank` and `current_tier` are null for owners with no Amps.
- `progress` is a 0–1 fraction toward that threshold.

---

### 8.5 Get Global Points Stats

```
GET /api/v1/points/global
```

**Query Parameters:** None

**Response:** `200 OK`
```json
{ "total_users": 125000, "total_amps_distributed": 987654321.0 }
```

---

### 8.6 Get Trading Amps

Aggregated trading Hz (Amps) for an owner across all their active subaccounts.

```
GET /api/v1/points/trading/amps
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `owner` | string | Yes | Owner wallet address |
| `season` | string | No | Restrict to one season (e.g. `"season1"`); omit to aggregate all |
| `days` | int32 | No | Lookback window in days (1 = today only); omit for lifetime |

**Response:** `200 OK`
```json
{
  "owner": "0x...",
  "total_amps": 12500.0,
  "breakdown": [{ "account": "0x...", "total_amps": 9000.0 }]
}
```

**Notes:**
- `breakdown` may be absent; `total_amps` is authoritative either way.

---

### 8.7 Get Account Streaks

```
GET /api/v1/streaks/account
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `owner` | string | Yes | Owner wallet address |

**Response:** `200 OK`
```json
{
  "owner": "0x...",
  "currentStreak": 5,
  "streakIpoints": 12.5,
  "streakAmpsEstimate": 3.0,
  "graceDaysAvailable": 2,
  "graceDaysUsed": 1,
  "qualifyingDates": ["2026-08-16", "2026-08-15"]
}
```

**Notes:**
- This is the **only** endpoint in the API that serves camelCase keys. The SDK aliases them to
  snake_case so its surface stays uniform.
- `qualifyingDates` are UTC `YYYY-MM-DD` strings.
- Grace days let a streak survive a missed day; `graceDaysAvailable` is what remains.

---

## 9. Referral & Affiliate Endpoints

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

### 9.4 Validate a Referral Code

```
GET /api/v1/referrals/code/{code}
```

**Path Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | string | Yes | Referral code, URL-encoded |

**Response:** `200 OK`
```json
{ "referral_code": "ABC123", "is_valid": true, "is_active": true }
```

**Notes:**
- Codes are user-supplied, so the path segment SHALL be percent-encoded (`/` → `%2F`).
- `is_valid` means the code exists; `is_active` means it can still be redeemed.

---

### 9.5 Redeem a Referral Code

```
POST /api/v1/referrals/redeem
```

**Request Body:**
```json
{ "referral_code": "ABC123", "account": "0x..." }
```

**Response:** `200 OK`
```json
{ "referral_code": "ABC123", "account": "0x..." }
```

---

### 9.6 Get Affiliate Codes

```
GET /api/v1/affiliates/codes/{account}
GET /api/v1/affiliates/codes/{account}/analytics
```

**Response (`/codes`):** `200 OK`
```json
{
  "owner_account": "0x...",
  "volume_threshold_met": true,
  "codes": [
    {
      "referral_code": "ABC123",
      "owner_account": "0x...",
      "max_usage": 100,
      "usage_count": 12,
      "is_active": true,
      "is_affiliate": true,
      "source": "admin",
      "created_at_ms": 1699564800000
    }
  ]
}
```

**Response (`/analytics`):** `200 OK`
```json
{
  "owner_account": "0x...",
  "codes": [{ "referral_code": "ABC123", "l1_volume_usd": 500000.0, "l1_amps_earned": 1250.0 }]
}
```

**`source` values:** `"admin"`, `"auto"`, `"reusable"`, `"predeposit"`, `"unknown"`

**Notes:**
- Analytics live behind a separate route deliberately: the metadata route is hit on every page load
  via the global nav and SHALL NOT pay the analytics JOIN cost.

---

### 9.7 Get Affiliate Earnings

```
GET /api/v1/affiliates/earnings/{account}
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `limit` | int32 | No | Max referred users returned in `users.items` |

**Response:** `200 OK`
```json
{
  "affiliate_account": "0x...",
  "is_affiliate": true,
  "earnings": { "l1_amps": 1250.0, "l2_amps": 300.0, "total_amps": 1550.0, "l1_count": 12, "l2_count": 40 },
  "users": {
    "items": [
      {
        "account": "0x...",
        "level": "L1",
        "referred_by": null,
        "total_amps": 900.0,
        "affiliate_amps_earned": 90.0,
        "total_volume": 250000.0,
        "active": true
      }
    ],
    "total_count": 52
  }
}
```

**Notes:**
- `level` is `"L1"` (directly referred) or `"L2"` (referred by an L1). `referred_by` is null for L1.
- The SDK requests `limit=1000` so the earnings breakdown and the user list stay consistent in one
  round trip.

---

## 10. Rewards, Campaign & Predeposit Endpoints

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

### 10.2 Get Active Campaigns

```
GET /api/v1/campaigns/active
```

**Query Parameters:** None

**Response:** `200 OK`
```json
[
  {
    "campaign_id": 7,
    "campaign_type": "fee_rebate",
    "status": "active",
    "title": "August Fee Rebate",
    "description": "Rebates on taker fees",
    "reward_asset": "0x...",
    "start_ts_sec": 1754006400,
    "end_ts_sec": 1756684800,
    "claim_start_ts_sec": 1756684800,
    "claim_end_ts_sec": 1759276800,
    "total_funded": 50000.0
  }
]
```

**`campaign_type` values:** `"fee_rebate"`, `"maker_incentive"`, `"liquidation_rebate"`,
`"volume_milestone"`, `"first_funded_trial"`

**`status` values:** `"draft"`, `"funded"`, `"active"`, `"expired"`, `"reclaimed"`, `"cancelled"`

**Notes:**
- Returns every campaign currently visible to users, regardless of the caller's allocation.

---

### 10.3 Get Account Campaign Summary

```
GET /api/v1/campaigns/account
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | Account address |
| `limit` | int32 | No | Paginate the `claims` list |
| `offset` | int32 | No | Pagination offset |

**Response:** `200 OK`
```json
{
  "lifetime_earned": 1250.0,
  "ready_to_claim": 300.0,
  "total_claimed": 950.0,
  "year_to_date": 1250.0,
  "weekly_wow_bps": 1500.0,
  "total_claims": 3,
  "breakdown_by_type": [
    { "campaign_type": "fee_rebate", "lifetime_earned": 1000.0, "ready_to_claim": 300.0, "total_claimed": 700.0 }
  ],
  "weekly_breakdown": [{ "week_start_ts_sec": 1754006400, "reward_amount": 120.0 }],
  "claims": [
    {
      "campaign_id": 7,
      "campaign_type": "fee_rebate",
      "status": "active",
      "title": "August Fee Rebate",
      "reward_asset": "0x...",
      "start_ts_sec": 1754006400,
      "end_ts_sec": 1756684800,
      "claim_start_ts_sec": 1756684800,
      "claim_end_ts_sec": 1759276800,
      "total_funded": 50000.0,
      "has_allocation": true,
      "claimable_amount": 300.0,
      "claimed_amount": 0.0,
      "ready_to_claim": 300.0,
      "claimed_at_ts_sec": null,
      "claim_tx_hash": null
    }
  ]
}
```

**Notes:**
- `limit` / `offset` paginate `claims` only; the aggregate totals always cover every campaign.
- Claim amounts are raw u64 chain units — divide by `10^6` for USDC.
- `lifetime_earned == ready_to_claim + total_claimed`.
- `ready_to_claim` already subtracts claimed and in-flight amounts, so it is the number to put
  behind a "Claim $X" button.
- `weekly_wow_bps` is cumulative week-over-week growth in basis points, and is 0 when the prior
  cumulative was 0 or growth was non-positive.

---

### 10.4 Get Protected Trials (Funded First Trade)

```
GET /api/v1/protected_trials
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | Yes | Account address |
| `campaign_addr` | string | No | Restrict to one campaign |
| `limit` | int32 | No | Max history rows |
| `offset` | int32 | No | Pagination offset |

**Response:** `200 OK`
```json
{
  "account": "0x...",
  "active_trial": { "trial_id": 1, "user": "0x...", "campaign_addr": "0x...", "status": "Active", "size": 1.5 },
  "active_trials": [],
  "history": [],
  "history_total_count": 12
}
```

**Notes:**
- The open-sourced fields (`market`, `mark_at_open`, `side`, …) are absent only on degraded reset
  rows; the terminal fields (`closed_at_ms`, `user_payout`, `settle_reason`, …) appear on
  closed/reset rows only.
- `size` is always serialized and is null when the market is unknown.
- `history_total_count` is a SQL-level count: server-skipped rows still count, so clients SHALL NOT
  assert `len(history) == history_total_count` on the last page.
- The SDK treats a trial that settled within the last 5 minutes as still worth showing, so
  `get_active_trial` may return a non-Active row from `history`.
- This endpoint may be absent on deployments predating the campaign; the SDK falls back to on-chain
  views rather than failing.

---

### 10.5 Get Campaign Locks

```
GET /api/v1/campaign_locks
```

**Query Parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `account` | string | Yes | — | Account address |
| `campaign_addr` | string | No | — | Restrict to one campaign |
| `status` | string | No | — | `"Active"` or `"Claimed"` |
| `limit` | int32 | No | `10` | Max results |
| `offset` | int32 | No | — | Pagination offset |

**Response:** `200 OK`
```json
{
  "account": "0x...",
  "locks": [
    {
      "lock_id": 1,
      "campaign_addr": "0x...",
      "trial_id": 1,
      "amount": 250000000,
      "amount_usd": 250.0,
      "duration_days": 7,
      "lock_subaccount": "0x...",
      "locked_at_ms": 1699564800000,
      "unlocks_at_ms": 1700169600000,
      "status": "Active",
      "was_extended": false
    }
  ],
  "total_count": 1
}
```

**Notes:**
- Extension fields (`previous_unlocks_at_ms`, `extended_at_ms`) appear on extended locks only; the
  returned/claimed fields (`returned_amount`, `claimed_at_ms`) on claimed locks only.
- `returned_amount` is trading-PnL-adjusted, so it may differ from `amount`.
- Skipped orphan rows still count and consume page slots:
  `has_next_page = offset + limit < total_count`.

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
| `asset_type` | string? | No | `"perp"` or `"spot"`; absent on pre-spot API versions (treat as perp) |
| `time_in_force` | string? | No | `"GTC"`, `"IOC"`, `"POST_ONLY"`. Spot orders carry it explicitly |
| `parent` | string | Yes | Parent account address |
| `market` | string | Yes | Market address |
| `client_order_id` | string | Yes | Client-specified ID (perp only; empty for spot) |
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
| `asset_type` | string? | No | `"perp"` or `"spot"`; absent on pre-spot API versions (treat as perp) |
| `account` | string | Yes | User's subaccount address |
| `market` | string | Yes | Market address |
| `action` | string | Yes | Perp: `"OpenLong"`/`"CloseLong"`/`"OpenShort"`/`"CloseShort"`/`"Net"`. Spot: `"Buy"`/`"Sell"` |
| `fee_asset` | string? | No | Spot only: FA address `fee_amount` is denominated in (base for the buyer, quote for the seller). Absent on perp, where fees are in USDC |
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
| `asset_type` | string? | No | `"perp"` or `"spot"`; absent on pre-spot API versions (treat as perp) |

Spot markets reuse this shape: `sz_decimals` is the base asset's decimals, `px_decimals` the
quote's, and `max_leverage` / `max_open_interest` are 0 (spot is unleveraged). `mode` is `"Open"`.
`/api/v1/markets` returns both products; the SDK filters spot rows out by default so existing perp
callers see no change.

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
| `asset_type` | string? | No | `"perp"` or `"spot"`; absent on pre-spot API versions (treat as perp) |

### 11.8 PaginatedResponse\<T\>

```json
{
  "items": [ T, ... ],
  "total_count": 42
}
```

All paginated responses SHALL include `items` (array) and `total_count` (int32).

### 11.9 SpotAssetContextDto

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `market_addr` | string | Yes | Spot market address |
| `name` | string | Yes | Market name (e.g. `"APT/USDC"`) |
| `ticker_id` | string | Yes | Ticker identifier (e.g. `"APT_USDC"`) |
| `base_asset_addr` | string | Yes | Base FA metadata address |
| `quote_asset_addr` | string | Yes | Quote FA metadata address |
| `base_decimals` | uint32 | Yes | Base asset decimals |
| `quote_decimals` | uint32 | Yes | Quote asset decimals |
| `last_price` | float64? | Yes | Last trade price; null with no 24h trades |
| `mid` | float64? | Yes | Book mid; null unless both sides have resting liquidity |
| `prev_day_price` | float64? | Yes | Price at the 24h boundary; null if it never traded before it |
| `volume_24h_base` | float64 | Yes | 24h volume in base units |
| `volume_24h_quote` | float64 | Yes | 24h volume in quote units |
| `high_24h` | float64? | Yes | 24h high; null with no 24h trades |
| `low_24h` | float64? | Yes | 24h low; null with no 24h trades |
| `timestamp_unix_ms` | int64 | Yes | Snapshot timestamp |

### 11.10 Enum Types

**AssetType:** `"perp"`, `"spot"` (absent on pre-spot API versions — treat as `"perp"`)

**TimeInForce:** `"GTC"`, `"IOC"`, `"POST_ONLY"`

**WithdrawQueueStatus:** `"Queued"`, `"Processed"`, `"Cancelled"`

**WithdrawCancelReason:** `"CancelledByUser"`, `"InsufficientWithdrawableBalance"`,
`"DepositCheckFailed"` (new reasons pass through unrecognized)

**CampaignType:** `"fee_rebate"`, `"maker_incentive"`, `"liquidation_rebate"`,
`"volume_milestone"`, `"first_funded_trial"`

**CampaignStatus:** `"draft"`, `"funded"`, `"active"`, `"expired"`, `"reclaimed"`, `"cancelled"`

**LockStatus:** `"Active"`, `"Claimed"`

**ReferralCodeSource:** `"admin"`, `"auto"`, `"reusable"`, `"predeposit"`, `"unknown"`

**AffiliateLevel:** `"L1"`, `"L2"`

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
