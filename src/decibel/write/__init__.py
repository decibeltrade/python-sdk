from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, TypeVar, cast

from decibel._base import BaseSDK, BaseSDKOptions, BaseSDKOptionsSync, BaseSDKSync
from decibel._order_status import OrderStatusClient
from decibel._order_types import (
    PlaceBulkOrdersFailure,
    PlaceBulkOrdersResult,
    PlaceBulkOrdersSuccess,
    PlaceOrderFailure,
    PlaceOrderResult,
    PlaceOrderSuccess,
)
from decibel._subaccount_types import RenameSubaccount, RenameSubaccountArgs
from decibel._transaction_builder import InputEntryFunctionData
from decibel._utils import (
    get_market_addr,
    get_primary_subaccount_addr,
    post_request,
    post_request_sync,
)

from ._types import TimeInForce

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from aptos_sdk.account import Account
    from aptos_sdk.account_address import AccountAddress

    from decibel._constants import DecibelConfig
    from decibel._transaction_builder import SimpleTransaction
    from decibel.read._types import CreateVaultArgs

__all__ = [
    "DecibelWriteDex",
    "DecibelWriteDexSync",
    "TimeInForce",
]

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _round_to_tick_size(value: int | float, tick_size: int | float) -> int | float:
    if value == 0 or tick_size == 0:
        return 0.0
    return round(value / tick_size) * tick_size


