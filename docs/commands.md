# Commands and input

Choose storage with global `--dir PATH` or `DECISION_LEDGER_DIR`. Global options
precede the command. `--timeout SECONDS` controls SQLite's contention wait and
accepts finite values from 0 through 86400; the default is 10 seconds.

| Command | Output |
| --- | --- |
| `init` | Creates a new ledger, or validates an existing one; returns initialization status |
| `record WORDS` | Appends reported original words as a decision |
| `record WORDS --corrects ID` | Appends a correction to an earlier decision |
| `ask WORDS` | Appends a question that starts open |
| `answer QUESTION_ID WORDS` | Appends an answer and resolves that question |
| `open` | JSON array of questions without an answer |
| `list [--kind KIND] [--actor LABEL]` | JSON array of matching records in append order |
| `history ID` | Object with `root`, `current`, and all `events` in that history |
| `validate` | Schema, integrity, reference, and record validation plus record count |

All three write commands accept exactly one input mechanism: positional `WORDS`,
`--words-stdin`, or `--words-file FILE`. File input must be a regular file. Input is
strict UTF-8; empty/whitespace-only text and NUL are refused. These checks do not
strip, rewrap, cap, or otherwise alter accepted text. Read stdin through a quoted
heredoc to avoid your shell expanding `$variables` or command substitutions.

`--interpretation TEXT` is available on decisions and answers, and must be one
nonblank line. `--source chat|paste|transcript` labels a caller-reported origin and
defaults to `chat`. Questions have no source or interpretation field value because
they are questions recorded by the caller, not statements attributed to an operator.

Every write accepts optional `--actor LABEL`, `--at TIMESTAMP`, and repeated
`--meta KEY=VALUE`. Actor labels use 1–128 characters: first a letter/digit, then
letters/digits or `._:@/-`. Attribution is never inferred from the environment,
user accounts, hostnames, or a session registry.

`--at` accepts a real UTC calendar timestamp in `YYYY-MM-DDTHH:MM:SS[.ffffff]Z`
form; storage normalizes it to six fractional digits. It describes when the words
were reported to have been spoken. `recorded_at` is generated during the write
transaction. Sequence numbers determine correction precedence, so a historical
backfill cannot override a later committed answer merely through its timestamp.

Metadata is a flat object with identifier-shaped keys. Envelope keys are reserved
and repeated keys are rejected. `true`/`false` become booleans; unsigned decimal
integers without leading zeroes become integers. Other values, including `007`,
negative-looking numbers, and an empty value, remain strings. No metadata has task
tracker, approval, or workflow-execution semantics.

| Exit | Meaning |
| --- | --- |
| `0` | Command succeeded and stdout was written successfully |
| `2` | Invalid arguments or input text |
| `3` | Storage, schema, integrity, or other operational failure |
| `4` | Ledger is uninitialized, or a referenced identifier is absent/wrong kind |
| `5` | SQLite contention prevented the operation |
| `6` | Stdout failed; a write may already be committed |
| `129`, `130`, `143` | Handled HUP, keyboard interruption, or TERM |

An empty `open`/`list` result is successful only for an initialized, validated
ledger. List filters match literal values and can legitimately match no records.
Unknown history, question, or correction identifiers return 4. Failed operations
write diagnostics to stderr, never a fabricated success receipt.
