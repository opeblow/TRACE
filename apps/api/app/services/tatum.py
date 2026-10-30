"""Tatum Sui gRPC adapter.

Sui JSON-RPC has been retired on Tatum's gateway (it returns HTTP 404 for valid
keys), so TRACE reads Mainnet data through Tatum's sui.rpc.v2 gRPC interface.

The schema is vendored in sui_rpc_v2.binpb (see scripts/refresh_sui_descriptors.py)
and messages are built dynamically from it. This module is the only place that
knows the provider's wire format; it returns plain, validated Python values.
"""
from __future__ import annotations

import asyncio
import random
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable

import grpc
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

from app.core.config import settings

SOURCE = "tatum_sui_grpc"
SUI_COIN_TYPE = "0x2::sui::SUI"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
CALL_TIMEOUT_SECONDS = 12.0
MAX_ATTEMPTS = 3
RETRYABLE_CODES = {grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.RESOURCE_EXHAUSTED, grpc.StatusCode.DEADLINE_EXCEEDED}
TRANSACTION_READ_MASK = [
    "digest",
    "timestamp",
    "checkpoint",
    "effects.status",
    "balance_changes",
    "transaction.sender",
]
_DESCRIPTOR_FILE = Path(__file__).with_name("sui_rpc_v2.binpb")


class TatumProviderError(RuntimeError):
    """Provider errors intentionally contain no credentials or response payloads."""


def _load_pool() -> descriptor_pool.DescriptorPool:
    file_set = descriptor_pb2.FileDescriptorSet.FromString(_DESCRIPTOR_FILE.read_bytes())
    pool = descriptor_pool.DescriptorPool()
    for proto in file_set.file:
        pool.Add(proto)
    return pool


_POOL = _load_pool()


def message_class(name: str):
    return message_factory.GetMessageClass(_POOL.FindMessageTypeByName(f"sui.rpc.v2.{name}"))


def canonical_coin_type(coin_type: str) -> str:
    """Shorten the address part so 0x000…02::sui::SUI and 0x2::sui::SUI compare equal."""
    address, sep, rest = coin_type.partition("::")
    if not sep or not address.lower().startswith("0x"):
        return coin_type
    short = address[2:].lstrip("0").lower() or "0"
    return f"0x{short}::{rest}"


@dataclass(frozen=True)
class ChainInfo:
    chain: str | None
    chain_id: str | None
    checkpoint_height: int | None


@dataclass(frozen=True)
class BalanceChange:
    address: str
    coin_type: str
    amount: str  # signed integer string in the coin's base unit (MIST for SUI)


@dataclass(frozen=True)
class TransactionRecord:
    digest: str
    timestamp_ms: int | None
    checkpoint: int | None
    status: str | None  # "success", "failure", or None when not reported
    sender: str | None
    balance_changes: list[BalanceChange] = field(default_factory=list)


@dataclass(frozen=True)
class WalletFetch:
    chain: ChainInfo
    sui_balance_mist: str | None
    transactions: list[TransactionRecord]
    has_more: bool


def _optional(message, name: str):
    return getattr(message, name) if message.HasField(name) else None


def parse_transaction(executed) -> TransactionRecord | None:
    """Convert an ExecutedTransaction message; returns None if it has no digest."""
    digest = _optional(executed, "digest")
    if not digest:
        return None
    timestamp_ms = None
    if executed.HasField("timestamp"):
        timestamp_ms = executed.timestamp.seconds * 1000 + executed.timestamp.nanos // 1_000_000
    status = None
    if executed.HasField("effects") and executed.effects.HasField("status") and executed.effects.status.HasField("success"):
        status = "success" if executed.effects.status.success else "failure"
    sender = None
    if executed.HasField("transaction") and executed.transaction.HasField("sender"):
        sender = executed.transaction.sender
    changes = []
    for change in executed.balance_changes:
        if not (change.HasField("address") and change.HasField("coin_type") and change.HasField("amount")):
            continue
        changes.append(BalanceChange(address=change.address, coin_type=change.coin_type, amount=change.amount))
    return TransactionRecord(
        digest=digest,
        timestamp_ms=timestamp_ms,
        checkpoint=_optional(executed, "checkpoint"),
        status=status,
        sender=sender,
        balance_changes=changes,
    )


ChannelFactory = Callable[[], Any]


