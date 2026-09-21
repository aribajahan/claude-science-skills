# archive-recall — why this exists

Built 2026-09-20, from a session where six completed analyses existed only in the conversation
and had to be recovered after the spans holding them had folded.

## What it caught

**The `results`/`hits` mistake, in the first attempt.** Six searches across six topics all
returned empty. The obvious reading — that none of this had been discussed — was wrong; the
result dict keys its matches under `hits` and the code was reading `results`. A false negative
that looks identical to a true one is the worst failure shape a retrieval tool can have, because
nothing prompts you to check.

**The `content`/`text` mistake, in the second attempt.** Seven messages recovered, all zero
characters, reported as `-> 0 chars` seven times. Caught only because zero is conspicuous.

**Tool output attributed to the user.** A sweep classifying on `role == "user"` returned 41
prompts. Filtering rehydrated tool results and fold-carrier summaries brought it to the true 24.
Without that filter, a transcript export would have presented 17 blocks of tool output and model
summaries as things the user had written.

## One honest limitation — and how the skill is shaped around it

The accessor details it documents (`hits`, `text`, `idx`, `next`) are **platform internals, not a
contract** — they can change between versions, and a skill that hard-asserts "the key is `hits`"
goes silently wrong the day it isn't. So the skill leads with the durable *method* (empty is not
absent; classify who really said what; a fold summary is a lead, not a quote) and keeps the exact
shapes in one clearly-marked "verify — may change" block, each with a self-check that prints the
keys actually returned. If a shape moves, the self-check surfaces it loudly instead of failing
quiet. Treat the shapes as today's observation; trust the method.

## What it deliberately does not do

**No `kernel.py`.** `host.archive` exists only in the `repl` tool; a sidecar loads into the
analysis kernel, where the API is absent. Shipping a sidecar here would produce helpers that fail
on import in the one place they load. The pure-logic half (`classify`) could technically live in a
sidecar, but the fetch cannot, and splitting one small procedure across two kernels with a
handoff file costs more than it saves.

**No interpretation.** It returns verbatim bytes and a classification. What the recovered text
means, and whether a past decision still stands, is yours.
