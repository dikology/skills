from pathlib import Path


CAPABILITIES = {
    "adapter": "claude",
    "operations": ["capabilities", "current-session", "note"],
    "signals": ["current_session_identity"],
    "destinations": ["retro_inbox"],
}


def capabilities():
    return CAPABILITIES


def current_session():
    transcripts = list((Path.home() / ".claude" / "projects").glob("*/*.jsonl"))
    if not transcripts:
        return {"adapter": "claude", "session_id": None, "status": "unavailable"}
    newest = max(transcripts, key=lambda path: path.stat().st_mtime)
    return {
        "adapter": "claude",
        "session_id": newest.stem,
        "status": "available",
        "transcript_path": str(newest),
    }