class DecibelWriteDex(BaseSDK):
    def __init__(
        self,
        config: DecibelConfig,
        account: Account,
        opts: BaseSDKOptions | None = None,
    ) -> None:
        super().__init__(config, account, opts)
        self._order_status_client = OrderStatusClient(config)

    @property
    def order_status_client(self) -> OrderStatusClient:
        return self._order_status_client

    def _extract_order_id_from_transaction(
        self,
        tx_response: dict[str, Any],
        subaccount_addr: str | None = None,
    ) -> str | None:
        order_event_types = [
            "market_types::OrderEvent",
            "async_matching_engine::TwapEvent",
        ]
        try:
            events: list[dict[str, Any]] | None = tx_response.get("events")
            if events is None:
                return None
            for event in events:
                event_type = str(event.get("type", ""))
                for oe_type in order_event_types:
                    if oe_type in event_type:
                        event_data: dict[str, Any] | None = event.get("data")
                        if event_data is None:
                            continue
                        user_address = subaccount_addr or str(self._account.address())
                        order_user_address = event_data.get("user")
                        twap_user_address = event_data.get("account")
                        if order_user_address == user_address or twap_user_address == user_address:
                            order_id = event_data.get("order_id")
                            if isinstance(order_id, str):
                                return order_id
                            if isinstance(order_id, dict):
                                oid = cast("dict[str, Any]", order_id).get("order_id")
                                return str(oid) if oid is not None else None
            return None
        except Exception as e:
            logger.error("Error extracting order_id from transaction: %s", e)
            return None

    async def send_subaccount_tx(
        self,
        send_tx: Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
        subaccount_addr: str | None = None,
    ) -> dict[str, Any]:
        if subaccount_addr is None:
            subaccount_addr = get_primary_subaccount_addr(
                self._account.address(),
                self._config.compat_version,
                self._config.deployment.package,
            )
        return await send_tx(subaccount_addr)

    async def with_subaccount(
        self,
        fn: Callable[[str], Coroutine[Any, Any, T]],
        subaccount_addr: str | None = None,
    ) -> T:
        if subaccount_addr is None:
            subaccount_addr = get_primary_subaccount_addr(
                self._account.address(),
                self._config.compat_version,
                self._config.deployment.package,
            )
        return await fn(subaccount_addr)

    async def rename_subaccount(
        self, args: RenameSubaccountArgs
    ) -> tuple[RenameSubaccount, int, str]:
        url = f"{self._config.trading_http_url}/api/v1/subaccounts/{args.subaccount_address}"
        return await post_request(
            RenameSubaccount,
            url,
            body={"name": args.new_name},
            api_key=self._node_api_key,
        )

    async def create_subaccount(self) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::dex_accounts_entry::create_new_subaccount",
                type_arguments=[],
                function_arguments=[],
            )
        )

    async def deposit(self, amount: int, subaccount_addr: str | None = None) -> dict[str, Any]:
        pkg = self._config.deployment.package
        usdc = self._config.deployment.usdc

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::deposit_to_subaccount_at",
                    type_arguments=[],
                    function_arguments=[addr, usdc, amount],
                )
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)

    async def withdraw(self, amount: int, subaccount_addr: str | None = None) -> dict[str, Any]:
        pkg = self._config.deployment.package
        usdc = self._config.deployment.usdc

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::withdraw_from_subaccount",
                    type_arguments=[],
                    function_arguments=[addr, usdc, amount],
                )
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)

    async def configure_user_settings_for_market(
        self,
        *,
        market_addr: str,
        subaccount_addr: str,
        is_cross: bool,
        user_leverage: int,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::configure_user_settings_for_market",
                    type_arguments=[],
                    function_arguments=[addr, market_addr, is_cross, user_leverage],
                )
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)

    async def place_order(
        self,
        *,
        market_name: str,
        price: int | float,
        size: int | float,
        is_buy: bool,
        time_in_force: TimeInForce,
        is_reduce_only: bool,
        client_order_id: str | None = None,
        stop_price: int | float | None = None,
        tp_trigger_price: int | float | None = None,
        tp_limit_price: int | float | None = None,
        sl_trigger_price: int | float | None = None,
        sl_limit_price: int | float | None = None,
        builder_addr: str | None = None,
        builder_fee: float | None = None,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
        tick_size: int | float | None = None,
    ) -> PlaceOrderResult:
        try:
            market_addr = get_market_addr(market_name, self._config.deployment.perp_engine_global)

            final_price = _round_to_tick_size(price, tick_size) if tick_size else price
            final_stop_price = (
                _round_to_tick_size(stop_price, tick_size)
                if stop_price is not None and tick_size
                else stop_price
            )
            final_tp_trigger = (
                _round_to_tick_size(tp_trigger_price, tick_size)
                if tp_trigger_price is not None and tick_size
                else tp_trigger_price
            )
            final_tp_limit = (
                _round_to_tick_size(tp_limit_price, tick_size)
                if tp_limit_price is not None and tick_size
                else tp_limit_price
            )
            final_sl_trigger = (
                _round_to_tick_size(sl_trigger_price, tick_size)
                if sl_trigger_price is not None and tick_size
                else sl_trigger_price
            )
            final_sl_limit = (
                _round_to_tick_size(sl_limit_price, tick_size)
                if sl_limit_price is not None and tick_size
                else sl_limit_price
            )

            pkg = self._config.deployment.package

            async def _send(addr: str) -> dict[str, Any]:
                return await self._send_tx(
                    InputEntryFunctionData(
                        function=f"{pkg}::dex_accounts_entry::place_order_to_subaccount",
                        type_arguments=[],
                        function_arguments=[
                            addr,
                            market_addr,
                            final_price,
                            size,
                            is_buy,
                            time_in_force,
                            is_reduce_only,
                            client_order_id,
                            final_stop_price,
                            final_tp_trigger,
                            final_tp_limit,
                            final_sl_trigger,
                            final_sl_limit,
                            builder_addr,
                            builder_fee,
                        ],
                    ),
                    account_override,
                )

            tx_response = await self.send_subaccount_tx(_send, subaccount_addr)

            order_id = self._extract_order_id_from_transaction(tx_response, subaccount_addr)

            return PlaceOrderSuccess(
                success=True,
                orderId=order_id,
                transactionHash=tx_response.get("hash", ""),
            )
        except Exception as e:
            logger.error("Error placing order: %s", e)
            return PlaceOrderFailure(
                success=False,
                error=str(e),
            )

    async def trigger_matching(
        self,
        *,
        market_addr: str,
        max_work_unit: int,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        tx_response = await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::public_apis::process_perp_market_pending_requests",
                type_arguments=[],
                function_arguments=[market_addr, max_work_unit],
            )
        )
        return {
            "success": True,
            "transactionHash": tx_response.get("hash", ""),
        }

    async def place_twap_order(
        self,
        *,
        market_name: str,
        size: int | float,
        is_buy: bool,
        is_reduce_only: bool,
        twap_frequency_seconds: int,
        twap_duration_seconds: int,
        client_order_id: str | None = None,
        builder_address: str | None = None,
        builder_fees: float | None = None,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> PlaceOrderResult:
        market_addr = get_market_addr(market_name, self._config.deployment.perp_engine_global)
        pkg = self._config.deployment.package

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::place_twap_order_to_subaccount_v2",
                    type_arguments=[],
                    function_arguments=[
                        addr,
                        market_addr,
                        size,
                        is_buy,
                        is_reduce_only,
                        client_order_id,
                        twap_frequency_seconds,
                        twap_duration_seconds,
                        builder_address,
                        builder_fees,
                    ],
                ),
                account_override,
            )

        tx_response = await self.send_subaccount_tx(_send, subaccount_addr)

        order_id = self._extract_order_id_from_transaction(tx_response, subaccount_addr)

        return PlaceOrderSuccess(
            success=True,
            orderId=order_id,
            transactionHash=tx_response.get("hash", ""),
        )

    async def cancel_order(
        self,
        *,
        order_id: int | str,
        market_name: str | None = None,
        market_addr: str | None = None,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        if market_name is not None:
            resolved_market_addr = get_market_addr(
                market_name, self._config.deployment.perp_engine_global
            )
        elif market_addr is not None:
            resolved_market_addr = market_addr
        else:
            raise ValueError("Either market_name or market_addr must be provided")

        pkg = self._config.deployment.package

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::cancel_order_to_subaccount",
                    type_arguments=[],
                    function_arguments=[addr, int(order_id), resolved_market_addr],
                ),
                account_override,
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)

    async def place_bulk_orders(
        self,
        *,
        market_name: str,
        sequence_number: int,
        bid_prices: list[int],
        bid_sizes: list[int],
        ask_prices: list[int],
        ask_sizes: list[int],
        builder_addr: str | None = None,
        builder_fee: int | None = None,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> PlaceBulkOrdersResult:
        try:
            market_addr = get_market_addr(market_name, self._config.deployment.perp_engine_global)
            pkg = self._config.deployment.package

            async def _send(addr: str) -> dict[str, Any]:
                return await self._send_tx(
                    InputEntryFunctionData(
                        function=f"{pkg}::dex_accounts_entry::place_bulk_orders_to_subaccount",
                        type_arguments=[],
                        function_arguments=[
                            addr,
                            market_addr,
                            sequence_number,
                            bid_prices,
                            bid_sizes,
                            ask_prices,
                            ask_sizes,
                            builder_addr,
                            builder_fee,
                        ],
                    ),
                    account_override,
                )

            tx_response = await self.send_subaccount_tx(_send, subaccount_addr)

            return PlaceBulkOrdersSuccess(
                transactionHash=tx_response.get("hash", ""),
            )
        except Exception as e:
            logger.error("Error placing bulk orders: %s", e)
            return PlaceBulkOrdersFailure(error=str(e))

    async def cancel_bulk_order(
        self,
        *,
        market_name: str,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        market_addr = get_market_addr(market_name, self._config.deployment.perp_engine_global)
        pkg = self._config.deployment.package

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::cancel_bulk_order_to_subaccount",
                    type_arguments=[],
                    function_arguments=[addr, market_addr],
                ),
                account_override,
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)

    async def cancel_client_order(
        self,
        *,
        client_order_id: str,
        market_name: str,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        market_addr = get_market_addr(market_name, self._config.deployment.perp_engine_global)
        pkg = self._config.deployment.package

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::cancel_client_order_to_subaccount",
                    type_arguments=[],
                    function_arguments=[addr, client_order_id, market_addr],
                ),
                account_override,
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)

    async def delegate_trading_to_for_subaccount(
        self,
        *,
        subaccount_addr: str,
        account_to_delegate_to: str,
        expiration_timestamp_secs: int | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::delegate_trading_to_for_subaccount",
                    type_arguments=[],
                    function_arguments=[
                        addr,
                        account_to_delegate_to,
                        expiration_timestamp_secs,
                    ],
                )
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)

    async def revoke_delegation(
        self,
        *,
        account_to_revoke: str,
        subaccount_addr: str | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::revoke_delegation",
                    type_arguments=[],
                    function_arguments=[addr, account_to_revoke],
                )
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)

    async def place_tp_sl_order_for_position(
        self,
        *,
        market_addr: str,
        tp_trigger_price: int | float | None = None,
        tp_limit_price: int | float | None = None,
        tp_size: int | float | None = None,
        sl_trigger_price: int | float | None = None,
        sl_limit_price: int | float | None = None,
        sl_size: int | float | None = None,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
        tick_size: int | float | None = None,
    ) -> dict[str, Any]:
        final_tp_trigger = (
            _round_to_tick_size(tp_trigger_price, tick_size)
            if tp_trigger_price is not None and tick_size
            else tp_trigger_price
        )
        final_tp_limit = (
            _round_to_tick_size(tp_limit_price, tick_size)
            if tp_limit_price is not None and tick_size
            else tp_limit_price
        )
        final_sl_trigger = (
            _round_to_tick_size(sl_trigger_price, tick_size)
            if sl_trigger_price is not None and tick_size
            else sl_trigger_price
        )
        final_sl_limit = (
            _round_to_tick_size(sl_limit_price, tick_size)
            if sl_limit_price is not None and tick_size
            else sl_limit_price
        )

        pkg = self._config.deployment.package

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::place_tp_sl_order_for_position",
                    type_arguments=[],
                    function_arguments=[
                        addr,
                        market_addr,
                        final_tp_trigger,
                        final_tp_limit,
                        tp_size,
                        final_sl_trigger,
                        final_sl_limit,
                        sl_size,
                        None,
                        None,
                    ],
                ),
                account_override,
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)

    async def update_tp_order_for_position(
        self,
        *,
        market_addr: str,
        prev_order_id: int | str,
        tp_trigger_price: float | None = None,
        tp_limit_price: float | None = None,
        tp_size: float | None = None,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::update_tp_order_for_position",
                    type_arguments=[],
                    function_arguments=[
                        addr,
                        int(prev_order_id),
                        market_addr,
                        tp_trigger_price,
                        tp_limit_price,
                        tp_size,
                    ],
                ),
                account_override,
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)

    async def update_sl_order_for_position(
        self,
        *,
        market_addr: str,
        prev_order_id: int | str,
        sl_trigger_price: float | None = None,
        sl_limit_price: float | None = None,
        sl_size: float | None = None,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::update_sl_order_for_position",
                    type_arguments=[],
                    function_arguments=[
                        addr,
                        int(prev_order_id),
                        market_addr,
                        sl_trigger_price,
                        sl_limit_price,
                        sl_size,
                    ],
                ),
                account_override,
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)

    async def cancel_tp_sl_order_for_position(
        self,
        *,
        market_addr: str,
        order_id: int | str,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::cancel_tp_sl_order_for_position",
                    type_arguments=[],
                    function_arguments=[addr, market_addr, int(order_id)],
                ),
                account_override,
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)

    async def cancel_twap_order(
        self,
        *,
        market_addr: str,
        order_id: int | str,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::cancel_twap_orders_to_subaccount",
                    type_arguments=[],
                    function_arguments=[addr, market_addr, int(order_id)],
                ),
                account_override,
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)

    async def build_deactivate_subaccount_tx(
        self,
        *,
        subaccount_addr: str,
        revoke_all_delegations: bool = True,
        signer_address: AccountAddress,
    ) -> SimpleTransaction:
        pkg = self._config.deployment.package
        return await self.build_tx(
            InputEntryFunctionData(
                function=f"{pkg}::dex_accounts_entry::deactivate_subaccount",
                type_arguments=[],
                function_arguments=[subaccount_addr, revoke_all_delegations],
            ),
            signer_address,
        )

    async def deactivate_subaccount(
        self,
        *,
        subaccount_addr: str,
        revoke_all_delegations: bool = True,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::deactivate_subaccount",
                    type_arguments=[],
                    function_arguments=[addr, revoke_all_delegations],
                ),
                account_override,
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)

    async def build_create_vault_tx(
        self,
        args: CreateVaultArgs,
        signer_address: AccountAddress,
    ) -> SimpleTransaction:
        pkg = self._config.deployment.package
        return await self.build_tx(
            InputEntryFunctionData(
                function=f"{pkg}::vault_api::create_and_fund_vault",
                type_arguments=[],
                function_arguments=[
                    self.get_primary_subaccount_address(signer_address),
                    args.get("contribution_asset_type") or self.config.deployment.usdc,
                    args.get("vault_name"),
                    args.get("vault_description"),
                    args.get("vault_social_links"),
                    args.get("vault_share_symbol"),
                    args.get("vault_share_icon_uri", ""),
                    args.get("vault_share_project_uri", ""),
                    args.get("fee_bps"),
                    args.get("fee_interval_s"),
                    args.get("contribution_lockup_duration_s"),
                    args.get("initial_funding", 0),
                    args.get("accepts_contributions", False),
                    args.get("delegate_to_creator", False),
                ],
            ),
            signer_address,
        )

    async def create_vault(
        self,
        args: CreateVaultArgs,
        *,
        account_override: Account | None = None,
        subaccount_addr: str | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        async def _send(_: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::vault_api::create_and_fund_vault",
                    type_arguments=[],
                    function_arguments=[
                        subaccount_addr
                        or self.get_primary_subaccount_address(
                            (account_override or self._account).address()
                        ),
                        args.get("contribution_asset_type") or self._config.deployment.usdc,
                        args.get("vault_name"),
                        args.get("vault_description"),
                        args.get("vault_social_links"),
                        args.get("vault_share_symbol"),
                        args.get("vault_share_icon_uri", ""),
                        args.get("vault_share_project_uri", ""),
                        args.get("fee_bps"),
                        args.get("fee_interval_s"),
                        args.get("contribution_lockup_duration_s"),
                        args.get("initial_funding", 0),
                        args.get("accepts_contributions", False),
                        args.get("delegate_to_creator", False),
                    ],
                ),
                account_override,
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)

    async def build_activate_vault_tx(
        self,
        *,
        vault_address: str,
        signer_address: AccountAddress,
    ) -> SimpleTransaction:
        pkg = self._config.deployment.package
        return await self.build_tx(
            InputEntryFunctionData(
                function=f"{pkg}::vault_api::activate_vault",
                type_arguments=[],
                function_arguments=[vault_address],
            ),
            signer_address,
        )

    async def activate_vault(
        self,
        *,
        vault_address: str,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::vault_api::activate_vault",
                type_arguments=[],
                function_arguments=[vault_address],
            ),
            account_override,
        )

    async def build_deposit_to_vault_tx(
        self,
        *,
        vault_address: str,
        amount: float,
        signer_address: AccountAddress,
    ) -> SimpleTransaction:
        pkg = self._config.deployment.package
        return await self.build_tx(
            InputEntryFunctionData(
                function=f"{pkg}::dex_accounts_entry::contribute_to_vault",
                type_arguments=[],
                function_arguments=[
                    self.get_primary_subaccount_address(signer_address),
                    vault_address,
                    self._config.deployment.usdc,
                    amount,
                ],
            ),
            signer_address,
        )

    async def deposit_to_vault(
        self,
        *,
        vault_address: str,
        amount: float,
        subaccount_addr: str,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        usdc = self._config.deployment.usdc

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::contribute_to_vault",
                    type_arguments=[],
                    function_arguments=[addr, vault_address, usdc, amount],
                )
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)

    async def build_withdraw_from_vault_tx(
        self,
        *,
        vault_address: str,
        shares: float,
        signer_address: AccountAddress,
    ) -> SimpleTransaction:
        pkg = self._config.deployment.package
        return await self.build_tx(
            InputEntryFunctionData(
                function=f"{pkg}::vault_api::redeem",
                type_arguments=[],
                function_arguments=[vault_address, shares],
            ),
            signer_address,
        )

    async def withdraw_from_vault(
        self,
        *,
        vault_address: str,
        shares: float,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::redeem_from_vault",
                    type_arguments=[],
                    function_arguments=[addr, vault_address, shares],
                ),
                account_override,
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)

    async def build_delegate_dex_actions_to_tx(
        self,
        *,
        vault_address: str,
        account_to_delegate_to: str,
        signer_address: AccountAddress,
        expiration_timestamp_secs: int | None = None,
    ) -> SimpleTransaction:
        pkg = self._config.deployment.package
        return await self.build_tx(
            InputEntryFunctionData(
                function=f"{pkg}::vault_admin_api::delegate_dex_actions_to",
                type_arguments=[],
                function_arguments=[
                    vault_address,
                    account_to_delegate_to,
                    expiration_timestamp_secs,
                ],
            ),
            signer_address,
        )

    async def delegate_vault_actions(
        self,
        *,
        vault_address: str,
        account_to_delegate_to: str,
        expiration_timestamp_secs: int | None = None,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::vault_admin_api::delegate_dex_actions_to",
                type_arguments=[],
                function_arguments=[
                    vault_address,
                    account_to_delegate_to,
                    expiration_timestamp_secs,
                ],
            ),
            account_override,
        )

    async def approve_max_builder_fee(
        self,
        *,
        builder_addr: str,
        max_fee: int,
        subaccount_addr: str | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::approve_max_builder_fee_for_subaccount",
                    type_arguments=[],
                    function_arguments=[addr, builder_addr, max_fee],
                )
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)

    async def revoke_max_builder_fee(
        self,
        *,
        builder_addr: str,
        subaccount_addr: str | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        async def _send(addr: str) -> dict[str, Any]:
            return await self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::revoke_max_builder_fee_for_subaccount",
                    type_arguments=[],
                    function_arguments=[addr, builder_addr],
                )
            )

        return await self.send_subaccount_tx(_send, subaccount_addr)