class TatumService:
    def __init__(self, api_key: str | None = None, target: str | None = None, channel_factory: ChannelFactory | None = None, retry_base_seconds: float = 0.4):
        self.api_key = settings.TATUM_MAINNET_API_KEY if api_key is None else api_key
        self.target = settings.TATUM_GRPC_TARGET if target is None else target
        self._channel_factory = channel_factory
        self._retry_base_seconds = retry_base_seconds

    @asynccontextmanager
    async def _channel(self) -> AsyncIterator[Any]:
        if self._channel_factory is not None:
            yield self._channel_factory()
            return
        channel = grpc.aio.secure_channel(
            self.target,
            grpc.ssl_channel_credentials(),
            options=[("grpc.max_receive_message_length", MAX_RESPONSE_BYTES)],
        )
        try:
            yield channel
        finally:
            await channel.close()

    @property
    def _metadata(self):
        return (("x-api-key", self.api_key),)

    async def _with_retry(self, operation):
        for attempt in range(MAX_ATTEMPTS):
            try:
                return await operation()
            except grpc.RpcError as exc:
                code = exc.code() if callable(getattr(exc, "code", None)) else None
                if code not in RETRYABLE_CODES or attempt == MAX_ATTEMPTS - 1:
                    raise TatumProviderError(f"Tatum request failed ({code.name if code else 'unknown'})") from None
                delay = self._retry_base_seconds * (2 ** attempt)
                await asyncio.sleep(delay + random.uniform(0, delay))
        raise TatumProviderError("Tatum request failed")  # pragma: no cover

    async def _unary(self, channel, service: str, method: str, request, response_name: str):
        call = channel.unary_unary(
            f"/sui.rpc.v2.{service}/{method}",
            request_serializer=lambda message: message.SerializeToString(),
            response_deserializer=message_class(response_name).FromString,
        )
        return await self._with_retry(lambda: call(request, metadata=self._metadata, timeout=CALL_TIMEOUT_SECONDS))

    async def _chain_info(self, channel) -> ChainInfo:
        info = await self._unary(channel, "LedgerService", "GetServiceInfo", message_class("GetServiceInfoRequest")(), "GetServiceInfoResponse")
        return ChainInfo(
            chain=_optional(info, "chain"),
            chain_id=_optional(info, "chain_id"),
            checkpoint_height=_optional(info, "checkpoint_height"),
        )

    async def _sui_balance(self, channel, address: str) -> str | None:
        request = message_class("GetBalanceRequest")(owner=address, coin_type=SUI_COIN_TYPE)
        response = await self._unary(channel, "StateService", "GetBalance", request, "GetBalanceResponse")
        if not response.HasField("balance"):
            return None
        balance = response.balance
        return str(balance.balance) if balance.HasField("balance") else None

    async def _transactions(self, channel, address: str, limit: int) -> tuple[list[TransactionRecord], bool]:
        request = message_class("ListTransactionsRequest")()
        literal = request.filter.terms.add().literals.add()
        literal.affected_address.address = address
        request.read_mask.paths.extend(TRANSACTION_READ_MASK)
        request.options.limit = limit
        request.options.ordering = 1  # ORDERING_DESCENDING: most recent first
        call = channel.unary_stream(
            "/sui.rpc.v2.LedgerService/ListTransactions",
            request_serializer=lambda message: message.SerializeToString(),
            response_deserializer=message_class("ListTransactionsResponse").FromString,
        )

        async def run():
            records: list[TransactionRecord] = []
            end_reason = None
            async for item in call(request, metadata=self._metadata, timeout=CALL_TIMEOUT_SECONDS):
                if item.HasField("transaction"):
                    record = parse_transaction(item.transaction)
                    if record is not None:
                        records.append(record)
                    if len(records) > limit:
                        break
                if item.HasField("end") and item.end.HasField("reason"):
                    end_reason = item.end.reason
            return records, end_reason

        records, end_reason = await self._with_retry(run)
        # ITEM_LIMIT (1) or SCAN_LIMIT (2) means the provider stopped before the
        # start of history. Treat an unreported reason at the limit as "more may exist".
        has_more = end_reason in (1, 2) or (end_reason is None and len(records) >= limit)
        return records[:limit], has_more

    async def fetch_wallet(self, address: str, limit: int = 50) -> WalletFetch:
        if not self.api_key:
            raise TatumProviderError("Tatum API key is not configured")
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        async with self._channel() as channel:
            chain, balance, (transactions, has_more) = await asyncio.gather(
                self._chain_info(channel),
                self._sui_balance(channel, address),
                self._transactions(channel, address, limit),
            )
        return WalletFetch(chain=chain, sui_balance_mist=balance, transactions=transactions, has_more=has_more)


tatum_service = TatumService()
