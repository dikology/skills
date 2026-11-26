#!/usr/bin/env python3

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import uuid

from adapters import get_adapter


def state_directory():
    configured = os.environ.get("RETROSPECTIVE_STATE_DIR")
    return Path(configured) if configured else Path.home() / ".retrospective"


def save_note(adapter, adapter_name, text, context):
    identity = adapter.current_session()
    note = {
        "id": str(uuid.uuid4()),
        "adapter": adapter_name,
        "session_id": identity["session_id"],
        "project": str(Path.cwd()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "context": context,
    }
    state = state_directory()
    state.mkdir(parents=True, exist_ok=True)
    inbox = state / "inbox.jsonl"
    with inbox.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(note, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return {"status": "saved", "note": note, "inbox": str(inbox)}


def selected_adapter_name(requested):
    if requested:
        return requested
    if os.environ.get("RETROSPECTIVE_ADAPTER"):
        return os.environ["RETROSPECTIVE_ADAPTER"]
    if os.environ.get("RETROSPECTIVE_RUNTIME"):
        return os.environ["RETROSPECTIVE_RUNTIME"]
    if os.environ.get("CLAUDECODE"):
        return "claude"
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(prog="retrospective")
    subparsers = parser.add_subparsers(dest="operation", required=True)
    for operation in ("capabilities", "current-session"):
        operation_parser = subparsers.add_parser(operation)
        operation_parser.add_argument("--adapter")
    note_parser = subparsers.add_parser("note")
    note_parser.add_argument("--adapter")
    note_parser.add_argument("--text", required=True)
    note_parser.add_argument("--context", required=True)
    note_parser.add_argument("--approve", action="store_true")
    args = parser.parse_args(argv)
    if args.operation == "note" and (
        not args.context.strip()
        or len(args.context) > 240
        or "\n" in args.context
        or "\r" in args.context
    ):
        parser.error("note context must be one non-empty line of at most 240 characters")

    adapter_name = selected_adapter_name(args.adapter)
    adapter = get_adapter(adapter_name)
    if args.operation == "current-session" and adapter is None:
        result = {"adapter": None, "session_id": None, "status": "unavailable"}
    else:
        if adapter is None:
            parser.error("an explicit supported adapter is required")
        if args.operation == "capabilities":
            result = adapter.capabilities()
        elif args.operation == "current-session":
            result = adapter.current_session()
        else:
            if args.approve:
                result = save_note(adapter, adapter_name, args.text, args.context)
            else:
                note = {"text": args.text, "context": args.context}
                result = {"status": "approval_required", "note": note}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
