# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-04-08

### Fixed

- Order status requests now send the correct query parameter ([#7](https://github.com/decibeltrade/python-sdk/pull/7)).

### Changed

- Transaction confirmation: clearer exception handling in the confirmation loop and additional logging around order placement ([#9](https://github.com/decibeltrade/python-sdk/pull/9)).

## [0.2.0] - 2026-04-06

Configurable transaction timeouts, Aptos contract ABI and registry updates for testnet and mainnet, custom submit/confirm exceptions, and CI improvements including release tagging. See the [v0.2.0](https://github.com/decibeltrade/python-sdk/releases/tag/v0.2.0) release on GitHub.

[0.2.1]: https://github.com/decibeltrade/python-sdk/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/decibeltrade/python-sdk/releases/tag/v0.2.0
