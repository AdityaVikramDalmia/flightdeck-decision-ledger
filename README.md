# Decision Ledger

A local, append-only ledger for the decisions, questions, and answers that callers report, kept in
their original wording: an interpretation never replaces the words, corrections append new records,
and open questions are derived from explicit answers. It records what was decided and asked, not
process or session lifecycle events (launches and completions belong in `flightdeck-session-ledger`).

> **Status:** public Apache-2.0 reference implementation, deprecated for new Claude Code
> integrations as of 2026-09-22. Not a claim that Claude Code replaces every capability; no
> ongoing feature work or support is promised.

## What it does

- `record` stores reported words as a decision, with an optional separate one-line
  interpretation; `record ... --corrects ID` appends a correction.
- `ask`, `answer`, and `open` track questions: a question is open exactly when no answer points
  to it, and a repeated answer is a correction.
- `history ID` returns the original record, the current one, and the complete correction history.
- Every command emits one JSON value. Storage is one SQLite database in an explicit directory.

## Why it exists

A summary can quietly stand in for what someone actually said, and a later answer can overwrite
an earlier one. Decision Ledger keeps accepted words unchanged, with interpretation in a separate
field, and keeps every answer and correction readable. The latest committed record is current.

## Install

Requires Python 3.9+ with its standard-library SQLite module, on macOS or Linux. At runtime it
needs no packages, Git checkout, service, model, or network access.

```bash
git clone https://github.com/AdityaVikramDalmia/flightdeck-decision-ledger.git
cd flightdeck-decision-ledger
make install PREFIX="$HOME/.local"
export PATH="$HOME/.local/bin:$PATH"
```

The installed executable is self-contained and can be copied independently.

## Quick use

```bash
export DECISION_LEDGER_DIR="$PWD/.decision-ledger"
decision-ledger init

decision-ledger record --words-stdin --source paste \
  --interpretation 'Keep the second version pending review' <<'WORDS'
Keep version 2. Don't substitute your interpretation for these words.
WORDS

question_id=$(decision-ledger ask 'May the release proceed?' |
  python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
decision-ledger open
decision-ledger answer "$question_id" 'Wait until review is complete.'
decision-ledger history "$question_id"
```

Or pass `decision-ledger --dir '/path with spaces/state' COMMAND` explicitly.
`init` is required: an unknown storage path cannot silently become an empty queue.

A successful write emits the committed event, including a stable UUID identifier and a
transaction-ordered sequence number. `--words-stdin` and `--words-file FILE` preserve UTF-8 text,
including line endings and trailing whitespace. They avoid command-line size limits and shell
quoting. Words are never shortened or normalized; interpretation occupies a separate field.

Repeated answers are legal corrections. Every answer remains stored, and the
latest committed answer is current. To correct a decision, append a decision with
`record ... --corrects ORIGINAL_ID`. `history` shows the original, current record,
and complete correction history.

See [documentation](docs/README.md) for the schema, transaction boundaries,
recovery, and exit codes. [Provenance](PROVENANCE.md) records the source revision
and deliberate changes.

## Limits

- This is local memory for callers' reports. An actor label, quoted text, or answer
  is **not authentication, proof of a human approval, or authorization to act**.
  The tool does not interpret or execute the recorded words.
- Append-only is application behavior, not tamper-proof storage: someone controlling the database
  can replace it or alter its guards ([records](docs/records.md)).
- Use a local filesystem on one machine. Every command validates the complete ledger, so it suits
  modest local decision history, not a high-throughput event stream. A write commits before its
  receipt prints, so a missing receipt does not prove a missing record ([storage](docs/storage.md)).

## Test

```bash
make test
bash examples/roundtrip.sh
```

## License and maintenance

Copyright 2026 Aditya Dalmia. Licensed under [Apache-2.0](LICENSE), with
[attribution](NOTICE) and [source provenance](PROVENANCE.md). This is a public
reference implementation, deprecated for new Claude Code integrations as of 2026-09-22. See the [release preparation index](docs/release/README.md),
[contributing guide](CONTRIBUTING.md), and [security contact](SECURITY.md).
