# api/routes/_sse.py
"""
Shared SSE generator for PacerAI streaming endpoints.

Extracted from api/routes/chat.py (Phase 3, Plan 03) to enable onboarding
and coaching endpoints to share a single generator implementation while
injecting different system prompts (D-22 dynamic system prompt pattern).

SSE event schema (D-07):
  event: token
  data: {"text": "..."}

  event: tool_start
  data: {"name": "...", "tool_use_id": "toolu_..."}

  event: tool_result
  data: {"tool_use_id": "toolu_...", "name": "...", "value": ...}

  event: done
  data: {}

  event: error
  data: {"code": "...", "message": "..."}
"""

import json

import anthropic

from backend.agent.loop import run_turn as _default_run_turn
from backend.agent.trust import scan_buffer


async def sse_generator(
    messages: list[dict],
    model: str,
    system_prompt: str | None = None,
    _run_turn=None,
    assistant_sink: list | None = None,
    user_id: str | None = None,
    conversation_id: str | None = None,
):
    """
    Async generator that drives run_turn and formats each event as an SSE frame.

    Args:
        messages:       Current conversation history to pass to run_turn.
        model:          Claude model identifier string.
        system_prompt:  Optional system prompt override (D-22). When None,
                        run_turn uses its default SYSTEM_PROMPT constant so
                        existing callers are unaffected.
        _run_turn:      Optional run_turn override for testing. When None,
                        uses the module-level default import. Callers (chat.py,
                        onboarding.py) pass their own module-level run_turn
                        reference so monkeypatching the caller module's
                        run_turn attribute is effective (test_sse.py pattern).
        assistant_sink: Optional mutable list. When provided, the fully
                        accumulated assistant text (concatenated from all
                        "token" events) is appended as a single string after
                        the stream completes on a `done`-terminated turn.
                        Nothing is appended on the error path (WR-06) --
                        this now covers BOTH a raised exception AND a turn
                        whose LAST yielded event is `event: error`. run_turn's
                        abnormal paths (max_tool_turns, unexpected_stop,
                        max_retries) each yield an error event and then
                        `return` normally -- a normal generator exit, not an
                        exception -- so gating on "the loop exited without
                        exception" alone would still persist that partial/
                        truncated text as if the turn completed. Existing
                        callers that omit this parameter (e.g. chat.py) are
                        unaffected.
        user_id:        Authenticated user's UUID (260702-wev). Forwarded to
                        run_turn, which injects it server-side into
                        save_profile/generate_plan tool calls.
        conversation_id: Conversation UUID (08-05). Forwarded to run_turn,
                        which threads it into dispatch_tool for durable audit
                        writes and uses it to seed tool_result_values from the
                        prior turns' audit trail (TRUST-06/TRUST-09).

    Frame format per D-07:
      event: <event_type>\\ndata: <json>\\n\\n

    Error handling: any unexpected exception from run_turn is caught and emitted
    as a final `event: error` frame so the stream never dies silently. Per
    WR-06, "nothing is appended on the error path" also applies when run_turn
    itself yields a terminal `event: error` and returns normally (no exception
    is raised in that case) -- the post-loop append is gated on the LAST
    yielded event being `done`, not merely on the loop exiting cleanly.
    """
    # Per-request Anthropic client: reads ANTHROPIC_API_KEY from env.
    # Instantiated here (not at module import) so the module is importable without the key.
    client = anthropic.AsyncAnthropic()
    audit_log: list = []

    # Use the caller-supplied run_turn (for monkeypatching) or the default import.
    fn = _run_turn if _run_turn is not None else _default_run_turn

    accumulated_text: str = ""
    # WR-06: tracks the type of the LAST event run_turn yielded, so the
    # post-loop sink append can be gated on a genuine `done` completion
    # rather than merely "the loop exited without raising".
    terminal_event: str | None = None

    try:
        kwargs: dict = {}
        if system_prompt is not None:
            kwargs["system"] = system_prompt
        if user_id is not None:
            kwargs["user_id"] = user_id
        if conversation_id is not None:
            kwargs["conversation_id"] = conversation_id

        async for event in fn(messages, client, model, scan_buffer, audit_log, **kwargs):
            event_type = event["event"]
            terminal_event = event_type
            data = json.dumps(event["data"])
            yield f"event: {event_type}\ndata: {data}\n\n"
            # Accumulate assistant text from token events for the sink.
            if event_type == "token":
                accumulated_text += event["data"].get("text", "")

        # WR-06: only publish to the sink when the turn's LAST event was
        # `done`. run_turn's abnormal paths (max_tool_turns, unexpected_stop,
        # max_retries) yield `event: error` and then return normally -- a
        # normal generator exit -- so checking only "no exception was raised"
        # would still persist that partial/truncated text as if the turn
        # completed successfully.
        if assistant_sink is not None and terminal_event == "done":
            assistant_sink.append(accumulated_text)
    except Exception as exc:  # noqa: BLE001
        error_data = json.dumps({"code": "server_error", "message": str(exc)})
        yield f"event: error\ndata: {error_data}\n\n"
        # Do NOT append to assistant_sink on the error path.
