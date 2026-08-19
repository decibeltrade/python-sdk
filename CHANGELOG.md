# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-08-19

Brings the Python SDK to parity with the TypeScript SDK: spot trading plus the readers and write
methods that had not been ported.

### Added

- **Spot trading.** Read, write and admin support for the spot product alongside perps:
  - `DecibelWriteDex` / `DecibelWriteDexSync`: `place_spot_order`, `cancel_spot_order`,
    `place_spot_bulk_order`, `cancel_spot_bulk_order`, `cancel_spot_bulk_order_at_price_level`,
    `approve_max_spot_builder_fee`, `revoke_max_spot_builder_fee`, `set_hold_as_non_collateral`,
    and the permissionless `process_spot_pending_requests`.
  - `DecibelSpotAdminDex` / `DecibelSpotAdminDexSync` for spot market registration and quote
    metadata configuration.
  - `read.spot_asset_contexts.get_all()` (`GET /api/v1/spot/asset_contexts`) and
    `read.markets.get_all_spot()`.
  - An `asset_type` selector on the dual-product readers — `AssetTypeName` (`"perp"` / `"spot"`)
    for market-scoped lookups and `AssetTypeFilter` (`"perp"` / `"spot"` / `"all"`) for list
    filters. Every reader defaults to `perp`, so existing perp code is unaffected; `"all"` omits
    the query parameter rather than sending `asset_type=all`.
  - `get_spot_market_addr()`, `get_market_addr_for_product()`, `get_spot_engine_global_address()`
    and `round_to_tick_size_for_side()`. Spot market addresses derive from the deployment
    **package** via the `GlobalSpotEngine` named object, not from `perp_engine_global`.
  - `PlaceSpotOrderSuccess.pending_cbs`: `True` means the transaction committed but the order is
    queued behind a rate-limited CBS withdrawal rather than resting on the book.
  - Account overview gained the `spot`, `secondary_collateral`, `cross_available_to_trade`,
    `free_vault_equity`, `perp_equity_haircutted` and `fee_income` blocks (all optional).
  - WebSocket topics `all_spot_mids`, `withdraw_queue:{userAddr}` and
    `protected_trial_update:{userAddr}`. Market-scoped topics stay product-agnostic — a market
    address already encodes its product.
  - On-chain view helpers `read.spot_market_assets()` and `read.fungible_asset_metadata()`.
  - Regenerated testnet/mainnet ABI JSON with the spot Move modules. On a network where the spot
    modules aren't deployed, spot writes raise the existing
    `Cannot build transaction: missing ABI for <fn>`.
- **Runtime ABI fallback.** When a function id isn't in the bundled ABI, `build_tx` now fetches its
  module from the fullnode and caches the result instead of raising outright, matching the
  TypeScript SDK. This costs one extra request the first time a module is touched, and covers
  functions in modules the ABI generator doesn't list (`vault_admin_api::delegate_dex_actions_to`,
  among others). A module that genuinely isn't published still raises the same error.
- Campaign / funded-first-trade ABIs are now bundled. `decibel.abi.generate` fetches
  `campaign_manager`, `funded_first_trade` and `protected_trial` from `deployment.campaign_package`
  in addition to the modules under `deployment.package`, and records which package they came from in
  the new `campaignPackageAddress` field. Without this, every campaign / FFT write took the slow
  fallback path.
- **New readers**: `user_orders` (single order by id or client order id), `user_fees`,
  `withdraw_queue`, `tier`, `global_points_stats`, `trading_amps`, `points_leaderboard`, `streaks`,
  `campaigns`, `referrals` (including affiliates) and `funded_first_trade`, plus
  `user_bulk_orders.get_status()` / `.get_fills()`.
- **New write methods**: `update_order`, `withdraw_non_collateral`, `admin_create_subaccount`,
  `claim_campaign_reward`, `open_fft_trial`, `claim_fft_unlock` and `settle_fft_trial`.
