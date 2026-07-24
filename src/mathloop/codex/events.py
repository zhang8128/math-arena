"""Bounded state machine that reduces Codex CLI `--json` JSONL events into a transcript."""

import hashlib
import json
from dataclasses import dataclass

from mathloop.codex.domain import CodexUsage

_USAGE_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)
_TERMINAL_TYPES = frozenset({"turn.completed", "turn.failed", "error"})


class CodexEventError(RuntimeError):
    """The Codex JSONL event stream violated the bounded parser contract."""


@dataclass(frozen=True)
class CodexEvent:
    """One accepted line from the Codex CLI `--json` event stream."""

    sequence: int
    event_type: str
    payload: dict[str, object]
    raw_sha256: str


@dataclass(frozen=True)
class CodexTranscript:
    """The reduced outcome of a single Codex turn's event stream."""

    thread_id: str
    dispatched: bool
    terminal_type: str
    final_message: str | None
    usage: CodexUsage | None
    events: tuple[CodexEvent, ...]


class CodexEventParser:
    """Reduces one Codex CLI `--json` JSONL stream into a `CodexTranscript`.

    The parser is a strict, forward-only state machine: it never infers
    missing data (token counts, a successful terminal state, ...) and it
    never lets a `turn.failed` or `error` terminal masquerade as success.
    A `turn.started` event durably marks the turn as dispatched even if the
    stream goes on to fail, which is why `dispatched` is exposed directly on
    the parser rather than only on the finished transcript.
    """

    def __init__(self, *, max_bytes: int) -> None:
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("max_bytes must be a positive integer")
        self._max_bytes = max_bytes
        self._bytes_seen = 0
        self._events: list[CodexEvent] = []
        self._thread_id: str | None = None
        self._turn_started = False
        self._terminal_type: str | None = None
        self._final_message: str | None = None
        self._usage: CodexUsage | None = None

    @property
    def dispatched(self) -> bool:
        return self._turn_started

    def feed(self, line: bytes) -> CodexEvent:
        # Count raw bytes before decoding so an oversize or garbage line is
        # rejected by the byte cap without ever being parsed as JSON.
        self._bytes_seen += len(line)
        if self._bytes_seen > self._max_bytes:
            raise CodexEventError(f"event stream exceeded max_bytes cap of {self._max_bytes}")
        payload = self._decode(line)
        event_type = payload.get("type")
        if type(event_type) is not str or not event_type:
            raise CodexEventError("event is missing a non-empty string 'type' field")
        self._apply(event_type, payload)
        event = CodexEvent(
            sequence=len(self._events),
            event_type=event_type,
            payload=payload,
            raw_sha256=hashlib.sha256(line).hexdigest(),
        )
        self._events.append(event)
        return event

    def finish(self) -> CodexTranscript:
        if self._thread_id is None:
            raise CodexEventError("event stream never produced a thread.started event")
        if not self._turn_started:
            raise CodexEventError("event stream never produced a turn.started event")
        if self._terminal_type is None:
            raise CodexEventError("event stream never produced a terminal event")
        # A turn.failed or error terminal must still produce a transcript, as
        # the ledger settles it as evidence -- but it never carries a final
        # agent message, regardless of what preceded the failure.
        final_message = self._final_message if self._terminal_type == "turn.completed" else None
        return CodexTranscript(
            thread_id=self._thread_id,
            dispatched=self._turn_started,
            terminal_type=self._terminal_type,
            final_message=final_message,
            usage=self._usage,
            events=tuple(self._events),
        )

    def _decode(self, line: bytes) -> dict[str, object]:
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError as error:
            raise CodexEventError(f"event line is not valid UTF-8: {error}") from error
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise CodexEventError(f"event line is not valid JSON: {error}") from error
        if not isinstance(payload, dict):
            raise CodexEventError("event line must decode to a single JSON object")
        return payload

    def _apply(self, event_type: str, payload: dict[str, object]) -> None:
        if event_type == "thread.started":
            self._apply_thread_started(payload)
        elif event_type == "turn.started":
            self._apply_turn_started()
        elif event_type == "item.completed":
            self._apply_item_completed(payload)
        elif event_type.startswith("item."):
            # Other documented item.* events (item.started, item.updated, ...)
            # carry no lifecycle-relevant state beyond terminal exclusion.
            self._require_not_terminal(event_type)
        elif event_type in _TERMINAL_TYPES:
            self._apply_terminal(event_type, payload)
        # Unknown event types are preserved as evidence by the caller but
        # never mutate lifecycle state, so no branch touches state here.

    def _require_not_terminal(self, event_type: str) -> None:
        if self._terminal_type is not None:
            raise CodexEventError(
                f"received {event_type!r} after terminal event {self._terminal_type!r}"
            )

    def _apply_thread_started(self, payload: dict[str, object]) -> None:
        self._require_not_terminal("thread.started")
        if self._thread_id is not None:
            raise CodexEventError("received a second thread.started event")
        thread_id = payload.get("thread_id")
        if type(thread_id) is not str or not thread_id:
            raise CodexEventError("thread.started is missing a non-empty string 'thread_id'")
        self._thread_id = thread_id

    def _apply_turn_started(self) -> None:
        self._require_not_terminal("turn.started")
        if self._turn_started:
            raise CodexEventError("received a second turn.started event")
        self._turn_started = True

    def _apply_item_completed(self, payload: dict[str, object]) -> None:
        self._require_not_terminal("item.completed")
        item = payload.get("item")
        if not isinstance(item, dict):
            raise CodexEventError("item.completed is missing an 'item' object")
        item_type = item.get("type")
        if type(item_type) is not str:
            raise CodexEventError("item.completed 'item' is missing a string 'type' field")
        if item_type != "agent_message":
            return
        text = item.get("text")
        if type(text) is not str:
            raise CodexEventError("agent_message item is missing a string 'text' field")
        if self._final_message is not None:
            raise CodexEventError("received more than one final agent message")
        self._final_message = text

    def _apply_terminal(self, event_type: str, payload: dict[str, object]) -> None:
        self._require_not_terminal(event_type)
        usage = self._parse_usage(payload, required=event_type == "turn.completed")
        if event_type == "turn.completed" and self._final_message is None:
            raise CodexEventError("turn.completed requires exactly one final agent message")
        self._terminal_type = event_type
        self._usage = usage

    def _parse_usage(self, payload: dict[str, object], *, required: bool) -> CodexUsage | None:
        usage_payload = payload.get("usage")
        if usage_payload is None:
            if required:
                raise CodexEventError("turn.completed is missing a 'usage' field")
            return None
        if not isinstance(usage_payload, dict):
            raise CodexEventError("'usage' field must be a JSON object")
        tokens: dict[str, int] = {}
        for field in _USAGE_FIELDS:
            value = usage_payload.get(field)
            # isinstance(True, int) is True in Python, so bool must be
            # excluded explicitly -- a bool is never a valid token count.
            if type(value) is not int or value < 0:
                raise CodexEventError(f"usage field {field!r} must be a non-negative integer")
            tokens[field] = value
        return CodexUsage(
            input_tokens=tokens["input_tokens"],
            cached_input_tokens=tokens["cached_input_tokens"],
            output_tokens=tokens["output_tokens"],
            reasoning_output_tokens=tokens["reasoning_output_tokens"],
        )
