import concurrent.futures
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin/decision-ledger"


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="decision ledger ")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.store = self.base / "storage with spaces"
        self.database = self.store / "decisions.sqlite3"
        self.call("init")

    def call(self, *args, expected=0, data=None, store=None, preexec=None, stderr=subprocess.PIPE):
        result = subprocess.run([str(CLI), "--dir", str(store or self.store), *args],
                                input=data, stdout=subprocess.PIPE, stderr=stderr,
                                preexec_fn=preexec, timeout=20)
        self.assertEqual(result.returncode, expected, repr(result.stdout) + repr(result.stderr))
        if result.stderr:
            self.assertNotIn(b"Traceback", result.stderr)
        return json.loads(result.stdout) if result.stdout else None

    def test_explicit_storage_and_missing_reads_fail_closed(self):
        env = dict(os.environ)
        env.pop("DECISION_LEDGER_DIR", None)
        result = subprocess.run([str(CLI), "open"], env=env, capture_output=True)
        self.assertEqual(result.returncode, 2)
        missing = self.base / "missing"
        self.call("open", store=missing, expected=4)
        self.assertFalse(missing.exists())

    def test_empty_initialized_ledger_has_empty_open_queue(self):
        self.assertEqual(self.call("open"), [])
        self.assertEqual(self.call("list"), [])
        self.assertEqual(self.call("validate"), {"valid": True, "records": 0})
        again = self.call("init")
        self.assertFalse(again["initialized"])

    def test_words_and_interpretation_remain_separate(self):
        words = 'Keep "version 2"; do not rewrite my wording.'
        event = self.call("record", words, "--interpretation", "Use the second version", "--actor", "reviewer")
        self.assertEqual(event["words"], words)
        self.assertEqual(event["interpretation"], "Use the second version")
        self.assertEqual(self.call("list"), [event])
        self.assertEqual(event["kind"], "decision")
        self.assertEqual(event["source"], "chat")

    def test_stdin_preserves_unicode_crlf_and_trailing_whitespace(self):
        words = "Don't reinterpret this — café\r\nSecond line.\n  \n\n"
        event = self.call("record", "--words-stdin", data=words.encode())
        self.assertEqual(event["words"].encode(), words.encode())
        self.assertEqual(self.call("history", event["id"])["root"]["words"], words)

    def test_words_file_avoids_argument_limits(self):
        words = "large original text λ\n" * 15000 + "trailing  \n"
        source = self.base / "quoted words.txt"
        source.write_bytes(words.encode())
        event = self.call("record", "--words-file", str(source), "--source", "transcript")
        self.assertEqual(event["words"], words)
        self.assertEqual(self.call("list")[0]["words"], words)

    def test_ask_answer_and_repeated_answer_corrections(self):
        question = self.call("ask", "Proceed with version 2?", "--actor", "builder")
        self.assertEqual(self.call("open"), [question])
        first = self.call("answer", question["id"], "Yes.", "--interpretation", "Proceed")
        second = self.call("answer", question["id"], "Wait until review.", "--source", "paste")
        repeated = self.call("answer", question["id"], "Wait until review.")
        self.assertEqual(self.call("open"), [])
        history = self.call("history", first["id"])
        self.assertEqual(history["events"], [question, first, second, repeated])
        self.assertEqual(history["current"], repeated)
        self.assertEqual(history["root"], question)
        self.assertEqual(len({event["id"] for event in history["events"]}), 4)

    def test_decision_corrections_preserve_every_original(self):
        first = self.call("record", "Use version 2.")
        second = self.call("record", "Use version 3 instead.", "--corrects", first["id"])
        third = self.call("record", "Keep version 3 with review.", "--corrects", second["id"])
        history = self.call("history", second["id"])
        self.assertEqual(history["root"], first)
        self.assertEqual(history["current"], third)
        self.assertEqual(history["events"], [first, second, third])

    def test_unknown_and_wrong_kind_references_do_not_append(self):
        decision = self.call("record", "A decision")
        question = self.call("ask", "A question?")
        before = self.call("list")
        self.call("answer", "0" * 32, "Unknown", expected=4)
        self.call("answer", "", "Empty reference", expected=4)
        self.call("record", "Empty correction", "--corrects", "", expected=4)
        self.call("answer", decision["id"], "Wrong kind", expected=4)
        self.call("record", "Wrong correction", "--corrects", question["id"], expected=4)
        self.call("history", "../not-an-id", expected=4)
        self.assertEqual(self.call("list"), before)

    def test_historical_timestamp_does_not_override_commit_order(self):
        question = self.call("ask", "Which version?")
        self.call("answer", question["id"], "Version 2", "--at", "2025-01-01T00:00:00Z")
        later = self.call("answer", question["id"], "Version 3", "--at", "2024-01-01T00:00:00Z")
        self.assertEqual(later["occurred_at"], "2024-01-01T00:00:00.000000Z")
        self.assertEqual(self.call("history", question["id"])["current"], later)

    def test_metadata_types_and_filters(self):
        event = self.call("record", "Typed metadata", "--actor", "reviewer", "--meta", "urgent=true",
                          "--meta", "count=3", "--meta", "leading=007", "--meta", "empty=")
        self.assertEqual(event["metadata"], {"urgent": True, "count": 3, "leading": "007", "empty": ""})
        self.assertEqual(self.call("list", "--actor", "reviewer", "--kind", "decision"), [event])
        self.assertEqual(self.call("list", "--actor", "absent"), [])

    def test_invalid_input_is_rejected_before_write(self):
        cases = [("record", " "), ("record", "x", "--words-stdin"),
                 ("record", "x", "--interpretation", "two\nlines"),
                 ("record", "x", "--at", "2025-02-30T00:00:00Z"),
                 ("record", "x", "--meta", "words=override"),
                 ("record", "x", "--meta", "a=1", "--meta", "a=2"),
                 ("record", "x", "--actor", "bad actor"),
                 ("ask", "x", "--interpretation", "not supported")]
        for args in cases:
            with self.subTest(args=args):
                self.call(*args, expected=2)
        self.call("record", "--words-stdin", data=b"invalid\xff", expected=2)
        self.call("record", "--words-stdin", data=b"nul\0text", expected=2)
        self.assertEqual(self.call("list"), [])

    def test_words_are_never_executed(self):
        marker = self.base / "must-not-exist"
        text = "$(touch " + str(marker) + "); `touch ignored`; DROP TABLE events;"
        event = self.call("record", text)
        self.assertEqual(event["words"], text)
        self.assertFalse(marker.exists())
        self.assertEqual(self.call("validate")["records"], 1)

    def test_concurrent_records_have_unique_ordered_identifiers(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            events = list(pool.map(lambda i: self.call("record", "record " + str(i)), range(24)))
        self.assertEqual(len({event["id"] for event in events}), 24)
        rows = self.call("list")
        self.assertEqual([event["seq"] for event in rows], list(range(1, 25)))
        self.assertEqual({event["words"] for event in rows}, {"record " + str(i) for i in range(24)})

    def test_concurrent_answers_keep_every_answer_and_resolve_one_question(self):
        question = self.call("ask", "Choose one?")
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            answers = list(pool.map(lambda i: self.call("answer", question["id"], "choice " + str(i)), range(12)))
        history = self.call("history", question["id"])
        self.assertEqual(len(history["events"]), 13)
        self.assertEqual(history["current"], max(answers, key=lambda row: row["seq"]))
        self.assertEqual(self.call("open"), [])

    def test_contention_fails_closed_without_receipt(self):
        connection = sqlite3.connect(self.database)
        self.addCleanup(connection.close)
        connection.execute("BEGIN IMMEDIATE")
        self.call("--timeout", "0", "record", "must not land", expected=5)
        connection.rollback()
        self.assertEqual(self.call("list"), [])

    def test_database_guards_refuse_update_and_delete(self):
        event = self.call("record", "Original stays")
        with sqlite3.connect(self.database) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE events SET words='changed'")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM events")
        self.assertEqual(self.call("list"), [event])

    def test_unknown_schema_and_non_database_fail_closed(self):
        with sqlite3.connect(self.database) as connection:
            connection.execute("PRAGMA user_version=99")
        self.call("open", expected=3)
        self.call("record", "refuse", expected=3)
        bad = self.base / "not database"
        bad.mkdir()
        (bad / "decisions.sqlite3").write_bytes(b"not a database")
        self.call("open", store=bad, expected=3)
        self.call("init", store=bad, expected=3)
        self.assertEqual((bad / "decisions.sqlite3").read_bytes(), b"not a database")

    def test_removed_guard_or_corrupt_row_cannot_look_like_an_empty_queue(self):
        self.call("ask", "still pending?")
        with sqlite3.connect(self.database) as connection:
            connection.execute("DROP TRIGGER events_no_update")
        self.call("open", expected=3)
        self.call("record", "refuse", expected=3)

    def test_dangling_reference_is_detected_even_if_external_writer_disabled_foreign_keys(self):
        event = self.call("record", "Original")
        with sqlite3.connect(self.database) as connection:
            values = connection.execute("SELECT * FROM events").fetchone()
            values = list(values)
            values[0] = 2
            values[1] = "a" * 32
            values[2] = "answer"
            values[9] = "b" * 32
            values[11] = "b" * 32
            connection.execute("INSERT INTO events VALUES (" + ",".join("?" for _ in values) + ")", values)
        self.call("open", expected=3)
        self.call("answer", event["id"], "refuse", expected=3)

    def test_closed_stdout_cannot_claim_receipt_success(self):
        self.call("record", "committed without receipt", expected=6, preexec=lambda: os.close(1))
        self.assertEqual(self.call("list")[0]["words"], "committed without receipt")
        self.call("open", expected=6, preexec=lambda: os.close(1))

    def test_broken_stdout_pipe_returns_failure_after_commit(self):
        reader, writer = os.pipe()
        os.close(reader)
        try:
            result = subprocess.run([str(CLI), "--dir", str(self.store), "record", "broken output"],
                                    stdout=writer, stderr=subprocess.PIPE, timeout=10)
        finally:
            os.close(writer)
        self.assertEqual(result.returncode, 6)
        self.assertEqual(self.call("list")[0]["words"], "broken output")

    def test_closed_stderr_preserves_reference_error(self):
        self.call("answer", "0" * 32, "missing", expected=4, preexec=lambda: os.close(2))

    def test_symlink_or_fifo_database_is_rejected(self):
        target = self.base / "outside.sqlite3"
        target.write_bytes(b"untouched")
        store = self.base / "linked store"
        store.mkdir()
        (store / "decisions.sqlite3").symlink_to(target)
        self.call("open", store=store, expected=3)
        self.assertEqual(target.read_bytes(), b"untouched")
        (store / "decisions.sqlite3").unlink()
        os.mkfifo(store / "decisions.sqlite3")
        self.call("open", store=store, expected=3)

    def test_install_is_independent(self):
        staged = self.base / "install with spaces"
        result = subprocess.run(["make", "install", "DESTDIR=" + str(staged), "PREFIX=/opt/decisions"],
                                cwd=ROOT, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = staged / "opt/decisions/bin/decision-ledger"
        result = subprocess.run([str(installed), "--dir", str(self.store), "open"], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])

    def test_sigkill_before_commit_rolls_back_entire_event(self):
        original = self.call("record", "Original transaction")
        marker = self.base / "inserted-uncommitted"
        runner = r'''
import os,pathlib,runpy,signal,sqlite3,sys
namespace=runpy.run_path(sys.argv[1])
real=sqlite3.connect
class Paused(sqlite3.Connection):
    def execute(self, sql, *args, **kwargs):
        result=super().execute(sql,*args,**kwargs)
        if sql.startswith("INSERT INTO events"):
            pathlib.Path(sys.argv[3]).touch()
            os.kill(os.getpid(),signal.SIGSTOP)
        return result
def connection(*args,**kwargs):
    kwargs['factory']=Paused
    return real(*args,**kwargs)
sqlite3.connect=connection
path=namespace['database_path'](sys.argv[2])
args=type('Arguments',(),{'action':'record','actor':None,'source':'chat','corrects':None})()
namespace['append'](path,10,args,('Uncommitted new words',None,{},None))
'''
        process = subprocess.Popen([sys.executable, "-c", runner, str(CLI), str(self.store), str(marker)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < deadline:
                self.assertIsNone(process.poll())
                time.sleep(.01)
            self.assertTrue(marker.exists())
            process.kill()
            process.communicate(timeout=5)
            self.assertEqual(self.call("list"), [original])
            next_event = self.call("record", "After recovery")
            self.assertEqual(next_event["seq"], 2)
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)

    def test_term_inside_transaction_rolls_back_and_returns_143(self):
        marker = self.base / "term-in-transaction"
        runner = r"""
import os,pathlib,runpy,signal,sqlite3,sys
namespace=runpy.run_path(sys.argv[1]);real=sqlite3.connect
marker=pathlib.Path(sys.argv[3])
class Paused(sqlite3.Connection):
    def execute(self, sql, *args, **kwargs):
        result=super().execute(sql,*args,**kwargs)
        if sql.startswith("INSERT INTO events"):
            marker.touch();os.kill(os.getpid(),signal.SIGSTOP)
        return result
def connection(*args,**kwargs):
    kwargs['factory']=Paused
    return real(*args,**kwargs)
sqlite3.connect=connection
sys.argv=[sys.argv[1],'--dir',sys.argv[2],'record','Interrupted words']
sys.exit(namespace['entry']())
"""
        process = subprocess.Popen([sys.executable, "-c", runner, str(CLI), str(self.store), str(marker)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < deadline:
                self.assertIsNone(process.poll());time.sleep(.01)
            self.assertTrue(marker.exists())
            process.terminate()
            os.kill(process.pid, signal.SIGCONT)
            out, err = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 143, out + err)
            self.assertEqual(out, b"")
            self.assertEqual(self.call("list"), [])
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)

    def test_interrupted_initialization_cannot_publish_an_incomplete_database(self):
        store = self.base / "interrupted initialization"
        marker = self.base / "ready-to-publish"
        runner = r"""
import os,pathlib,runpy,signal,sys
namespace=runpy.run_path(sys.argv[1]);real=os.link
marker=pathlib.Path(sys.argv[3])
def pause(source,target):
    marker.touch();os.kill(os.getpid(),signal.SIGSTOP)
    return real(source,target)
os.link=pause
sys.argv=[sys.argv[1],'--dir',sys.argv[2],'init']
sys.exit(namespace['entry']())
"""
        process = subprocess.Popen([sys.executable, "-c", runner, str(CLI), str(store), str(marker)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < deadline:
                self.assertIsNone(process.poll());time.sleep(.01)
            self.assertTrue(marker.exists())
            process.kill();out, _ = process.communicate(timeout=5)
            self.assertEqual(out, b"")
            self.assertFalse((store / "decisions.sqlite3").exists())
            self.call("open", store=store, expected=4)
            self.assertTrue(self.call("init", store=store)["initialized"])
            self.assertEqual(self.call("open", store=store), [])
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)

    def test_private_database_mode_and_no_accidental_environment_identity(self):
        self.assertEqual(self.database.stat().st_mode & 0o777, 0o600)
        event = self.call("record", "Explicit attribution only")
        self.assertIsNone(event["actor"])
        self.assertNotIn("machine", event)

    def test_invalid_words_in_an_external_insert_block_reads_and_writes(self):
        self.call("record", "Valid original")
        with sqlite3.connect(self.database) as connection:
            values = list(connection.execute("SELECT * FROM events").fetchone())
            values[0], values[1], values[3], values[11] = 2, "c" * 32, "  ", "c" * 32
            connection.execute("INSERT INTO events VALUES (" + ",".join("?" for _ in values) + ")", values)
        self.call("open", expected=3)
        self.call("record", "Do not append", expected=3)

    def insert_external_metadata(self, metadata):
        with sqlite3.connect(self.database) as connection:
            values = list(connection.execute("SELECT * FROM events ORDER BY seq LIMIT 1").fetchone())
            values[0], values[1], values[11], values[12] = 2, "d" * 32, "d" * 32, metadata
            connection.execute("INSERT INTO events VALUES (" + ",".join("?" for _ in values) + ")", values)

    def test_duplicate_metadata_keys_never_silently_replace_a_value(self):
        self.call("record", "Preserved original")
        ambiguous = '{"detail":"original","detail":"silently replaced"}'
        self.insert_external_metadata(ambiguous)
        before = self.database.read_bytes()
        for command in (("list",), ("open",), ("validate",), ("record", "must not append")):
            self.call(*command, expected=3)
        self.assertEqual(self.database.read_bytes(), before)
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT metadata FROM events WHERE seq=2").fetchone()[0], ambiguous)
            self.assertEqual(connection.execute("SELECT count(*) FROM events").fetchone()[0], 2)

    def test_deeply_nested_metadata_returns_storage_failure_without_traceback(self):
        self.call("record", "Original")
        self.insert_external_metadata("[" * 10000 + "0" + "]" * 10000)
        before = self.database.read_bytes()
        self.call("open", expected=3)
        self.call("record", "must not append", expected=3)
        self.assertEqual(self.database.read_bytes(), before)

    def test_unknown_objects_cannot_hide_behind_a_sqlite_like_name(self):
        with sqlite3.connect(self.database) as connection:
            connection.execute("CREATE TABLE sqlitex_hidden (value TEXT)")
        self.call("validate", expected=3)
        self.call("open", expected=3)


if __name__ == "__main__":
    unittest.main()
