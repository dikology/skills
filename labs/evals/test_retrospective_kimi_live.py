"""One real Kimi Code 2.7.2 headless retrospective in disposable native homes.

    RETROSPECTIVE_KIMI_LIVE=1 python3 -u -m unittest labs.evals.test_retrospective_kimi_live -v

Set RETROSPECTIVE_KIMI_BINARY to a 2.7.2 executable when `kimi` on PATH is another version.
Every prompt, session, destination and retrospective state file belongs to the test. Real
configuration is used only to seed model access; no real conversation or generic agent resource
is read, and the fake `gh` makes a live GitHub write impossible.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "labs" / "retrospective" / "scripts"))
from adapters import kimi as kimi_adapter  # noqa: E402

from labs.evals.test_retrospective_kimi import message, prompt  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / "labs" / "retrospective"
NOTE_TEXT = "Contract tests must run with --no-cache after a schema change."
SEEDED = "# Synthetic project\n\nNothing learned yet.\n"
TURN_TIMEOUT = 900


def flat(text):
    return " ".join(str(text or "").split())


class KimiLiveRetrospectiveTest(unittest.TestCase):
    def setUp(self):
        if os.environ.get("RETROSPECTIVE_KIMI_LIVE") != "1":
            self.skipTest("set RETROSPECTIVE_KIMI_LIVE=1 to spend a real Kimi session")
        self.binary = os.environ.get("RETROSPECTIVE_KIMI_BINARY", "kimi")
        if not shutil.which(self.binary):
            self.skipTest(f"{self.binary} is not on PATH")
        version = subprocess.run(
            [self.binary, "--version"], text=True, capture_output=True, check=False, timeout=30,
        )
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertEqual(version.stdout.strip(), "2.7.2", "the live evidence requires Kimi Code 2.7.2")
        self.adapter = run_evals.process_adapter("kimi")
        self.temp_dir = tempfile.TemporaryDirectory()
        if os.environ.get("RETROSPECTIVE_KIMI_KEEP") == "1":
            print(f"keeping the run's root: {self.temp_dir.name}", flush=True)
        else:
            self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.real_home = self.adapter.real_home()
        self.home = self.adapter.make_isolated_home(self.root, self.real_home)
        self.env = self.adapter.agent_env(self.home)
        if not self.adapter.login_found(self.real_home, self.env):
            self.skipTest("no model login to seed an isolated Kimi home with")

        self.project = self.root / "synthetic-project"
        self.project.mkdir()
        self.instructions = self.project / ".kimi-code" / "AGENTS.md"
        self.instructions.parent.mkdir()
        self.instructions.write_text(SEEDED, encoding="utf-8")
        shutil.copytree(CANDIDATE, self.project / ".kimi-code" / "skills" / "retrospective")

        self.gh_log = self.root / "gh.log"
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        gh = fake_bin / "gh"
        gh.write_text(
            "#!/bin/bash\nprintf '%s\\n' \"$*\" >> \"$FAKE_GH_LOG\"\n"
            "echo 'refused: this run has no GitHub access' >&2\nexit 1\n",
            encoding="utf-8",
        )
        gh.chmod(0o755)
        self.state = self.root / "retrospective-state"
        self.env.update({
            "PATH": f"{fake_bin}{os.pathsep}{self.env.get('PATH', '')}",
            "FAKE_GH_LOG": str(self.gh_log),
            "RETROSPECTIVE_STATE_DIR": str(self.state),
        })

        self.seeded = ["session-synthetic-0001", "session-synthetic-0002"]
        today = date.today().isoformat()
        prompts = [
            ["run the contract tests", "no, the cache hid the schema change", "file the fix under contracts"],
            ["check the schema contract", "the cached fixture hid it again", "keep the synthetic project rule"],
        ]
        for index, session_id in enumerate(self.seeded):
            records = []
            for turn, text in enumerate(prompts[index]):
                records.append(prompt(text, self.millisecond(today, turn * 2)))
                records.append(message("assistant", self.millisecond(today, turn * 2 + 1), "synthetic answer"))
            self.seed_session(session_id, f"wd_synthetic_{index}", records)

        self.session = None
        self.replies = []
        self.versions = []

    @staticmethod
    def millisecond(day, minute):
        from datetime import datetime, timezone

        moment = datetime.fromisoformat(f"{day}T09:{minute:02}:00+00:00")
        return int(moment.replace(tzinfo=timezone.utc).timestamp() * 1000)

    def seed_session(self, session_id, workspace_id, records):
        directory = self.home / "sessions" / workspace_id / session_id
        wire = directory / "agents" / "main" / "wire.jsonl"
        wire.parent.mkdir(parents=True)
        wire.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
        (directory / "state.json").write_text(json.dumps({
            "title": "Synthetic schema work", "cwd": str(self.project),
            "createdAt": date.today().isoformat() + "T09:00:00.000Z",
            "updatedAt": date.today().isoformat() + "T10:00:00.000Z",
        }), encoding="utf-8")
        with (self.home / "session_index.jsonl").open("a", encoding="utf-8") as index:
            index.write(json.dumps({
                "sessionId": session_id, "sessionDir": str(directory), "workDir": str(self.project),
            }) + "\n")

    def live_wire(self):
        if not self.session:
            return None
        paths = list((self.home / "sessions").glob(f"*/{self.session}/agents/main/wire.jsonl"))
        return paths[0] if paths else None

    def turn(self, text):
        argv = self.adapter.session_argv(text, resume=self.session)
        argv[0] = self.binary
        try:
            proc = subprocess.run(
                argv, cwd=self.project, capture_output=True, text=True,
                timeout=TURN_TIMEOUT, env=self.env,
            )
        except subprocess.TimeoutExpired:
            self.fail(f"the live turn timed out after {TURN_TIMEOUT}s: {text[:60]}")
        self.assertEqual(proc.returncode, 0, f"turn failed: {(proc.stderr or '')[-1000:]}")
        read = self.adapter.read_turn(proc.stdout, env=self.env)
        self.assertFalse(read["is_error"], read["error"])
        if self.session:
            self.assertEqual(read["session_id"], self.session, "a turn resumed as a stranger")
        self.session = read["session_id"]
        self.replies.append(read["text"])
        self.versions.extend(
            json.loads(line).get("version") for line in proc.stdout.splitlines()
            if line.strip() and json.loads(line).get("type") == "system.version"
        )
        print(f"\n--- Kimi turn {len(self.replies)} ---\n{read['text']}", flush=True)
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
        self.turn(f"/skill:retrospective note {NOTE_TEXT} — learned in the synthetic project, file it")

        filed = self.notes()
        self.assertEqual(len(filed), 1, filed)
        self.assertEqual(filed[0]["adapter"], "kimi")
        self.assertEqual(filed[0]["session_id"], self.session)
        self.assertTrue(filed[0]["workspace_id"])
        self.assertEqual(filed[0]["text"], NOTE_TEXT)
        self.assertLessEqual(len(filed[0]["context"]), 240)
        self.assertEqual(self.instructions.read_text(encoding="utf-8"), SEEDED)

        report = self.turn(
            "/skill:retrospective over the last 14 days in synthetic-project, including temporary "
            "projects. Propose Rule candidates for this project's Kimi-specific instructions only: "
            "never Memory, never an Issue. Print the report verbatim and nothing else."
        )
        self.assertIn("Retro candidates", report)
        self.assertIn("Reply with numbers (e.g. 1 3), all, or none.", report)
        self.assertTrue(any(session_id[:8] in report for session_id in self.seeded), report[:1500])
        self.assertTrue(filed[0]["id"] in report or flat(NOTE_TEXT).lower() in flat(report).lower())
        cited = re.search(r'1\.\s+\S[^\n]*\n\s+"((?:.|\n)*?)"\n\s+from:', report)
        self.assertIsNotNone(cited, f"no exact proposed text under candidate 1:\n{report[:1500]}")
        proposed = flat(cited.group(1))
        self.assertEqual(self.instructions.read_text(encoding="utf-8"), SEEDED)

        self.turn("1")

        written = self.instructions.read_text(encoding="utf-8")
        self.assertNotEqual(written, SEEDED)
        self.assertIn("no-cache", flat(written).lower())
        self.assertIn(proposed, flat(written))
        self.assertEqual(self.notes(), [])
        reviewed = self.ledger("reviewed.txt")
        self.assertTrue(reviewed)
        self.assertTrue(all(line.startswith("kimi:") for line in reviewed), reviewed)
        self.assertTrue(all(len(line.split(":", 1)[1]) > 8 for line in reviewed), reviewed)
        self.assertFalse(self.gh_log.exists(), "the run called gh")
        self.assertFalse((self.root / "os-home" / ".agents").exists(), "generic agent resources leaked")
        self.assertFalse((self.home / "memories").exists(), "the run wrote a memory store")

        wire = self.live_wire()
        self.assertIsNotNone(wire, "the live session recorded no native main wire")
        parsed, warnings = kimi_adapter.parse_session({
            "session_id": self.session, "workspace_id": wire.parents[3].name,
            "directory": wire.parents[2], "work_dir": str(self.project),
        })
        self.assertEqual(parsed["session_id"], self.session)
        self.assertEqual(parsed["project_path"], str(self.project.resolve()))
        self.assertIn("retrospective", parsed["skills"], "native skill activation was not retained")
        self.assertEqual(self.versions, ["2.7.2"] * 3)

        print(
            "\n--- live Kimi retrospective evidence ---\n"
            f"kimi session {self.session}\nworkspace: {filed[0]['workspace_id']}\n"
            f"transcript: {wire}\nturns: {len(self.replies)}\n"
            f"skills: {parsed['skills']}\nparse warnings: {warnings}\n"
            f"reviewed: {reviewed}\ndeclined: {self.ledger('declined.txt')}\n"
            f"Kimi AGENTS.md now:\n{written}"
        )


if __name__ == "__main__":
    unittest.main()
