# Records and corrections

Each event has a stable lowercase 32-hex UUID `id` and a contiguous integer `seq`.
References address identifiers within one ledger. The sequence reflects serialized
transaction order; it is not a timestamp or a cross-machine identifier.

| Field | Meaning |
| --- | --- |
| `kind` | `decision`, `question`, or `answer` |
| `words` | Original accepted text, unchanged |
| `interpretation` | Separate optional one-line reading of a decision or answer |
| `actor` | Optional caller-supplied attribution label |
| `source` | Reported source category for decisions/answers; null for questions |
| `occurred_at` | Caller-reported time, or the recording time when omitted |
| `recorded_at` | Time generated during the write transaction |
| `reply_to` | Earlier question answered by this event, or null |
| `corrects` | Earlier decision corrected by this event, or null |
| `root_id` | Original question/decision for this history |
| `metadata` | Separate typed caller metadata |

A question is open precisely when no answer points to it. Resolving a question
never updates its row, and an answer cannot reference another answer or decision.
No answer contents are interpreted: a reply saying “wait” still resolves the
pending question by recording a response. It does not approve the proposed action.

Repeated answers, even identical ones, create separate events with new identifiers.
The answer with the greatest committed sequence is current. This preserves the
source behavior in which a later answer is an explicit correction, while making
commit order authoritative even for historical timestamps.

A decision correction points to an earlier decision. It can name the original or
another correction in the same history. All remain present; the latest committed
decision in that history is the current reported decision. `history ID` accepts any
event in the history, including an answer, and returns the original root plus all
related events and the current answer/decision. An unanswered question has
`current: null`.

The CLI has no update/delete operation. SQLite triggers reject ordinary SQL UPDATE
and DELETE on events, and every operation checks the expected schema, all records,
sequence continuity, and references. Stored metadata must be a flat JSON object
with unique keys; duplicate keys are rejected rather than collapsed to the last
value. Malformed or excessively nested metadata blocks reads and writes with a
storage error, including on supported Python versions with stricter parser limits. This is append-only application behavior,
not tamper-proof storage: someone controlling the database can replace it or alter
its guards. The ledger cannot determine whether a caller quoted someone correctly
or whether an actor label identifies a real person.
