# Provenance

Adapted from source revision `494799eea3b9e7ce8686506a288c297ccf96be8d`:

- `bin/directive.sh`: separate original words and interpretation; append-only
  decisions, questions, and answers; derived open questions; repeated answers as
  corrections; stdin/file ingestion preserving original text.
- `bin/directive-test.sh`: informed synthetic tests for reference validation,
  multiline/Unicode wording, large inputs, concurrent writes, and original-row
  preservation.

This standalone adaptation uses Python's standard-library SQLite support rather
than a shared shell helper stack and per-machine JSONL files. It requires explicit
initialization/storage, assigns stable UUID identifiers, orders corrections by
serialized transaction sequence, and validates the complete schema and history.
It adds explicit decision-correction histories and stdin/file input for questions.

Caller attribution is explicit, with no personal registry, roster, task-tracker,
or global-agent configuration lookup. No historical words, authentic operator
records, private identifiers, incident descriptions, or live state were copied.
All fixtures and examples are synthetic. Records remain caller reports, not
proof of authenticated approval. This file records provenance, not a license grant.
