# Storage, interruption, and recovery

The explicit directory contains `decisions.sqlite3`. New directories use mode 0700
and the database is initially created with mode 0600. Existing directory permissions
are not changed. The final storage directory/database cannot be symlinks, and the
database must be a regular file with one directory entry. Ancestor directories and
all writers must be trusted and stable. Use a local filesystem on one machine;
network filesystems, hostile concurrent path replacement, and cross-machine sync
are unsupported.

Initialization builds and validates a complete temporary SQLite database before
publishing it through an exclusive same-directory hard link. It does not overwrite
an existing file, even if that file is not a recognized database. An interrupted
initialization before publication leaves no visible ledger. A subsequent `init`
can create a fresh one; an unpublished `.decision-ledger-init-*` file may remain
after SIGKILL and can be inspected/removed once every initializer has stopped.

A SIGKILL between publication and unlinking the temporary name can leave the valid
database with an extra hard link. Commands refuse that state instead of opening a
potentially aliased SQLite database. Stop all users, verify that the remaining
`.decision-ledger-init-*` name has the same device/inode as `decisions.sqlite3`,
remove only that initialization link, and run `validate`. Never remove or rename
an active database or journal to bypass a lock.

Writes use SQLite `BEGIN IMMEDIATE`, foreign-key checks, DELETE rollback journals,
and `synchronous=FULL`. Reference lookup, sequence assignment, and insertion occur
inside the same serialized transaction. A waiting writer either obtains the SQLite
lock or returns exit 5; there is no unlocked fallback. Reads use a transaction for
a consistent snapshot. Every command validates the complete ledger, so validation
cost and memory grow with record count. This is intended for modest local decision
history, not a high-throughput event stream.

A successful append commits before printing its event receipt. A process can die,
be signalled, or lose stdout after the commit. Absence of a receipt therefore does
not prove absence of a record. Inspect `list`/`history` before retrying an uncertain
write. Retries are not automatically deduplicated; repeated answers deliberately
remain separate history. Successfully writing stdout does not prove that a pipe's
downstream consumer processed the receipt.

Before-commit interruption leaves the previous logical ledger intact. SQLite may
leave a hot rollback journal after a crash; the next connection can perform normal
SQLite recovery. Do not delete that journal. Handled TERM/HUP/keyboard interruption
rolls back an active transaction when Python regains control. A SQLite call can
delay signal handling until its configured contention wait completes. SIGKILL
cannot run Python cleanup. These are tested process-crash behaviors, not a formal
claim about every filesystem, storage device, power failure, or hardware cache.

Malformed/unrecognized databases, changed schemas, missing guards, invalid records,
and dangling references fail closed. The tool does not reset, migrate, repair, or
silently drop such data. Preserve a backup and investigate the corruption; restoring
a known-good complete database is an operator decision.

For backups, stop all callers, let a normal connection finish any SQLite recovery,
run `validate`, and then copy the database. Keep the original until the copied
ledger has also passed validation. No automatic retention or pruning is provided.
Words/files are read as data and inserted with SQL parameters; they are never
executed as shell, Python, SQL, or model instructions.