class DecibelWriteDexSync(BaseSDKSync):
    def __init__(
        self,
        config: DecibelConfig,
        account: Account,
        opts: BaseSDKOptionsSync | None = None,
    ) -> None:
        super().__init__(config, account, opts)
        self._order_status_client = OrderStatusClient(config)

    @property
    def order_status_client(self) -> OrderStatusClient:
        return self._order_status_client

    def _extract_order_id_from_transaction(
        self,
        tx_response: dict[str, Any],
        subaccount_addr: str | None = None,
    ) -> str | None:
        order_event_types = [
            "market_types::OrderEvent",
            "async_matching_engine::TwapEvent",
        ]
        try:
            events: list[dict[str, Any]] | None = tx_response.get("events")
            if events is None:
                return None
            for event in events:
                event_type = str(event.get("type", ""))
                for oe_type in order_event_types:
                    if oe_type in event_type:
                        event_data: dict[str, Any] | None = event.get("data")
                        if event_data is None:
                            continue
                        user_address = subaccount_addr or str(self._account.address())
                        order_user_address = event_data.get("user")
                        twap_user_address = event_data.get("account")
                        if order_user_address == user_address or twap_user_address == user_address:
                            order_id = event_data.get("order_id")
                            if isinstance(order_id, str):
                                return order_id
                            if isinstance(order_id, dict):
                                oid = cast("dict[str, Any]", order_id).get("order_id")
                                return str(oid) if oid is not None else None
            return None
        except Exception as e:
            logger.error("Error extracting order_id from transaction: %s", e)
            return None

    def send_subaccount_tx(
        self,
        send_tx: Callable[[str], dict[str, Any]],
        subaccount_addr: str | None = None,
    ) -> dict[str, Any]:
        if subaccount_addr is None:
            subaccount_addr = get_primary_subaccount_addr(
                self._account.address(),
                self._config.compat_version,
                self._config.deployment.package,
            )
        return send_tx(subaccount_addr)

    def with_subaccount(
        self,
        fn: Callable[[str], T],
        subaccount_addr: str | None = None,
    ) -> T:
        if subaccount_addr is None:
            subaccount_addr = get_primary_subaccount_addr(
                self._account.address(),
                self._config.compat_version,
                self._config.deployment.package,
            )
        return fn(subaccount_addr)

    def rename_subaccount(self, args: RenameSubaccountArgs) -> tuple[RenameSubaccount, int, str]:
        url = f"{self._config.trading_http_url}/api/v1/subaccounts/{args.subaccount_address}"
        return post_request_sync(
            RenameSubaccount,
            url,
            body={"name": args.new_name},
            api_key=self._node_api_key,
        )

    def create_subaccount(self) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::dex_accounts_entry::create_new_subaccount",
                type_arguments=[],
                function_arguments=[],
            )
        )

    def deposit(self, amount: int, subaccount_addr: str | None = None) -> dict[str, Any]:
        pkg = self._config.deployment.package
        usdc = self._config.deployment.usdc

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::deposit_to_subaccount_at",
                    type_arguments=[],
                    function_arguments=[addr, usdc, amount],
                )
            )

        return self.send_subaccount_tx(_send, subaccount_addr)

    def withdraw(self, amount: int, subaccount_addr: str | None = None) -> dict[str, Any]:
        pkg = self._config.deployment.package
        usdc = self._config.deployment.usdc

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::withdraw_from_subaccount",
                    type_arguments=[],
                    function_arguments=[addr, usdc, amount],
                )
            )

        return self.send_subaccount_tx(_send, subaccount_addr)

    def configure_user_settings_for_market(
        self,
        *,
        market_addr: str,
        subaccount_addr: str,
        is_cross: bool,
        user_leverage: int,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::configure_user_settings_for_market",
                    type_arguments=[],
                    function_arguments=[addr, market_addr, is_cross, user_leverage],
                )
            )

        return self.send_subaccount_tx(_send, subaccount_addr)

    def place_order(
        self,
        *,
        market_name: str,
        price: int | float,
        size: int | float,
        is_buy: bool,
        time_in_force: TimeInForce,
        is_reduce_only: bool,
        client_order_id: str | None = None,
        stop_price: int | float | None = None,
        tp_trigger_price: int | float | None = None,
        tp_limit_price: int | float | None = None,
        sl_trigger_price: int | float | None = None,
        sl_limit_price: int | float | None = None,
        builder_addr: str | None = None,
        builder_fee: float | None = None,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
        tick_size: int | float | None = None,
    ) -> PlaceOrderResult:
        try:
            market_addr = get_market_addr(market_name, self._config.deployment.perp_engine_global)

            final_price = _round_to_tick_size(price, tick_size) if tick_size else price
            final_stop_price = (
                _round_to_tick_size(stop_price, tick_size)
                if stop_price is not None and tick_size
                else stop_price
            )
            final_tp_trigger = (
                _round_to_tick_size(tp_trigger_price, tick_size)
                if tp_trigger_price is not None and tick_size
                else tp_trigger_price
            )
            final_tp_limit = (
                _round_to_tick_size(tp_limit_price, tick_size)
                if tp_limit_price is not None and tick_size
                else tp_limit_price
            )
            final_sl_trigger = (
                _round_to_tick_size(sl_trigger_price, tick_size)
                if sl_trigger_price is not None and tick_size
                else sl_trigger_price
            )
            final_sl_limit = (
                _round_to_tick_size(sl_limit_price, tick_size)
                if sl_limit_price is not None and tick_size
                else sl_limit_price
            )

            pkg = self._config.deployment.package

            def _send(addr: str) -> dict[str, Any]:
                return self._send_tx(
                    InputEntryFunctionData(
                        function=f"{pkg}::dex_accounts_entry::place_order_to_subaccount",
                        type_arguments=[],
                        function_arguments=[
                            addr,
                            market_addr,
                            final_price,
                            size,
                            is_buy,
                            time_in_force,
                            is_reduce_only,
                            client_order_id,
                            final_stop_price,
                            final_tp_trigger,
                            final_tp_limit,
                            final_sl_trigger,
                            final_sl_limit,
                            builder_addr,
                            builder_fee,
                        ],
                    ),
                    account_override,
                )

            tx_response = self.send_subaccount_tx(_send, subaccount_addr)

            order_id = self._extract_order_id_from_transaction(tx_response, subaccount_addr)

            return PlaceOrderSuccess(
                success=True,
                orderId=order_id,
                transactionHash=tx_response.get("hash", ""),
            )
        except Exception as e:
            logger.error("Error placing order: %s", e)
            return PlaceOrderFailure(
                success=False,
                error=str(e),
            )

    def trigger_matching(
        self,
        *,
        market_addr: str,
        max_work_unit: int,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        tx_response = self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::public_apis::process_perp_market_pending_requests",
                type_arguments=[],
                function_arguments=[market_addr, max_work_unit],
            )
        )
        return {
            "success": True,
            "transactionHash": tx_response.get("hash", ""),
        }

    def place_twap_order(
        self,
        *,
        market_name: str,
        size: int | float,
        is_buy: bool,
        is_reduce_only: bool,
        twap_frequency_seconds: int,
        twap_duration_seconds: int,
        client_order_id: str | None = None,
        builder_address: str | None = None,
        builder_fees: float | None = None,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> PlaceOrderResult:
        market_addr = get_market_addr(market_name, self._config.deployment.perp_engine_global)
        pkg = self._config.deployment.package

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::place_twap_order_to_subaccount_v2",
                    type_arguments=[],
                    function_arguments=[
                        addr,
                        market_addr,
                        size,
                        is_buy,
                        is_reduce_only,
                        client_order_id,
                        twap_frequency_seconds,
                        twap_duration_seconds,
                        builder_address,
                        builder_fees,
                    ],
                ),
                account_override,
            )

        tx_response = self.send_subaccount_tx(_send, subaccount_addr)

        order_id = self._extract_order_id_from_transaction(tx_response, subaccount_addr)

        return PlaceOrderSuccess(
            success=True,
            orderId=order_id,
            transactionHash=tx_response.get("hash", ""),
        )

    def cancel_order(
        self,
        *,
        order_id: int | str,
        market_name: str | None = None,
        market_addr: str | None = None,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        if market_name is not None:
            resolved_market_addr = get_market_addr(
                market_name, self._config.deployment.perp_engine_global
            )
        elif market_addr is not None:
            resolved_market_addr = market_addr
        else:
            raise ValueError("Either market_name or market_addr must be provided")

        pkg = self._config.deployment.package

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::cancel_order_to_subaccount",
                    type_arguments=[],
                    function_arguments=[addr, int(order_id), resolved_market_addr],
                ),
                account_override,
            )

        return self.send_subaccount_tx(_send, subaccount_addr)

    def place_bulk_orders(
        self,
        *,
        market_name: str,
        sequence_number: int,
        bid_prices: list[int],
        bid_sizes: list[int],
        ask_prices: list[int],
        ask_sizes: list[int],
        builder_addr: str | None = None,
        builder_fee: int | None = None,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> PlaceBulkOrdersResult:
        try:
            market_addr = get_market_addr(market_name, self._config.deployment.perp_engine_global)
            pkg = self._config.deployment.package

            def _send(addr: str) -> dict[str, Any]:
                return self._send_tx(
                    InputEntryFunctionData(
                        function=f"{pkg}::dex_accounts_entry::place_bulk_orders_to_subaccount",
                        type_arguments=[],
                        function_arguments=[
                            addr,
                            market_addr,
                            sequence_number,
                            bid_prices,
                            bid_sizes,
                            ask_prices,
                            ask_sizes,
                            builder_addr,
                            builder_fee,
                        ],
                    ),
                    account_override,
                )

            tx_response = self.send_subaccount_tx(_send, subaccount_addr)

            return PlaceBulkOrdersSuccess(
                transactionHash=tx_response.get("hash", ""),
            )
        except Exception as e:
            logger.error("Error placing bulk orders: %s", e)
            return PlaceBulkOrdersFailure(error=str(e))

    def cancel_bulk_order(
        self,
        *,
        market_name: str,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        market_addr = get_market_addr(market_name, self._config.deployment.perp_engine_global)
        pkg = self._config.deployment.package

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::cancel_bulk_order_to_subaccount",
                    type_arguments=[],
                    function_arguments=[addr, market_addr],
                ),
                account_override,
            )

        return self.send_subaccount_tx(_send, subaccount_addr)

    def cancel_client_order(
        self,
        *,
        client_order_id: str,
        market_name: str,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        market_addr = get_market_addr(market_name, self._config.deployment.perp_engine_global)
        pkg = self._config.deployment.package

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::cancel_client_order_to_subaccount",
                    type_arguments=[],
                    function_arguments=[addr, client_order_id, market_addr],
                ),
                account_override,
            )

        return self.send_subaccount_tx(_send, subaccount_addr)

    def delegate_trading_to_for_subaccount(
        self,
        *,
        subaccount_addr: str,
        account_to_delegate_to: str,
        expiration_timestamp_secs: int | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::delegate_trading_to_for_subaccount",
                    type_arguments=[],
                    function_arguments=[
                        addr,
                        account_to_delegate_to,
                        expiration_timestamp_secs,
                    ],
                )
            )

        return self.send_subaccount_tx(_send, subaccount_addr)

    def revoke_delegation(
        self,
        *,
        account_to_revoke: str,
        subaccount_addr: str | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::revoke_delegation",
                    type_arguments=[],
                    function_arguments=[addr, account_to_revoke],
                )
            )

        return self.send_subaccount_tx(_send, subaccount_addr)

    def place_tp_sl_order_for_position(
        self,
        *,
        market_addr: str,
        tp_trigger_price: int | float | None = None,
        tp_limit_price: int | float | None = None,
        tp_size: int | float | None = None,
        sl_trigger_price: int | float | None = None,
        sl_limit_price: int | float | None = None,
        sl_size: int | float | None = None,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
        tick_size: int | float | None = None,
    ) -> dict[str, Any]:
        final_tp_trigger = (
            _round_to_tick_size(tp_trigger_price, tick_size)
            if tp_trigger_price is not None and tick_size
            else tp_trigger_price
        )
        final_tp_limit = (
            _round_to_tick_size(tp_limit_price, tick_size)
            if tp_limit_price is not None and tick_size
            else tp_limit_price
        )
        final_sl_trigger = (
            _round_to_tick_size(sl_trigger_price, tick_size)
            if sl_trigger_price is not None and tick_size
            else sl_trigger_price
        )
        final_sl_limit = (
            _round_to_tick_size(sl_limit_price, tick_size)
            if sl_limit_price is not None and tick_size
            else sl_limit_price
        )

        pkg = self._config.deployment.package

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::place_tp_sl_order_for_position",
                    type_arguments=[],
                    function_arguments=[
                        addr,
                        market_addr,
                        final_tp_trigger,
                        final_tp_limit,
                        tp_size,
                        final_sl_trigger,
                        final_sl_limit,
                        sl_size,
                        None,
                        None,
                    ],
                ),
                account_override,
            )

        return self.send_subaccount_tx(_send, subaccount_addr)

    def update_tp_order_for_position(
        self,
        *,
        market_addr: str,
        prev_order_id: int | str,
        tp_trigger_price: float | None = None,
        tp_limit_price: float | None = None,
        tp_size: float | None = None,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::update_tp_order_for_position",
                    type_arguments=[],
                    function_arguments=[
                        addr,
                        int(prev_order_id),
                        market_addr,
                        tp_trigger_price,
                        tp_limit_price,
                        tp_size,
                    ],
                ),
                account_override,
            )

        return self.send_subaccount_tx(_send, subaccount_addr)

    def update_sl_order_for_position(
        self,
        *,
        market_addr: str,
        prev_order_id: int | str,
        sl_trigger_price: float | None = None,
        sl_limit_price: float | None = None,
        sl_size: float | None = None,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::update_sl_order_for_position",
                    type_arguments=[],
                    function_arguments=[
                        addr,
                        int(prev_order_id),
                        market_addr,
                        sl_trigger_price,
                        sl_limit_price,
                        sl_size,
                    ],
                ),
                account_override,
            )

        return self.send_subaccount_tx(_send, subaccount_addr)

    def cancel_tp_sl_order_for_position(
        self,
        *,
        market_addr: str,
        order_id: int | str,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::cancel_tp_sl_order_for_position",
                    type_arguments=[],
                    function_arguments=[addr, market_addr, int(order_id)],
                ),
                account_override,
            )

        return self.send_subaccount_tx(_send, subaccount_addr)

    def cancel_twap_order(
        self,
        *,
        order_id: str,
        market_addr: str,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::cancel_twap_orders_to_subaccount",
                    type_arguments=[],
                    function_arguments=[addr, market_addr, order_id],
                ),
                account_override,
            )

        return self.send_subaccount_tx(_send, subaccount_addr)

    def build_deactivate_subaccount_tx(
        self,
        *,
        subaccount_addr: str,
        revoke_all_delegations: bool = True,
        signer_address: AccountAddress,
    ) -> SimpleTransaction:
        pkg = self._config.deployment.package
        return self.build_tx(
            InputEntryFunctionData(
                function=f"{pkg}::dex_accounts_entry::deactivate_subaccount",
                type_arguments=[],
                function_arguments=[subaccount_addr, revoke_all_delegations],
            ),
            signer_address,
        )

    def deactivate_subaccount(
        self,
        *,
        subaccount_addr: str,
        revoke_all_delegations: bool = True,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::deactivate_subaccount",
                    type_arguments=[],
                    function_arguments=[addr, revoke_all_delegations],
                ),
                account_override,
            )

        return self.send_subaccount_tx(_send, subaccount_addr)

    def build_create_vault_tx(
        self,
        args: CreateVaultArgs,
        signer_address: AccountAddress,
    ) -> SimpleTransaction:
        pkg = self._config.deployment.package
        return self.build_tx(
            InputEntryFunctionData(
                function=f"{pkg}::vault_api::create_and_fund_vault",
                type_arguments=[],
                function_arguments=[
                    self.get_primary_subaccount_address(signer_address),
                    args.get("contribution_asset_type"),
                    args.get("vault_name"),
                    args.get("vault_description"),
                    args.get("vault_social_links"),
                    args.get("vault_share_symbol"),
                    args.get("vault_share_icon_uri", ""),
                    args.get("vault_share_project_uri", ""),
                    args.get("fee_bps"),
                    args.get("fee_interval_s"),
                    args.get("contribution_lockup_duration_s"),
                    args.get("initial_funding", 0),
                    args.get("accepts_contributions", False),
                    args.get("delegate_to_creator", False),
                ],
            ),
            signer_address,
        )

    def create_vault(
        self,
        args: CreateVaultArgs,
        *,
        account_override: Account | None = None,
        subaccount_addr: str | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        def _send(_: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::vault_api::create_and_fund_vault",
                    type_arguments=[],
                    function_arguments=[
                        subaccount_addr
                        or self.get_primary_subaccount_address(
                            (account_override or self._account).address()
                        ),
                        args.get("contribution_asset_type"),
                        args.get("vault_name"),
                        args.get("vault_description"),
                        args.get("vault_social_links"),
                        args.get("vault_share_symbol"),
                        args.get("vault_share_icon_uri", ""),
                        args.get("vault_share_project_uri", ""),
                        args.get("fee_bps"),
                        args.get("fee_interval_s"),
                        args.get("contribution_lockup_duration_s"),
                        args.get("initial_funding", 0),
                        args.get("accepts_contributions", False),
                        args.get("delegate_to_creator", False),
                    ],
                ),
                account_override,
            )

        return self.send_subaccount_tx(_send, subaccount_addr)

    def build_activate_vault_tx(
        self,
        *,
        vault_address: str,
        signer_address: AccountAddress,
    ) -> SimpleTransaction:
        pkg = self._config.deployment.package
        return self.build_tx(
            InputEntryFunctionData(
                function=f"{pkg}::vault_api::activate_vault",
                type_arguments=[],
                function_arguments=[vault_address],
            ),
            signer_address,
        )

    def activate_vault(
        self,
        *,
        vault_address: str,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::vault_api::activate_vault",
                type_arguments=[],
                function_arguments=[vault_address],
            ),
            account_override,
        )

    def build_deposit_to_vault_tx(
        self,
        *,
        vault_address: str,
        amount: float,
        signer_address: AccountAddress,
    ) -> SimpleTransaction:
        pkg = self._config.deployment.package
        return self.build_tx(
            InputEntryFunctionData(
                function=f"{pkg}::dex_accounts_entry::contribute_to_vault",
                type_arguments=[],
                function_arguments=[
                    self.get_primary_subaccount_address(signer_address),
                    vault_address,
                    self._config.deployment.usdc,
                    amount,
                ],
            ),
            signer_address,
        )

    def deposit_to_vault(
        self,
        *,
        vault_address: str,
        amount: float,
        subaccount_addr: str,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        usdc = self._config.deployment.usdc

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::contribute_to_vault",
                    type_arguments=[],
                    function_arguments=[addr, vault_address, usdc, amount],
                )
            )

        return self.send_subaccount_tx(_send, subaccount_addr)

    def build_withdraw_from_vault_tx(
        self,
        *,
        vault_address: str,
        shares: float,
        signer_address: AccountAddress,
    ) -> SimpleTransaction:
        pkg = self._config.deployment.package
        return self.build_tx(
            InputEntryFunctionData(
                function=f"{pkg}::vault_api::redeem",
                type_arguments=[],
                function_arguments=[vault_address, shares],
            ),
            signer_address,
        )

    def withdraw_from_vault(
        self,
        *,
        vault_address: str,
        shares: float,
        subaccount_addr: str | None = None,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::redeem_from_vault",
                    type_arguments=[],
                    function_arguments=[addr, vault_address, shares],
                ),
                account_override,
            )

        return self.send_subaccount_tx(_send, subaccount_addr)

    def build_delegate_dex_actions_to_tx(
        self,
        *,
        vault_address: str,
        account_to_delegate_to: str,
        signer_address: AccountAddress,
        expiration_timestamp_secs: int | None = None,
    ) -> SimpleTransaction:
        pkg = self._config.deployment.package
        return self.build_tx(
            InputEntryFunctionData(
                function=f"{pkg}::vault_admin_api::delegate_dex_actions_to",
                type_arguments=[],
                function_arguments=[
                    vault_address,
                    account_to_delegate_to,
                    expiration_timestamp_secs,
                ],
            ),
            signer_address,
        )

    def delegate_vault_actions(
        self,
        *,
        vault_address: str,
        account_to_delegate_to: str,
        expiration_timestamp_secs: int | None = None,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::vault_admin_api::delegate_dex_actions_to",
                type_arguments=[],
                function_arguments=[
                    vault_address,
                    account_to_delegate_to,
                    expiration_timestamp_secs,
                ],
            ),
            account_override,
        )

    def approve_max_builder_fee(
        self,
        *,
        builder_addr: str,
        max_fee: int,
        subaccount_addr: str | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::approve_max_builder_fee_for_subaccount",
                    type_arguments=[],
                    function_arguments=[addr, builder_addr, max_fee],
                )
            )

        return self.send_subaccount_tx(_send, subaccount_addr)

    def revoke_max_builder_fee(
        self,
        *,
        builder_addr: str,
        subaccount_addr: str | None = None,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package

        def _send(addr: str) -> dict[str, Any]:
            return self._send_tx(
                InputEntryFunctionData(
                    function=f"{pkg}::dex_accounts_entry::revoke_max_builder_fee_for_subaccount",
                    type_arguments=[],
                    function_arguments=[addr, builder_addr],
                )
            )

        return self.send_subaccount_tx(_send, subaccount_addr)
