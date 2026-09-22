# Decision Ledger

> **Deprecated for new Claude Code integrations — 2026-09-22.** Retained as an
> Apache-2.0 reference project. Public launch remains deferred and the repository
> remains private. This is a maintainer status decision, not a claim that Claude
> Code replaces every capability. No ongoing feature work or support is promised.

Keep reported decisions, questions, and answers without replacing original wording
with an interpretation. Corrections append new records; the original text remains
readable. Open questions are derived from explicit answer references.

This is local memory for callers' reports. An actor label, quoted text, or answer
is **not authentication, proof of a human approval, or authorization to act**.
The tool does not interpret or execute the recorded words.

Requires Python 3.9+ with its standard-library SQLite module, on macOS or Linux.
No packages, Git checkout, service, model, or network access are required.

```bash
make install PREFIX="$HOME/.local"
export PATH="$HOME/.local/bin:$PATH"
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
The installed executable is self-contained and can be copied independently.

Every command emits one JSON value. A successful write emits the committed event,
including a stable UUID identifier and a transaction-ordered sequence number.
`--words-stdin` and `--words-file FILE` preserve UTF-8 text, including line endings
and trailing whitespace. They avoid command-line size limits and shell quoting.
Words are never shortened or normalized; interpretation occupies a separate field.

Repeated answers are legal corrections. Every answer remains stored, and the
latest committed answer is current. To correct a decision, append a decision with
`record ... --corrects ORIGINAL_ID`. `history` shows the original, current record,
and complete correction history.

```bash
make test
bash examples/roundtrip.sh
```

See [documentation](docs/README.md) for the schema, transaction boundaries,
recovery, and exit codes. [Provenance](PROVENANCE.md) records the source revision
and deliberate changes. Licensed under Apache-2.0; see [LICENSE](LICENSE) and [NOTICE](NOTICE). Repository visibility remains private.

## License and maintenance

Copyright 2026 Aditya Dalmia. Licensed under [Apache-2.0](LICENSE), with
[attribution](NOTICE) and [source provenance](PROVENANCE.md). Public launch is
deferred; repository access remains private. See the [release preparation index](docs/release/README.md),
[contributing guide](CONTRIBUTING.md), and [security contact](SECURITY.md).
