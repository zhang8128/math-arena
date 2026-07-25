import json

import pytest

from mathloop.codex.events import CodexEventError, CodexEventParser


def encoded(payload: dict[str, object]) -> bytes:
    return json.dumps(payload).encode() + b"\n"


def usage_payload(
    *,
    input_tokens: object = 10,
    cached_input_tokens: object = 2,
    output_tokens: object = 4,
    reasoning_output_tokens: object = 1,
) -> dict[str, object]:
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": reasoning_output_tokens,
    }


def test_parser_reduces_completed_turn_and_usage() -> None:
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-1"}))
    parser.feed(encoded({"type": "turn.started"}))
    parser.feed(
        encoded(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": '{"strategy":"induction"}'},
            }
        )
    )
    parser.feed(
        encoded(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 10,
                    "cached_input_tokens": 2,
                    "output_tokens": 4,
                    "reasoning_output_tokens": 1,
                },
            }
        )
    )
    transcript = parser.finish()
    assert transcript.thread_id == "thread-1"
    assert transcript.dispatched is True
    assert transcript.final_message == '{"strategy":"induction"}'
    assert transcript.usage.output_tokens == 4


def test_parser_represents_failed_turn_without_final_message() -> None:
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-2"}))
    parser.feed(encoded({"type": "turn.started"}))
    parser.feed(
        encoded({"type": "turn.failed", "error": {"message": "model overloaded"}})
    )
    transcript = parser.finish()
    assert transcript.dispatched is True
    assert transcript.terminal_type == "turn.failed"
    assert transcript.final_message is None
    assert transcript.usage is None


def test_parser_rejects_duplicate_start_completion_and_oversize() -> None:
    parser = CodexEventParser(max_bytes=80)
    parser.feed(encoded({"type": "turn.started"}))
    with pytest.raises(CodexEventError):
        parser.feed(encoded({"type": "turn.started"}))
    with pytest.raises(CodexEventError):
        parser.feed(b"x" * 81)


def test_parser_rejects_second_thread_started() -> None:
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-1"}))
    with pytest.raises(CodexEventError):
        parser.feed(encoded({"type": "thread.started", "thread_id": "thread-2"}))


def test_parser_rejects_second_terminal_event() -> None:
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-1"}))
    parser.feed(encoded({"type": "turn.started"}))
    parser.feed(
        encoded(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "done"},
            }
        )
    )
    parser.feed(encoded({"type": "turn.completed", "usage": usage_payload()}))
    with pytest.raises(CodexEventError):
        parser.feed(
            encoded({"type": "turn.failed", "error": {"message": "too late"}})
        )


def test_parser_rejects_agent_message_after_terminal_completion() -> None:
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-1"}))
    parser.feed(encoded({"type": "turn.started"}))
    parser.feed(
        encoded(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "done"},
            }
        )
    )
    parser.feed(encoded({"type": "turn.completed", "usage": usage_payload()}))
    with pytest.raises(CodexEventError):
        parser.feed(
            encoded(
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": "late"},
                }
            )
        )


def test_parser_accepts_documented_item_subtypes_without_mutating_state() -> None:
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-1"}))
    parser.feed(encoded({"type": "turn.started"}))
    parser.feed(
        encoded({"type": "item.started", "item": {"type": "command_execution"}})
    )
    parser.feed(
        encoded(
            {
                "type": "item.completed",
                "item": {"type": "command_execution", "text": "ls"},
            }
        )
    )
    parser.feed(
        encoded(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "done"},
            }
        )
    )
    parser.feed(encoded({"type": "turn.completed", "usage": usage_payload()}))
    transcript = parser.finish()
    assert transcript.final_message == "done"
    item_types = [
        event.event_type for event in transcript.events if event.event_type.startswith("item.")
    ]
    assert item_types == ["item.started", "item.completed", "item.completed"]


def test_parser_preserves_unknown_events_without_mutating_lifecycle() -> None:
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-1"}))
    parser.feed(encoded({"type": "turn.started"}))
    parser.feed(encoded({"type": "codex.debug", "note": "diagnostic"}))
    parser.feed(
        encoded(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "done"},
            }
        )
    )
    parser.feed(encoded({"type": "turn.completed", "usage": usage_payload()}))
    # Unknown events never mutate lifecycle state, so they are tolerated even
    # after the terminal event has already been recorded.
    parser.feed(encoded({"type": "codex.debug", "note": "post-terminal"}))
    transcript = parser.finish()
    unknown_event_types = [
        event.event_type for event in transcript.events if event.event_type == "codex.debug"
    ]
    assert unknown_event_types == ["codex.debug", "codex.debug"]
    assert transcript.final_message == "done"
    assert transcript.terminal_type == "turn.completed"


def test_parser_requires_one_json_object_per_line() -> None:
    parser = CodexEventParser(max_bytes=4096)
    with pytest.raises(CodexEventError):
        parser.feed(json.dumps([{"type": "turn.started"}]).encode() + b"\n")


