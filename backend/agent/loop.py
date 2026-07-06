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
    is appended (not the violating assistant message -- Pitfall 5).

The trust_scanner is injected so the loop is unit-testable without the
real regex (Plan 04). Signature: trust_scanner(text: str, tool_result_values:
list[str], self_reported_values: list[str] | None = None) -> TrustViolation | None.

08-08 / D-02 / D-05: run_turn extracts self_reported_values -- the user's own
chat messages this turn (role=="user" string content only) -- ONCE, before
the while loop, and threads that snapshot into every trust_scanner call
alongside tool_result_values. This is the missing "onboarding profile /
self-report" half of D-02's confirmed-values registry design: it lets a
Branch A self-reported physiological number (e.g. a directly-stated LTHR)
be legitimately restated in the mandatory D-03 confirmation-gate summary
with NO tool call, without opening a laundering loophole -- the snapshot is
taken before any correction/retry message or tool-result block is appended,
so only genuine user-authored text ever enters the channel. It never flows
into tool arguments: server-side injection (D-02 / Plan 06) remains the sole
authority for computed-output fields.

Streaming pitfall (Pitfall 3): get_final_message() must be awaited AFTER
the async-for over stream events completes, never inside the loop.
"""

import asyncio
import json
from typing import AsyncIterator

from backend.agent.audit import load_prior_audit_values
from backend.agent.tools import TOOL_SCHEMAS, dedup_key, dispatch_tool
from backend.agent.trust import collect_self_reported_values, handle_violation

MAX_RETRIES: int = 3
MAX_TOOL_TURNS: int = 10

SYSTEM_PROMPT = (
    "You are PacerAI, an evidence-based adaptive cycling coach. "
    "You MUST call a tool for any physiological number (power zones, TSS, FTP, CTL, ATL, TSB, HR zones). "
    "Never emit a physiological number from your own reasoning -- use only the provided tools. "
    "If no tool covers the needed calculation, call log_capability_gap."
)


async def run_turn(
    messages: list[dict],
    client,  # anthropic.AsyncAnthropic -- injected for testability
    model: str,
    trust_scanner,  # callable: (str, list[str]) -> TrustViolation | None
    audit_log: list,
    system: str = SYSTEM_PROMPT,  # D-22: injectable system prompt; defaults to module constant
    user_id: str | None = None,
    conversation_id: str | None = None,
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
        user_id:       Authenticated user's UUID (260702-wev). When provided, injected
                       server-side into save_profile/generate_plan tool calls via
                       dispatch_tool, overriding any LLM-supplied value.
        conversation_id: Conversation UUID (08-05/TRUST-06/TRUST-09). When provided,
                       threaded into dispatch_tool for durable per-call audit
                       writes and used to seed tool_result_values from the
                       conversation's prior-turn audit trail before the first
                       trust scan, so a legitimate number established in an
                       earlier (stateless) invocation is not re-flagged.

    Invariants (08-08 / D-02 / D-05): user-self-reported numbers are
    attributed alongside tool results via a snapshot of self_reported_values
    taken once, before the while loop, sourced ONLY from role=="user" string
    messages present at turn start (never assistant text, never a tool-result
    content-block list) -- and passed unchanged to every trust_scanner call
    this turn. This channel never flows into tool arguments; server-side
    injection remains the sole authority for computed-output fields.
    """
    retries: int = 0
    tool_turns: int = 0
    # CR-01 / 260702-w52: tool_result_values is list[str] (JSON text from tool
    # results), not list[dict]. scan_buffer does substring checks on these
    # strings. Declared OUTSIDE the while loop so it accumulates across every
    # round of this turn (trust retries AND tool-use continuation rounds) --
    # a later round's text may legitimately reference a number from an
    # earlier round's tool call, and must still be able to attribute it.
    tool_result_values: list[str] = []
    # TRUST-09 / D-04: seed with prior turns' durable audit-trail results before
    # the first scan. On a stateless serverless invocation, a number established
    # in an earlier turn (and now only referenced qualitatively in this turn's
    # prose) would otherwise be flagged as an unsourced trust violation. No-op
    # (returns []) when conversation_id is None -- new conversations behave
    # exactly as before this change.
    if conversation_id is not None:
        tool_result_values.extend(
            await load_prior_audit_values(conversation_id, user_id=user_id)
        )

    # 08-08 / D-02 / D-05: one-time snapshot of genuine user inputs at turn
    # start. Taken BEFORE the while loop so the correction/retry user message
    # appended on a violation (and any tool-result content-block lists) never
    # enter the self-report channel -- only what the user actually typed this
    # turn is a legitimate attribution source.
    self_reported_values: list[str] = collect_self_reported_values(messages)

    while retries <= MAX_RETRIES:
        text_buffer: list[str] = []

        # Per-turn dedup dict (D-13 / Anti-Pattern: fresh per iteration, not module-level)
        seen_calls: dict[tuple, bool] = {}

        # ------------------------------------------------------------------
        # 1. Stream one API call (Pitfall 3: get_final_message after async-for)
        # ------------------------------------------------------------------
        async with client.messages.stream(
            model=model,
            max_tokens=4096,
            tools=TOOL_SCHEMAS,
            system=system,
            messages=messages,
        ) as stream:
            async for event in stream:
                # Collect text deltas into the per-turn buffer.
                # TRUST-03: Do NOT yield token events yet -- buffer first, trust-scan after.
                # Anti-pattern (RESEARCH.md): yielding tokens before scan lets unsourced
                # physiological numbers reach the SSE stream before the violation is caught.
                if hasattr(event, "type") and event.type == "content_block_delta":
                    if hasattr(event, "delta") and hasattr(event.delta, "text"):
                        text_buffer.append(event.delta.text)

            # Pitfall 3: awaited after the async-for exits, not inside it.
            final_msg = await stream.get_final_message()

        stop_reason = final_msg.stop_reason

        # ------------------------------------------------------------------
        # 2. Trust scan the buffered assistant text (D-09, TRUST-03)
        #    Before appending ANY assistant content to messages (Pitfall 5).
        # ------------------------------------------------------------------
        buffered_text = "".join(text_buffer)
        violation = trust_scanner(buffered_text, tool_result_values, self_reported_values)

        if violation:
            retries += 1
            # CR-02: await handle_violation to satisfy TRUST-05 (log capability gap).
            # Best-effort: handle_violation swallows DB errors internally.
            await handle_violation(violation)
            # Pitfall 5: Do NOT append the violating assistant message.
            # Append a correction user message asking for qualitative rephrasing.
            # TRUST-03: Do NOT yield the buffered tokens -- they contain the unsourced
            # number and must never reach the SSE stream on a violation path.
            messages.append({
                "role": "user",
                "content": (
                    "Please rephrase your response without specific physiological "
                    "numbers. Use qualitative descriptions only -- any numbers must "
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
        # 3. Trust scan passed -- now safe to emit buffered token events.
        #    Emit all buffered text deltas as individual token events before
        #    routing on stop_reason. This preserves the streaming-text UX
        #    while enforcing the trust invariant (numbers only after scan).
        # ------------------------------------------------------------------
        for chunk in text_buffer:
            yield {"event": "token", "data": {"text": chunk}}

        # ------------------------------------------------------------------
        # 4. Route on stop_reason
        # ------------------------------------------------------------------
        if stop_reason == "tool_use":
            # CR-03: bound tool-use iterations independently of trust retries.
            tool_turns = tool_turns + 1
            if tool_turns > MAX_TOOL_TURNS:
                yield {
                    "event": "error",
                    "data": {
                        "code": "max_tool_turns",
                        "message": f"Tool-use turn limit ({MAX_TOOL_TURNS}) exceeded",
                    },
                }
                return

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

            # WR-01: guard against all blocks being duplicated in a single turn,
            # which would produce an empty content array rejected by the API.
            if not unique_blocks:
                messages.append({
                    "role": "user",
                    "content": [{"type": "text", "text": "(duplicate tool calls skipped)"}],
                })
            else:
                # D-12 / AGENT-02: dispatch unique blocks concurrently
                result_blocks = await asyncio.gather(
                    *[
                        dispatch_tool(
                            b, audit_log, user_id=user_id, conversation_id=conversation_id
                        )
                        for b in unique_blocks
                    ]
                )

                # Yield tool_result events and accumulate values for trust attribution
                for block, result_block in zip(unique_blocks, result_blocks):
                    # CR-01: extract JSON text string for trust attribution,
                    # not the raw dict. scan_buffer does substring checks on strings.
                    content_text = None
                    content_list = result_block.get("content", [])
                    if content_list and isinstance(content_list[0], dict):
                        content_text = content_list[0].get("text")
                    if content_text:
                        tool_result_values.append(content_text)
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
            # Continue while loop -- next iteration calls the API again

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