- Examples for spot reads and writes, a spot trading section in the README, a market maker example, and a buy-low-sell-high bot example with validation and safety guards.
- Comprehensive REST and WebSocket API specifications, behavioral tests, and testnet integration coverage.

### Changed

- **Breaking: `write.withdraw()` now targets `dex_accounts_entry::withdraw_from_cross_collateral`
  instead of `dex_accounts_entry::withdraw_from_subaccount`**, matching the TypeScript SDK. Callers
  relying on the previous subaccount-scoped behaviour need to review their withdrawal flows.
- **Breaking: `Deployment` gained a required `spot_engine_global` field.** Code constructing a
  `Deployment` directly (rather than via `_create_deployment` or the bundled `TESTNET_CONFIG` /
  `MAINNET_CONFIG`) must now supply it — `get_spot_engine_global_address(package)` derives it. The
  new `campaign_package` and `fft_campaign_addr` fields are optional and default to unset.
- **Breaking: `NETNA_CONFIG` is no longer available.** Use `TESTNET_CONFIG` instead; bundled ABIs now cover testnet and mainnet.
- Shared HTTP clients reduce SDK connection setup overhead.
- Updated bundled testnet and mainnet ABIs from the live Aptos deployments; transaction confirmation retries, WebSocket lifecycle handling, reader request models, and simulation timeouts were improved.

### Fixed

- `user_open_orders`, `user_order_history` and `user_twap_history` now send the `account` query
  parameter instead of `user`, matching the REST specification and the TypeScript SDK.
- `DecibelAdminDex.usdc_balance` returned garbage: `RestClient.view()` hands back the raw response
  body, and the result was indexed without decoding it first. It is now JSON-decoded, as are the
  other on-chain view helpers.
- The sync admin view helpers (`DecibelAdminDexSync.usdc_balance`,
  `DecibelSpotAdminDexSync.list_market_addresses`) now `raise_for_status()`, so a fullnode error
  surfaces as an HTTP error rather than an `IndexError` on the error body.
- `merge_withdraw_queue_entries` now backfills `cancel_reason` when deduplicating the `existing`
  list, matching how it already handled the delta pass; a Cancelled entry split across two rows
  could previously lose its reason.
- `UserBulkOrder.previous_seq_num` now defaults to `None` instead of being a required field.
- Sync/async signature drift: `DecibelWriteDexSync.cancel_twap_order` accepts `order_id: int | str`
  like its async counterpart (was `str`-only), and `DecibelWriteDexSync.create_vault` accepts and
  forwards `txn_submit_timeout` / `txn_confirm_timeout` like every other write method.
- The funded-first-trade on-chain lock scan no longer aborts on a single unreadable lock struct —
  it skips the entry, matching the TypeScript fallback. This is already the degraded path, so one
  bad entry sinking the whole scan defeated its purpose.
- Builder-fee basis-point conversion, additional REST-reader models and query parameters, order-status behavior, and fee-payer request handling.
- Synchronized the SDK runtime version with distribution metadata.

## [0.2.1] - 2026-04-08

### Fixed

- Order status requests now send the correct query parameter ([#7](https://github.com/decibeltrade/python-sdk/pull/7)).

### Changed

- Transaction confirmation: clearer exception handling in the confirmation loop and additional logging around order placement ([#9](https://github.com/decibeltrade/python-sdk/pull/9)).

## [0.2.0] - 2026-04-06

Configurable transaction timeouts, Aptos contract ABI and registry updates for testnet and mainnet, custom submit/confirm exceptions, and CI improvements including release tagging. See the [v0.2.0](https://github.com/decibeltrade/python-sdk/releases/tag/v0.2.0) release on GitHub.

[0.3.0]: https://github.com/decibeltrade/python-sdk/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/decibeltrade/python-sdk/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/decibeltrade/python-sdk/releases/tag/v0.2.0