def test_parser_requires_usage_when_turn_completes() -> None:
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-1"}))
    parser.feed(encoded({"type": "turn.started"}))
    parser.feed(
        encoded(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "done"},
            }
        )
    )
    with pytest.raises(CodexEventError):
        parser.feed(encoded({"type": "turn.completed"}))


def test_parser_requires_final_agent_message_when_turn_completes() -> None:
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-1"}))
    parser.feed(encoded({"type": "turn.started"}))
    with pytest.raises(CodexEventError):
        parser.feed(encoded({"type": "turn.completed", "usage": usage_payload()}))


def test_parser_last_agent_message_before_terminal_wins() -> None:
    """Real Codex turns routinely emit assistant preambles before the final
    answer (made more likely by the production prompt inviting the model to
    inspect the repository and run tests first) -- a second `agent_message`
    must not be fatal. The LAST one seen before the terminal event is the
    one that counts, not the first.
    """
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-1"}))
    parser.feed(encoded({"type": "turn.started"}))
    parser.feed(
        encoded(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "first"},
            }
        )
    )
    parser.feed(
        encoded(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "second"},
            }
        )
    )
    parser.feed(encoded({"type": "turn.completed", "usage": usage_payload()}))
    transcript = parser.finish()
    assert transcript.final_message == "second"


def test_parser_rejects_bool_as_int_usage_fields() -> None:
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-1"}))
    parser.feed(encoded({"type": "turn.started"}))
    parser.feed(
        encoded(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "done"},
            }
        )
    )
    with pytest.raises(CodexEventError):
        parser.feed(
            encoded(
                {
                    "type": "turn.completed",
                    "usage": usage_payload(output_tokens=True),
                }
            )
        )


def test_parser_never_defaults_missing_usage_field() -> None:
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-1"}))
    parser.feed(encoded({"type": "turn.started"}))
    parser.feed(
        encoded(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "done"},
            }
        )
    )
    incomplete_usage = usage_payload()
    del incomplete_usage["reasoning_output_tokens"]
    with pytest.raises(CodexEventError):
        parser.feed(encoded({"type": "turn.completed", "usage": incomplete_usage}))


def test_parser_carries_usage_from_failed_terminal_without_final_message() -> None:
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-1"}))
    parser.feed(encoded({"type": "turn.started"}))
    parser.feed(
        encoded(
            {
                "type": "turn.failed",
                "error": {"message": "model overloaded"},
                "usage": usage_payload(output_tokens=7),
            }
        )
    )
    transcript = parser.finish()
    assert transcript.final_message is None
    assert transcript.usage is not None
    assert transcript.usage.output_tokens == 7


def test_finish_requires_thread_turn_and_terminal_events() -> None:
    parser = CodexEventParser(max_bytes=4096)
    with pytest.raises(CodexEventError):
        parser.finish()


def test_parser_represents_error_terminal_without_final_message() -> None:
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-3"}))
    parser.feed(encoded({"type": "turn.started"}))
    parser.feed(encoded({"type": "error", "message": "stream aborted"}))
    transcript = parser.finish()
    assert transcript.terminal_type == "error"
    assert transcript.final_message is None
    assert transcript.usage is None
    assert transcript.dispatched is True


def test_parser_dispatched_is_true_before_a_terminal_event_is_seen() -> None:
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-1"}))
    parser.feed(encoded({"type": "turn.started"}))
    # The turn is durably consumed the moment turn.started is accepted, even
    # though the stream never reaches a terminal event.
    assert parser.dispatched is True
    with pytest.raises(CodexEventError):
        parser.finish()


def test_parser_rejects_negative_usage_value() -> None:
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-1"}))
    parser.feed(encoded({"type": "turn.started"}))
    parser.feed(
        encoded(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "done"},
            }
        )
    )
    with pytest.raises(CodexEventError):
        parser.feed(
            encoded(
                {
                    "type": "turn.completed",
                    "usage": usage_payload(output_tokens=-1),
                }
            )
        )


def test_parser_discards_agent_message_captured_before_a_failed_terminal() -> None:
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-1"}))
    parser.feed(encoded({"type": "turn.started"}))
    parser.feed(
        encoded(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "partial progress"},
            }
        )
    )
    parser.feed(
        encoded({"type": "turn.failed", "error": {"message": "model overloaded"}})
    )
    transcript = parser.finish()
    assert transcript.terminal_type == "turn.failed"
    assert transcript.final_message is None


def test_parser_never_infers_missing_fields_on_optional_failed_usage() -> None:
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-1"}))
    parser.feed(encoded({"type": "turn.started"}))
    incomplete_usage = usage_payload()
    del incomplete_usage["output_tokens"]
    # turn.failed's usage is optional, but if present it must be complete and
    # valid -- the parser must never fabricate a zero for a missing field.
    with pytest.raises(CodexEventError):
        parser.feed(
            encoded(
                {
                    "type": "turn.failed",
                    "error": {"message": "model overloaded"},
                    "usage": incomplete_usage,
                }
            )
        )
