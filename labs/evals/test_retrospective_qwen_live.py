"""One real Qwen headless session, in a home of its own, end to end.

The fixture suite says what the adapter does with transcripts. This says the adapter works
inside the CLI it claims to support: the Skill installed the way a Qwen user installs it, a
Retro note filed by a live turn, a report the agent built from what it discovered natively,
a numeric approval, a write to a synthetic destination, and the bookkeeping that followed.

It draws on a model, so it is not part of the offline suite:

    RETROSPECTIVE_QWEN_LIVE=1 python3 -u -m unittest labs.evals.test_retrospective_qwen_live -v

Everything it touches — the Qwen home, the retrospective state, the vault, the destinations
and the `gh` on PATH — belongs to the run and is thrown away with it. No real prompt body,
credential, memory or retrospective state is read, and no live GitHub write is possible.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, str(Path(__file__).parent))
import run_evals  # noqa: E402

from labs.evals.test_retrospective_qwen import human  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / "labs" / "retrospective"
NOTE_TEXT = "Contract tests must run with --no-cache after a schema change."
SEEDED = "# Synthetic project\n\nNothing learned yet.\n"
TURN_TIMEOUT = 900


def flat(text):
    return " ".join(str(text or "").split())


class QwenLiveRetrospectiveTest(unittest.TestCase):
    def setUp(self):
        if os.environ.get("RETROSPECTIVE_QWEN_LIVE") != "1":
            self.skipTest("set RETROSPECTIVE_QWEN_LIVE=1 to spend a real Qwen run")
        if not shutil.which(run_evals.BINARY):
            self.skipTest(f"{run_evals.BINARY} is not on PATH")
        self.temp_dir = tempfile.TemporaryDirectory()
        if os.environ.get("RETROSPECTIVE_QWEN_KEEP") == "1":
            print(f"keeping the run's root: {self.temp_dir.name}", flush=True)
        else:
            self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.real_home = run_evals.real_home()
        self.home = run_evals.make_isolated_home(self.root, self.real_home)
        env = run_evals.agent_env(self.home)
        if not run_evals.login_found(self.real_home, env):
            self.skipTest("no model login to seed an isolated Qwen home with")

        # A synthetic project: the originating project, the destination, and the only thing
        # this run may write to.
        self.project = self.root / "synthetic-vault"
        self.project.mkdir()
        self.instructions = self.project / "QWEN.md"
        self.instructions.write_text(SEEDED, encoding="utf-8")
        shutil.copytree(CANDIDATE, self.project / ".qwen" / "skills" / "retrospective")

        # A `gh` that only ever logs: a live GitHub write is impossible from here.
        self.gh_log = self.root / "gh.log"
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        gh = fake_bin / "gh"
        gh.write_text(
            "#!/bin/bash\n"
            "printf '%s\\n' \"$*\" >> \"$FAKE_GH_LOG\"\n"
            "echo 'refused: this run has no GitHub access' >&2\n"
            "exit 1\n",
            encoding="utf-8",
        )
        gh.chmod(0o755)

        self.state = self.root / "retrospective-state"
        self.env = {
            **env,
            "HOME": str(self.root),
            "PATH": f"{fake_bin}{os.pathsep}{env.get('PATH', '')}",
            "FAKE_GH_LOG": str(self.gh_log),
            "RETROSPECTIVE_STATE_DIR": str(self.state),
        }

        # Two synthetic earlier sessions in the run's own Qwen home, so the cross-session
        # review has evidence no real conversation supplied.
        today = date.today().isoformat()
        chats = self.home / "projects" / "-synthetic-vault" / "chats"
        chats.mkdir(parents=True)
        self.seeded = ["feedface-0001", "bedbed-0002"]
        for index, session_id in enumerate(self.seeded):
            records = [
                human("run the contract tests", f"{today}T09:0{index}:00Z", cwd=str(self.project)),
                human("no, the cache hid the schema change", f"{today}T09:1{index}:00Z", cwd=str(self.project)),
                human("file the fix under contracts", f"{today}T09:2{index}:00Z", cwd=str(self.project)),
            ]
            (chats / f"{session_id}.jsonl").write_text(
                "\n".join(
                    json.dumps({**record, "sessionId": session_id, "uuid": f"{session_id}-{step}"})
                    for step, record in enumerate(records)
                )
                + "\n",
                encoding="utf-8",
            )

        self.session = None
        self.replies = []
        self.tokens = 0
        self.skills = []
        self.no_init = False
        self.mcp = []

    def turn(self, text):
        """One human turn in the live session, asserting the turn itself held."""
        argv = run_evals.session_argv(text, resume=self.session)
        try:
            proc = subprocess.run(
                argv, cwd=self.project, capture_output=True, text=True,
                timeout=TURN_TIMEOUT, env=self.env,
            )
        except subprocess.TimeoutExpired:
            self.fail(f"the live turn timed out after {TURN_TIMEOUT}s: {text[:60]}")
        try:
            read = run_evals.read_turn(proc.stdout)
        except ValueError:
            self.fail(f"the live turn printed no result event: {(proc.stderr or proc.stdout)[-800:]}")
        self.assertFalse(
            proc.returncode != 0 or read["is_error"],
            f"turn failed: {read.get('error') or (proc.stderr or '')[-800:]}",
        )
        if self.session:
            self.assertEqual(read["session_id"], self.session, "a turn resumed as a stranger")
        self.session = read["session_id"] or self.session
        self.no_init = self.no_init or not read["init_reported"]
        self.mcp = self.mcp or read["mcp_servers"]
        self.tokens += read["tokens"]
        self.skills += read["skills"]
        self.replies.append(read["text"])
        print(f"\n--- agent turn {len(self.replies)} ---\n{read['text']}", flush=True)
        return read["text"]

    def notes(self):
        path = self.state / "inbox.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def ledger(self, name):
        path = self.state / name
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    def test_live_session_completes_note_report_approval_write_and_bookkeeping(self):
        self.turn(f"/retrospective note {NOTE_TEXT} — learned in the synthetic vault, file it")

        filed = self.notes()
        self.assertEqual(len(filed), 1, filed)
        self.assertEqual(filed[0]["adapter"], "qwen")
        self.assertEqual(filed[0]["session_id"], self.session, "the note carries no native identity")
        self.assertEqual(filed[0]["text"], NOTE_TEXT)
        self.assertIn("synthetic-vault", filed[0]["project"])
        self.assertEqual(self.instructions.read_text(encoding="utf-8"), SEEDED, "note mode wrote a destination")

        report = self.turn(
            "/retrospective over the last 14 days in synthetic-vault, including temporary "
            "projects. Propose Rule candidates for this project's QWEN.md only: never Memory, "
            "never an Issue. Print the report verbatim and nothing else."
        )
        self.assertIn("Retro candidates", report)
        self.assertIn("Reply with numbers (e.g. 1 3), all, or none.", report)
        self.assertTrue(
            any(session_id[:8] in report for session_id in self.seeded),
            f"the report cites neither synthetic session:\n{report[:1500]}",
        )
        self.assertTrue(
            filed[0]["id"] in report or flat(filed[0]["text"]).lower() in flat(report).lower(),
            f"the report neither names nor quotes the open Retro note:\n{report[:1500]}",
        )
        cited = re.search(r'1\.\s+\S[^\n]*\n\s+"((?:.|\n)*?)"\n\s+from:', report)
        self.assertIsNotNone(cited, f"no exact proposed text under candidate 1:\n{report[:1500]}")
        proposed = flat(cited.group(1))
        self.assertEqual(self.instructions.read_text(encoding="utf-8"), SEEDED, "the report wrote before approval")
        self.assertEqual([note["id"] for note in self.notes()], [filed[0]["id"]])

        self.turn("1")

        written = self.instructions.read_text(encoding="utf-8")
        self.assertNotEqual(written, SEEDED)
        self.assertIn("no-cache", flat(written).lower())
        self.assertIn(proposed, flat(written))
        self.assertEqual(self.notes(), [], "the handled note was not cleared")
        reviewed = self.ledger("reviewed.txt")
        self.assertTrue(reviewed, "no session was marked reviewed")
        self.assertTrue(all(line.startswith("qwen:") for line in reviewed), reviewed)
        self.assertTrue(
            all(len(line.split(":", 1)[1]) > 8 for line in reviewed),
            f"a session ID was truncated: {reviewed}",
        )
        self.assertFalse(self.gh_log.exists(), "the run called gh")
        self.assertFalse((self.home / "memories").exists(), "the run wrote Qwen memories")
        self.assertFalse((self.project / "MEMORY.md").exists(), "the run wrote a memory index")
        self.assertTrue(str(self.state).startswith(str(self.root)))
        self.assertFalse(self.mcp, "the session loaded an MCP server")
        self.assertFalse(self.no_init, "a turn printed no init event: isolation not proven")
        self.assertIsNone(
            run_evals.check_run(
                "retrospective",
                {
                    "init_reported": True,
                    "mcp_servers": self.mcp,
                    "skills_invoked": sorted(set(self.skills)),
                },
            )
        )

        print(
            "\n--- live Qwen retrospective evidence ---\n"
            f"qwen: {run_evals.BINARY} session {self.session}\n"
            f"turns: {len(self.replies)}  tokens: {self.tokens}\n"
            f"skills invoked: {sorted(set(self.skills))}\n"
            f"reviewed: {reviewed}\n"
            f"declined: {self.ledger('declined.txt')}\n"
            f"QWEN.md now:\n{written}"
        )


if __name__ == "__main__":
    unittest.main()
