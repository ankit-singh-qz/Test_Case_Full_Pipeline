# Agent 7 runaway generation

Agent 7 (field-level design) was the only Tier 1 agent that kept dying
with `ReadTimeoutError` on Bedrock. The other three agents in that tier
had already finished. Raising the client timeout and cutting parallelism
did not fix it.

## What was actually happening

`ChatBedrockConverse` used a non-streaming `converse` call, so Bedrock
sent no bytes until the whole reply was done. `max_tokens` was unset.
The read timeout was therefore a cap on total generation time, and a
loop looked the same as a stalled network.

Agent 7 is the prompt that asks for concrete values at a string's exact
max length and one past it (`VARCHAR(50)` means a 50-character example
and a 51-character example). The model typed those out character by
character, could not count them, and fell into a repetition loop
(`1234567890` repeated, or `"A".repeat(50)` written as code instead of
JSON). A normal Agent 7 reply is about 2K tokens and finishes in
seconds. Agent 4, in the same tier, writes far more text and still
completes. A silent 120 seconds on a 2K-token job means the response
never finished.

`temperature=0` makes that loop deterministic. Once the FDD or TDD
state contains a long `VARCHAR`, every rerun hits the same loop.

## What changed

### `llm.py` (every agent)

- `call_agent` streams the reply. The read timeout now means "no bytes
  for this long", not "total generation time". A real Bedrock stall
  still surfaces as `ReadTimeoutError`. A loop does not.
- The last 800 characters are compressed as they arrive. Real JSON from
  this pipeline stays at or above about 0.17. A repetition loop scores
  about 0.02–0.03. Below 0.08 the stream is aborted and the tail is
  printed.
- A loop is retried at temperature 0.4 with a note telling the model
  not to write long literals. Temperature 0 would replay the same loop.
  After 3 failed attempts the call raises and includes that tail.
- A default output cap of 24000 tokens is a backstop. The largest
  technique agent produces about 12K tokens, so the default has
  headroom. `call_agent(..., max_tokens=N)` sets a tighter per-agent
  cap.
- Both knobs are overridable in `.env`:

  | Variable | Default | Meaning |
  |---|---|---|
  | `LLM_READ_TIMEOUT` | `120` | Seconds with no streamed bytes before the call fails |
  | `LLM_MAX_OUTPUT_TOKENS` | `24000` | Default `max_tokens` when an agent does not pass its own cap |

### `agents/agent7_field_level_design.py`

- Prompt rule: never write a string longer than 16 characters. A length
  boundary is a descriptor, not a typed-out literal. Example for
  `VARCHAR(50)`: valid `"<string of 50 chars>"`, invalid
  `"<string of 51 chars>"`.
- Agent 7's own cap is 8000 tokens, about 4x its normal output.
- After the model returns, any example string longer than 32 characters
  is replaced with `<string of N chars>`, where `N` is Python's
  `len()`. That corrects the case where the model used the same
  40-character string as both the valid max and the invalid over-max.

Downstream agents (boundary testing, data validation) consume those
descriptors as written. They do not need the 50 characters spelled out.
