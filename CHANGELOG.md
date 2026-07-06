# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Feature parity with the TypeScript SDK ([#18](https://github.com/decibeltrade/python-sdk/pull/18)):
  - Write methods: `update_order`, `withdraw_non_collateral`, `admin_create_subaccount`, and `claim_campaign_reward` (with a new `campaign_package` field on `Deployment`), on both `DecibelWriteDex` and `DecibelWriteDexSync`.
  - Read-client on-chain view helpers: `global_perp_engine_state`, `collateral_balance_decimals`, `usdc_decimals`, `usdc_balance`, `token_balance`, `account_balance`, `position_size`, and `get_crossed_position`.
  - Read namespaces: `campaigns`, `points_leaderboard`, `streaks`, `trading_amps`, `tier`, `global_points_stats`, `referrals`, `user_fees`, and `withdraw_queue` (with WebSocket subscription, on-chain pending-withdrawals fallback, and merge helpers).
  - Utilities: `calculate_liquidation_price`, `to_checksum_address` (EIP-55), and `derive_aptos_from_eth` / `derive_aptos_from_solana` (derivable accounts).

## [0.2.1] - 2026-04-08

### Fixed

- Order status requests now send the correct query parameter ([#7](https://github.com/decibeltrade/python-sdk/pull/7)).

### Changed

- Transaction confirmation: clearer exception handling in the confirmation loop and additional logging around order placement ([#9](https://github.com/decibeltrade/python-sdk/pull/9)).

## [0.2.0] - 2026-04-06

Configurable transaction timeouts, Aptos contract ABI and registry updates for testnet and mainnet, custom submit/confirm exceptions, and CI improvements including release tagging. See the [v0.2.0](https://github.com/decibeltrade/python-sdk/releases/tag/v0.2.0) release on GitHub.

[Unreleased]: https://github.com/decibeltrade/python-sdk/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/decibeltrade/python-sdk/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/decibeltrade/python-sdk/releases/tag/v0.2.0
