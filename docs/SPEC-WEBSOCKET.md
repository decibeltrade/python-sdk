# Decibel Python SDK — WebSocket API Specification

> **Source:** AsyncAPI 3.0.0 spec at `https://docs.decibel.trade/api-reference/asyncapi.json`
> **Servers:**
> - Mainnet: `wss://api.mainnet.aptoslabs.com/decibel/ws`
> - Testnet: `wss://api.testnet.aptoslabs.com/decibel/ws`

## Table of Contents

1. [Connection Protocol](#1-connection-protocol)
2. [Subscription Protocol](#2-subscription-protocol)
3. [Market Data Channels](#3-market-data-channels)
4. [Account Channels](#4-account-channels)
5. [Order Management Channels](#5-order-management-channels)
6. [TWAP Channels](#6-twap-channels)
7. [Notification Channels](#7-notification-channels)
8. [SDK Subscription Interface](#8-sdk-subscription-interface)
9. [Message Schemas](#9-message-schemas)

---

## 1. Connection Protocol

### 1.1 Connection Establishment

The client SHALL connect via WSS with authentication in the subprotocol header:

```
WebSocket URL: wss://api.mainnet.aptoslabs.com/decibel/ws
Sec-Websocket-Protocol: decibel, <API_KEY>
```

### 1.2 Connection Lifecycle

```
┌──────────┐   WSS Connect    ┌──────────┐
│  Client  │ ───────────────> │  Server  │
│          │   (w/ API key)   │          │
│          │ <─────────────── │          │
│          │   Connection OK  │          │
│          │                  │          │
│          │   subscribe msg  │          │
│          │ ───────────────> │          │
│          │ <─────────────── │          │
│          │   {success:true} │          │
│          │                  │          │
│          │ <─────────────── │          │
│          │   data messages  │          │
│          │   (continuous)   │          │
│          │                  │          │
│          │   ping frame     │          │
│          │ <─────────────── │          │ (every 30s)
│          │ ───────────────> │          │
│          │   pong frame     │          │
│          │                  │          │
│          │   unsubscribe    │          │
│          │ ───────────────> │          │
│          │ <─────────────── │          │
│          │   {success:true} │          │
│          │                  │          │
│          │   close frame    │          │
│          │ ───────────────> │          │
└──────────┘                  └──────────┘
```

### 1.3 Session Constraints

| Constraint | Value |
|-----------|-------|
| Maximum session duration | 1 hour |
| Heartbeat interval | 30 seconds (server → client ping) |
| Maximum subscriptions per connection | 100 topics |

### 1.4 Heartbeat

- The server SHALL send WebSocket ping frames every 30 seconds.
- The ping timer resets upon receiving a pong response or when the client subscribes/unsubscribes.
- The client SHALL respond with pong frames to maintain the connection.
- If the server does not receive a pong within the heartbeat interval, it MAY close the connection.

### 1.5 Reconnection Strategy

The SDK SHALL implement automatic reconnection with:
1. Exponential backoff between retry attempts
2. Preservation of active subscription list for restoration after reconnect
3. Automatic re-subscription to all previously subscribed topics upon reconnection

---

## 2. Subscription Protocol

### 2.1 Subscribe Request

```json
{
  "method": "subscribe",
  "topic": "account_open_orders:0x1234..."
}
```

### 2.2 Subscribe Response (Success)

```json
{
  "success": true,
  "message": "Subscribed to account_open_orders:0x1234..."
}
```

> **Note:** Subscribe/unsubscribe response (ACK) frames do NOT contain a `topic` field.
> They are control messages identified by the `success` field. Clients SHALL treat any
> message containing a `success` field as a non-data ACK and silently ignore it.

### 2.3 Subscribe Response (Error)

```json
{
  "success": false,
  "message": "Unknown topic type 'invalid_topic'"
}
```

Other error messages:
- `"Maximum client topic subscription count of 100 reached"`

### 2.4 Unsubscribe Request

```json
{
  "method": "unsubscribe",
  "topic": "account_open_orders:0x1234..."
}
```

### 2.5 Unsubscribe Response

```json
{
  "success": true,
  "message": "Unsubscribed from account_open_orders:0x1234..."
}
```

### 2.6 Data Messages

All data messages SHALL include a `topic` field matching the subscribed topic string:

```json
{
  "topic": "account_open_orders:0x1234...",
  "orders": [ ... ]
}
```

### 2.7 Initial Snapshot Behavior

Upon subscribing to a topic, the server SHALL send the current state as the first message. Subsequent messages are incremental updates.

---

## 3. Market Data Channels

> **Products.** Market-scoped topics (`depth:`, `trades:`, `market_candlestick:`, `market_price:`)
> are **product-agnostic**: they are keyed by market address, and the address already encodes the
> product — perp addresses derive from the perp engine, spot addresses from the spot engine. A spot
> subscription therefore differs from a perp one only in the address, and no `asset_type` parameter
> appears anywhere in a topic string. Payload rows on the dual-product channels carry an
> `asset_type` field; it is absent on API versions predating spot, which SHALL be read as `"perp"`.

### 3.1 All Market Prices

**Topic:** `all_market_prices`

**Description:** Price updates for all markets. Global topic (no parameters).

**Message Schema:**
```json
{
  "topic": "all_market_prices",
  "prices": [
    {
      "market": "0x...",
      "oracle_px": 50125.75,
      "mark_px": 50120.5,
      "mid_px": 50122.25,
      "funding_rate_bps": 5,
      "is_funding_positive": true,
      "transaction_unix_ms": 1699564800000,
      "open_interest": 125000.5
    }
  ]
}
```

**Payload Type:** `AllMarketPricesResponse`

| Field | Type | Required |
|-------|------|----------|
| `topic` | string | Yes |
| `prices` | PriceDto[] | Yes |

**Notes:**
- `funding_rate_bps` is EMA-smoothed (unlike REST which returns raw values)
- Updates are broadcast whenever any market price changes

---

### 3.2 Market Price (Single)

**Topic:** `market_price:{marketAddr}`

**Example:** `market_price:0xabcdef...`

**Message Schema:**
```json
{
  "topic": "market_price:0xabcdef...",
  "price": {
    "market": "0xabcdef...",
    "oracle_px": 50125.75,
    "mark_px": 50120.5,
    "mid_px": 50122.25,
    "funding_rate_bps": 5,
    "is_funding_positive": true,
    "transaction_unix_ms": 1699564800000,
    "open_interest": 125000.5
  }
}
```

**Payload Type:** `MarketPriceResponse`

| Field | Type | Required |
|-------|------|----------|
| `topic` | string | Yes |
| `price` | PriceDto | Yes |

---

### 3.3 Market Depth (Order Book)

**Topic:** `depth:{marketAddr}:{aggregationLevel}`

**Examples:**
- `depth:0xabcdef...:1` (tick-level granularity)
- `depth:0xabcdef...:100` (100-tick aggregation)

**Aggregation Levels:** `1`, `2`, `5`, `10`, `100`, `1000`

If aggregation level is omitted, defaults to `1`.

**Message Schema:**
```json
{
  "topic": "depth:0xabcdef...:1",
  "market": "0xabcdef...",
  "bids": [
    { "price": 50000.0, "size": 10.5 },
    { "price": 49950.0, "size": 15.2 }
  ],
  "asks": [
    { "price": 50050.0, "size": 8.3 },
    { "price": 50100.0, "size": 12.7 }
  ]
}
```

**Payload Type:** `MarketDepthResponse`

| Field | Type | Required |
|-------|------|----------|
| `topic` | string | Yes |
| `market` | string | Yes |
| `bids` | NormalizedPriceLevel[] | Yes |
| `asks` | NormalizedPriceLevel[] | Yes |

**NormalizedPriceLevel:**

| Field | Type | Required |
|-------|------|----------|
| `price` | float64 | Yes |
| `size` | float64 | Yes |

**Notes:**
- Each message is a full snapshot of the order book (not incremental deltas)
- Use sequence tracking for ordering if needed

---

### 3.4 Market Trades

**Topic:** `trades:{marketAddr}`

**Example:** `trades:0xabcdef...`

**Message Schema:**
```json
{
  "topic": "trades:0xabcdef...",
  "trades": [
    {
      "account": "0x...",
      "market": "0xabcdef...",
      "action": "Open Long",
      "trade_id": 3647277,
      "size": 0.8,
      "price": 50100.0,
      "is_profit": false,
      "realized_pnl_amount": -45.2,
      "is_funding_positive": true,
      "realized_funding_amount": 5.1,
      "is_rebate": false,
      "fee_amount": 20.04,
      "order_id": "45680",
      "client_order_id": "order_123",
      "transaction_unix_ms": 1699564900000,
      "transaction_version": 3647276286
    }
  ]
}
```

**Payload Type:** `MarketTradesResponse`

| Field | Type | Required |
|-------|------|----------|
| `topic` | string | Yes |
| `trades` | TradeDto[] | Yes |

---

### 3.5 Market Candlestick

**Topic:** `market_candlestick:{marketAddr}:{interval}`

**Example:** `market_candlestick:0xabcdef...:1h`

**Supported intervals:** `1m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `1d`, `1w`, `1mo`

**Message Schema:**
```json
{
  "topic": "market_candlestick:0xabcdef...:1h",
  "candle": {
    "t": 1699564800000,
    "T": 1699568400000,
    "o": 49800.0,
    "h": 50300.0,
    "l": 49600.0,
    "c": 50125.75,
    "v": 1250.5,
    "i": "1h"
  }
}
```

**Payload Type:** `MarketCandlestickResponse`

| Field | Type | Required |
|-------|------|----------|
| `topic` | string | Yes |
| `candle` | CandlestickResponseItemDto | Yes |

---

### 3.6 All Spot Mids

**Topic:** `all_spot_mids`

**Description:** Mid / last-trade prices for all spot markets. Global topic (no parameters). The
spot counterpart of `all_market_prices` — spot has no funding or open interest, so it carries prices
only.

**Message Schema:**
```json
{
  "topic": "all_spot_mids",
  "mids": [
    {
      "market_addr": "0xabcdef...",
      "asset_type": "spot",
      "mid": 12.51,
      "last_trade_price": 12.5,
      "transaction_unix_ms": 1699564800000
    }
  ]
}
```

**Payload Type:** `AllSpotMidsResponse`

| Field | Type | Required |
|-------|------|----------|
| `topic` | string | Yes |
| `mids` | MidDto[] | Yes |

**MidDto:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `market_addr` | string | Yes | Spot market address |
| `asset_type` | string | Yes | `"spot"` |
| `mid` | float64? | Yes | Null unless both book sides have resting liquidity |
| `last_trade_price` | float64? | Yes | Null until the market's first fill |
| `transaction_unix_ms` | int64 | Yes | Update timestamp |

**Notes:**
- Each update carries one row per registered spot market.

---

## 4. Account Channels

### 4.1 Account Overview

**Topic:** `account_overview:{userAddr}`

**Message Schema:**
```json
{
  "topic": "account_overview:0x1234...",
  "account_overview": {
    "perp_equity_balance": 50250.75,
    "unrealized_pnl": 1250.5,
    "realized_pnl": 0,
    "unrealized_funding_cost": -125.25,
    "cross_margin_ratio": 0.15,
    "maintenance_margin": 2500.0,
    "cross_account_leverage_ratio": 500.0,
    "volume": 125000.0,
    "all_time_return": 0.25,
    "pnl_90d": 5000.0,
    "sharpe_ratio": 1.8,
    "max_drawdown": -0.08,
    "weekly_win_rate_12w": 0.65,
    "average_cash_position": 45000.0,
    "average_leverage": 5.5,
    "cross_account_position": 25000.0,
    "total_margin": 10000.0,
    "usdc_cross_withdrawable_balance": 7500.0,
    "usdc_isolated_withdrawable_balance": 2500.0
  }
}
```

**Payload Type:** `AccountOverviewResponse`

| Field | Type | Required |
|-------|------|----------|
| `topic` | string | Yes |
| `account_overview` | AccountOverviewDto | Yes |

---

### 4.2 User Positions

**Topic:** `account_positions:{userAddr}`

**Message Schema:**
```json
{
  "topic": "account_positions:0x1234...",
  "positions": [
    {
      "market": "0x...",
      "user": "0x1234...",
      "size": 2.5,
      "user_leverage": 10,
      "max_allowed_leverage": 20,
      "entry_price": 49800.0,
      "is_isolated": false,
      "is_deleted": false,
      "unrealized_funding": -25.5,
      "event_uid": 123456789012345678901234567890123456,
      "estimated_liquidation_price": 45000.0,
      "transaction_version": 12345681,
      "tp_order_id": "tp_001",
      "tp_trigger_price": 52000,
      "tp_limit_price": 51900,
      "sl_order_id": "sl_001",
      "sl_trigger_price": 48000,
      "sl_limit_price": null,
      "has_fixed_sized_tpsls": false
    }
  ]
}
```

**Payload Type:** `UserPositionsResponse`

| Field | Type | Required |
|-------|------|----------|
| `topic` | string | Yes |
| `positions` | PositionDto[] | Yes |

**WebSocket-specific PositionDto fields (not in REST):**
- `max_allowed_leverage` (uint32, required)
- `event_uid` (u128, required)

**WebSocket TP/SL price fields** are `int64` (chain units), unlike REST which uses `float64`.

---

### 4.3 User Open Orders

**Topic:** `account_open_orders:{userAddr}`

**Message Schema:**
```json
{
  "topic": "account_open_orders:0x1234...",
  "orders": [
    {
      "parent": "0x...",
      "market": "0x...",
      "client_order_id": "order_123",
      "order_id": "45678",
      "status": "Open",
      "order_type": "Limit",
      "trigger_condition": "None",
      "order_direction": "Open Long",
      "orig_size": 1.5,
      "remaining_size": 1.5,
      "size_delta": null,
      "price": 50000.5,
      "is_buy": true,
      "is_reduce_only": false,
      "details": "",
      "tp_order_id": null,
      "tp_trigger_price": null,
      "tp_limit_price": null,
      "sl_order_id": null,
      "sl_trigger_price": null,
      "sl_limit_price": null,
      "transaction_version": 12345678,
      "unix_ms": 1699564800000
    }
  ]
}
```

**Payload Type:** `UserOpenOrdersResponse`

| Field | Type | Required |
|-------|------|----------|
| `topic` | string | Yes |
| `orders` | OrderDto[] | Yes |

---

### 4.4 User Trades

**Topic:** `user_trades:{userAddr}`

**Description:** Live trade execution stream (different from trade history which includes historical data).

**Message Schema:**
```json
{
  "topic": "user_trades:0x1234...",
  "trades": [ ... ]
}
```

**Payload Type:** `UserTradesResponse` (same schema as UserTradeHistoryResponse)

---

### 4.7 User Funding Rate History

**Topic:** `user_funding_rate_history:{userAddr}`

**Message Schema:**
```json
{
  "topic": "user_funding_rate_history:0x1234...",
  "funding_rates": [
    {
      "market": "0x...",
      "action": "Close Long",
      "size": 1.5,
      "is_funding_positive": false,
      "realized_funding_amount": -12.3,
      "is_rebate": false,
      "fee_amount": 5.15,
      "transaction_unix_ms": 1699564800000
    }
  ]
}
```

**Payload Type:** `UserFundingRateHistoryResponse`

| Field | Type | Required |
|-------|------|----------|
| `topic` | string | Yes |
| `funding_rates` | FundingRateHistory[] | Yes |

**Note:** WebSocket FundingRateHistory includes `is_funding_positive` field which is absent from REST FundingRateHistory.

---

### 4.8 Withdraw Queue

**Topic:** `withdraw_queue:{userAddr}`

**Description:** Incremental updates to an account's async withdrawal queue. Withdrawals settle
asynchronously, so a single `request_id` produces several events over its lifetime
(Queued → Processed / Cancelled, plus one row per partial fill).

**Message Schema:**
```json
{
  "topic": "withdraw_queue:0x1234...",
  "entries": [
    {
      "user": "0x1234...",
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
  ]
}
```

**Payload Type:** `WithdrawQueueUpdate`

| Field | Type | Required |
|-------|------|----------|
| `topic` | string | Yes |
| `entries` | WithdrawQueueEntry[] | Yes |

**Notes:**
- Deltas, not snapshots. Seed from `GET /api/v1/withdraw_queue` (Section 3.8 of SPEC-REST) and merge
  by `request_id`.
- Delivery is **at-least-once**: apply an update only when its `transaction_version` is *strictly*
  greater than the one held, or a redelivery will overwrite merged fields with nulls.
- On reconnect, merge with the WS cache as the base and the HTTP snapshot as the delta, so HTTP data
  cannot regress entries the WS has already advanced.
- `queued_at_ms` may be null on deltas whose Queued event was in a different batch. Do not fall back
  to `timestamp_ms` — that is the latest event's time.
- Carry `cancel_reason` forward only between Cancelled rows, or a Queued row ends up wearing a stale
  reason.

---

## 5. Order Management Channels

### 5.1 Order Update

**Topic:** `order_updates:{userAddr}`

**Description:** Real-time order status change events. Fires for each individual order state transition.

**Message Schema:**
```json
{
  "topic": "order_updates:0x1234...",
  "order": {
    "status": "Filled",
    "details": "",
    "order": {
      "parent": "0x...",
      "market": "0x...",
      "client_order_id": "historical_order_456",
      "order_id": "45679",
      "status": "Filled",
      "order_type": "Market",
      "trigger_condition": "None",
      "order_direction": "Close Short",
      "orig_size": 2.0,
      "remaining_size": 0.0,
      "size_delta": null,
      "price": 49500.0,
      "is_buy": false,
      "is_reduce_only": false,
      "details": "",
      "tp_order_id": null,
      "tp_trigger_price": null,
      "tp_limit_price": null,
      "sl_order_id": null,
      "sl_trigger_price": null,
      "sl_limit_price": null,
      "transaction_version": 12345680,
      "unix_ms": 1699565000000
    }
  }
}
```

**Payload Type:** `OrderUpdateResponse`

| Field | Type | Required |
|-------|------|----------|
| `topic` | string | Yes |
| `order` | OrderUpdate | Yes |

**OrderUpdate:**

| Field | Type | Required |
|-------|------|----------|
| `status` | string | Yes |
| `details` | string | Yes |
| `order` | OrderDto | Yes |

---

### 5.2 Bulk Orders

**Topic:** `bulk_orders:{userAddr}`

**Message Schema:**
```json
{
  "topic": "bulk_orders:0x1234...",
  "bulk_order": {
    "status": "Placed",
    "details": "",
    "bulk_order": {
      "market": "0x...",
      "user": "0x1234...",
      "sequence_number": 100,
      "previous_seq_num": 99,
      "bid_prices": [50000, 49900],
      "bid_sizes": [1, 2],
      "ask_prices": [50100, 50200],
      "ask_sizes": [1.5, 2.5],
      "cancelled_bid_prices": [],
      "cancelled_bid_sizes": [],
      "cancelled_ask_prices": [],
      "cancelled_ask_sizes": [],
      "transaction_version": 12345678,
      "transaction_unix_ms": 1699564800000,
      "event_uid": 123456789012345678901234567890123456
    }
  }
}
```

**Payload Type:** `BulkOrdersResponse`

| Field | Type | Required |
|-------|------|----------|
| `topic` | string | Yes |
| `bulk_order` | BulkOrderStatusResponse | Yes |

---

### 5.3 Bulk Order Fills

**Topic:** `bulk_order_fills:{userAddr}`

**Message Schema:**
```json
{
  "topic": "bulk_order_fills:0x1234...",
  "bulk_order_fills": [
    {
      "market": "0x...",
      "sequence_number": 100,
      "user": "0x1234...",
      "filled_size": 1.5,
      "price": 50000.0,
      "is_bid": true,
      "transaction_unix_ms": 1699564800000,
      "transaction_version": 12345682,
      "event_uid": 123456789012345678901234567890123456
    }
  ]
}
```

**Payload Type:** `BulkOrderFillsResponse`

| Field | Type | Required |
|-------|------|----------|
| `topic` | string | Yes |
| `bulk_order_fills` | BulkOrderFillDto[] | Yes |

---

## 6. TWAP Channels

### 6.1 User Active TWAPs

**Topic:** `user_active_twaps:{userAddr}`

**Message Schema:**
```json
{
  "topic": "user_active_twaps:0x1234...",
  "twaps": [
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
      "transaction_unix_ms": 1699564800000,
      "transaction_version": 12345679
    }
  ]
}
```

**Payload Type:** `UserActiveTwapsResponse`

| Field | Type | Required |
|-------|------|----------|
| `topic` | string | Yes |
| `twaps` | TwapDto[] | Yes |

---

## 7. Notification Channels

### 7.1 Notifications

**Topic:** `notifications:{userAddr}`

**Message Schema:**
```json
{
  "topic": "notifications:0x1234...",
  "notification": {
    "account": "0x1234...",
    "notification_type": "OrderFilled",
    "order": { ... },
    "twap": null,
    "notification_metadata": null
  }
}
```

**Payload Type:** `UserNotificationResponse`

| Field | Type | Required |
|-------|------|----------|
| `topic` | string | Yes |
| `notification` | NotificationDto | Yes |

**NotificationDto:**

| Field | Type | Required |
|-------|------|----------|
| `account` | string | Yes |
| `notification_type` | NotificationType | Yes |
| `order` | OrderDto? | No |
| `twap` | TwapDto? | No |
| `notification_metadata` | NotificationMetadata? | No |

**NotificationMetadata:**

| Field | Type | Required |
|-------|------|----------|
| `amount` | int64? | No |
| `filled_size` | float64? | No |
| `reason` | string? | No |
| `trigger_price` | uint64? | No |

**NotificationType values:**
- Order lifecycle: `MarketOrderPlaced`, `LimitOrderPlaced`, `StopMarketOrderPlaced`, `StopMarketOrderTriggered`, `StopLimitOrderPlaced`, `StopLimitOrderTriggered`, `OrderPartiallyFilled`, `OrderFilled`, `OrderSizeReduced`, `OrderCancelled`, `OrderRejected`, `OrderErrored`
- TWAP lifecycle: `TwapOrderPlaced`, `TwapOrderTriggered`, `TwapOrderCompleted`, `TwapOrderCancelled`, `TwapOrderErrored`
- Account events: `AccountDeposit`, `AccountWithdrawal`
- TP/SL events: `TpSlSet`, `TpHit`, `SlHit`, `TpCancelled`, `SlCancelled`

---

### 7.2 Protected Trial Update (Funded First Trade)

**Topic:** `protected_trial_update:{userAddr}`

**Description:** Fires on `TrialOpened`, `TrialClosed` and `TrialResetByAdmin` for the funded-first-
trade campaign.

**Message Schema:**
```json
{
  "topic": "protected_trial_update:0x1234...",
  "trials": [
    {
      "trial_id": 1,
      "user": "0x1234...",
      "campaign_addr": "0x...",
      "status": "Active",
      "size": 1.5,
      "market": "0x...",
      "side": "Long",
      "opened_at_ms": 1699564800000,
      "expires_at_ms": 1699565400000
    }
  ]
}
```

**Payload Type:** `ProtectedTrialUpdate`

| Field | Type | Required |
|-------|------|----------|
| `topic` | string | Yes |
| `trials` | TrialDto[] | Yes |

**Notes:**
- Streaming-only: there is no initial snapshot. Seed from `GET /api/v1/protected_trials`
  (SPEC-REST Section 10.4) and merge by `trial_id`.
- Terminal pushes may omit the open-sourced fields (`mark_at_open`, `market`, `side`, …), so a merge
  SHALL preserve the values already held rather than overwriting them with nulls.

---

## 8. SDK Subscription Interface

### 8.1 Subscribe Method

The SDK SHALL provide a `subscribe` method on the WebSocket client:

```python
def subscribe(
    topic: str,
    model: type[BaseModel],
    on_data: Callable[[BaseModel], None] | Callable[[BaseModel], Awaitable[None]]
) -> Callable[[], None]:  # Returns unsubscribe function
```

**Behavior:**
1. If not connected, SHALL auto-connect to the WebSocket server
2. SHALL send a subscribe message to the server
3. SHALL parse incoming messages for the topic using the specified Pydantic model
4. SHALL invoke the `on_data` callback for each received message
5. SHALL support both sync and async callbacks
6. SHALL return a callable that unsubscribes when invoked

### 8.2 Unsubscribe Behavior

When the unsubscribe function is called:
1. SHALL send an unsubscribe message to the server
2. SHALL remove the callback from the topic's subscriber list
3. If no more subscribers exist for any topic, SHOULD close the connection after a short delay

### 8.3 Reset Method

```python
def reset(topic: str) -> None:
```

Unsubscribes and re-subscribes to a topic (useful for forcing a fresh snapshot).

### 8.4 Connection States

```python
def ready_state() -> int:
```

Returns:
- `0` — CONNECTING
- `1` — OPEN
- `2` — CLOSING
- `3` — CLOSED

### 8.5 Close Method

```python
def close() -> None:
```

Closes the WebSocket connection and removes all subscriptions.

---

## 9. Message Schemas

### 9.1 Schema Differences: REST vs WebSocket

The following differences exist between REST and WebSocket DTOs:

| Field | REST | WebSocket |
|-------|------|-----------|
| `PositionDto.max_allowed_leverage` | absent | present (uint32) |
| `PositionDto.event_uid` | absent | present (u128) |
| `PositionDto.tp/sl prices` | float64 | int64 (chain units) |
| `FundingRateHistory.is_funding_positive` | absent | present (bool) |
| `TradeDto.source` | present | absent |
| `TradeDto.trade_id` | string | integer |
| `TradeDto.is_funding_positive` | absent | present (bool) |
| `BulkOrderDto.cancellation_reason` | present | absent |
| `BulkOrderDto.event_uid` | string (u128) | number |
| `PriceDto.funding_rate_bps` | float64 (raw) | integer (EMA-smoothed) |

The SDK SHALL define separate Pydantic models for REST and WebSocket response types where the schemas diverge, OR use optional fields where appropriate to handle both.

### 9.2 BigInt Handling

Some fields (e.g., `event_uid`) may exceed JavaScript's safe integer range. The SDK SHALL:
1. Parse JSON with a custom deserializer that handles large integers
2. Represent u128 values as Python `int` (which supports arbitrary precision)

### 9.3 Topic String Format

All topic strings follow the pattern: `{channel_name}:{parameter}:{optional_parameter}`

| Channel | Topic Pattern | Parameters |
|---------|--------------|------------|
| All Market Prices | `all_market_prices` | none |
| All Spot Mids | `all_spot_mids` | none |
| Market Price | `market_price:{marketAddr}` | market address |
| Market Depth | `depth:{marketAddr}:{aggregation}` | market address, aggregation level |
| Market Trades | `trades:{marketAddr}` | market address |
| Market Candlestick | `market_candlestick:{marketAddr}:{interval}` | market address, interval |
| Account Overview | `account_overview:{userAddr}` | subaccount address |
| User Positions | `account_positions:{userAddr}` | subaccount address |
| User Open Orders | `account_open_orders:{userAddr}` | subaccount address |
| User Trades | `user_trades:{userAddr}` | subaccount address |
| User Funding History | `user_funding_rate_history:{userAddr}` | subaccount address |
| Order Updates | `order_updates:{userAddr}` | subaccount address |
| Bulk Orders | `bulk_orders:{userAddr}` | subaccount address |
| Bulk Order Fills | `bulk_order_fills:{userAddr}` | subaccount address |
| User Active TWAPs | `user_active_twaps:{userAddr}` | subaccount address |
| Notifications | `notifications:{userAddr}` | subaccount address |
| Withdraw Queue | `withdraw_queue:{userAddr}` | subaccount address |
| Protected Trial Update | `protected_trial_update:{userAddr}` | account address |

> **Note:** No topic string carries an `asset_type` component. Market-scoped topics are keyed by
> market address, which already encodes the product; account-scoped topics stream both products and
> tag each row with `asset_type`.

> **Note:** The AsyncAPI spec at docs.decibel.trade uses `user_positions` and `user_open_orders`
> as channel names, but the actual server topics used by the SDK are `account_positions` and
> `account_open_orders`. The SDK's `UserOrderHistoryReader` subscribes to `order_updates` (not
> `user_order_history`) which provides real-time order status change events.
