# agent/loop.py
"""
Multi-turn agentic loop for PacerAI.

run_turn is an async generator that drives the Anthropic streaming API
in a while-loop, yielding SSE-shaped event dicts to the caller (SSE
transport lives in api/routes/chat.py and is not imported here).

Key invariants:
  - AGENT-01 / D-11: explicit stop_reason == "tool_use" check; raw anthropic
    SDK only (the autonomous agent SDK is explicitly forbidden per AGENT-01).
  - AGENT-02 / D-12: parallel tool dispatch via asyncio.gather.
  - AGENT-03: MAX_RETRIES = 3 hard cap on trust-violation retries.
  - AGENT-04 / D-13: per-turn dedup by (name, args_hash) via dedup_key.
  - TRUST-04: audit_log receives one entry per dispatched tool call.
  - TRUST-05 / D-09: injected trust_scanner intercepts buffered assistant
    text before it is forwarded; on violation the corrective user message
    is appended (not the violating assistant message — Pitfall 5).

The trust_scanner is injected so the loop is unit-testable without the
real regex (Plan 04). Signature: trust_scanner(text: str, tool_result_values:
list[dict]) -> TrustViolation | None.

Streaming pitfall (Pitfall 3): get_final_message() must be awaited AFTER
the async-for over stream events completes, never inside the loop.
"""

import asyncio
import json
from typing import AsyncIterator

from agent.tools import TOOL_SCHEMAS, dedup_key, dispatch_tool

MAX_RETRIES: int = 3


async def run_turn(
    messages: list[dict],
    client,  # anthropic.AsyncAnthropic — injected for testability
    model: str,
    trust_scanner,  # callable: (str, list) -> TrustViolation | None
    audit_log: list,
) -> AsyncIterator[dict]:
    """
    Drive a multi-turn Anthropic conversation with tool use.

    Yields SSE-shaped dicts:
      {"event": "token",       "data": {"text": str}}
      {"event": "tool_start",  "data": {"name": str, "tool_use_id": str}}
      {"event": "tool_result", "data": {"tool_use_id": str, "name": str, "value": any}}
      {"event": "done",        "data": {}}
      {"event": "error",       "data": {"code": str, "message": str}}

    Args:
        messages:      Current conversation history (mutated in place each turn).
        client:        AsyncAnthropic instance (or test mock with .messages.stream()).
        model:         Claude model identifier string.
        trust_scanner: Callable that scans buffered assistant text for unsourced
                       physiological numbers. Returns a violation object (truthy) or
                       None. Injected so tests can pass a no-op lambda.
        audit_log:     List accumulating per-call audit entries (TRUST-04).
    """
    retries: int = 0

    while retries <= MAX_RETRIES:
        text_buffer: list[str] = []
        tool_result_values: list[dict] = []

        # Per-turn dedup dict (D-13 / Anti-Pattern: fresh per iteration, not module-level)
        seen_calls: dict[tuple, bool] = {}

        # ------------------------------------------------------------------
        # 1. Stream one API call (Pitfall 3: get_final_message after async-for)
        # ------------------------------------------------------------------
        async with client.messages.stream(
            model=model,
            max_tokens=4096,
            tools=TOOL_SCHEMAS,
            messages=messages,
        ) as stream:
            async for event in stream:
                # Collect text deltas into the per-turn buffer.
                # Do NOT yield token events here — buffer first, trust-scan later.
                if hasattr(event, "type") and event.type == "content_block_delta":
                    if hasattr(event, "delta") and hasattr(event.delta, "text"):
                        text_buffer.append(event.delta.text)
                        yield {"event": "token", "data": {"text": event.delta.text}}

            # Pitfall 3: awaited after the async-for exits, not inside it.
            final_msg = await stream.get_final_message()

        stop_reason = final_msg.stop_reason

        # ------------------------------------------------------------------
        # 2. Trust scan the buffered assistant text (D-09, TRUST-03)
        #    Before appending ANY assistant content to messages (Pitfall 5).
        # ------------------------------------------------------------------
        buffered_text = "".join(text_buffer)
        violation = trust_scanner(buffered_text, tool_result_values)

        if violation:
            retries += 1
            # Pitfall 5: Do NOT append the violating assistant message.
            # Append a correction user message asking for qualitative rephrasing.
            messages.append({
                "role": "user",
                "content": (
                    "Please rephrase your response without specific physiological "
                    "numbers. Use qualitative descriptions only — any numbers must "
                    "come from the tool results in this conversation."
                ),
            })
            yield {
                "event": "error",
                "data": {
                    "code": "trust_violation",
                    "message": str(violation),
                },
            }
            continue  # retry the turn

        # ------------------------------------------------------------------
        # 3. Route on stop_reason
        # ------------------------------------------------------------------
        if stop_reason == "tool_use":
            # Append assistant message now that it has passed trust scan
            messages.append({"role": "assistant", "content": final_msg.content})

            # Collect tool_use blocks from final message content
            tool_use_blocks = [
                b for b in final_msg.content
                if hasattr(b, "type") and b.type == "tool_use"
            ]

            # D-13: dedup within this turn before dispatching
            unique_blocks = []
            for block in tool_use_blocks:
                key = dedup_key(block.name, block.input)
                if key not in seen_calls:
                    seen_calls[key] = True
                    unique_blocks.append(block)
                    yield {
                        "event": "tool_start",
                        "data": {
                            "name": block.name,
                            "tool_use_id": block.id,
                        },
                    }

            # D-12 / AGENT-02: dispatch unique blocks concurrently
            result_blocks = await asyncio.gather(
                *[dispatch_tool(b, audit_log) for b in unique_blocks]
            )

            # Yield tool_result events and accumulate values for trust attribution
            for block, result_block in zip(unique_blocks, result_blocks):
                tool_result_values.append(result_block)
                # Extract value text for trust attribution on next turn
                content_text = None
                content_list = result_block.get("content", [])
                if content_list and isinstance(content_list[0], dict):
                    content_text = content_list[0].get("text")
                yield {
                    "event": "tool_result",
                    "data": {
                        "tool_use_id": block.id,
                        "name": block.name,
                        "value": content_text,
                    },
                }

            # Append tool results as a user-role message and loop back
            messages.append({"role": "user", "content": list(result_blocks)})
            # Continue while loop — next iteration calls the API again

        elif stop_reason == "end_turn":
            yield {"event": "done", "data": {}}
            return

        else:
            # Unexpected stop_reason (e.g. "max_tokens", "stop_sequence")
            yield {
                "event": "error",
                "data": {
                    "code": "unexpected_stop",
                    "message": f"Unexpected stop reason: {stop_reason}",
                },
            }
            return

    # While loop exhausted: retries exceeded MAX_RETRIES
    yield {
        "event": "error",
        "data": {
            "code": "max_retries",
            "message": f"Max retries ({MAX_RETRIES}) exceeded",
        },
    }
