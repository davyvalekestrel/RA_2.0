"""
ra2.sigil — Sigil shorthand memory (one plain-text file per stream).

Format per line:  σN: key→value
Max 15 entries, FIFO replacement.
Deterministic rule-based generation only — no AI involvement.
"""

import os
import re
from typing import List, Optional, Tuple

SIGIL_DIR: str = os.environ.get(
    "RA2_SIGIL_DIR",
    os.path.join(os.path.expanduser("~"), ".ra2", "sigils"),
)

MAX_ENTRIES = 15
_LINE_RE = re.compile(r"^σ(\d+):\s*(.+)$")


def _sigil_path(stream_id: str) -> str:
    return os.path.join(SIGIL_DIR, f"{stream_id}.sigil")


def load(stream_id: str) -> List[Tuple[int, str]]:
    """Load sigil entries as list of (index, body) tuples."""
    path = _sigil_path(stream_id)
    if not os.path.exists(path):
        return []
    entries: List[Tuple[int, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            m = _LINE_RE.match(line)
            if m:
                entries.append((int(m.group(1)), m.group(2)))
    return entries


def save(stream_id: str, entries: List[Tuple[int, str]]) -> None:
    """Persist sigil entries, enforcing MAX_ENTRIES via FIFO."""
    # FIFO: keep only the last MAX_ENTRIES
    entries = entries[-MAX_ENTRIES:]
    os.makedirs(SIGIL_DIR, exist_ok=True)
    path = _sigil_path(stream_id)
    with open(path, "w", encoding="utf-8") as f:
        for idx, body in entries:
            f.write(f"\u03c3{idx}: {body}\n")


def append(stream_id: str, body: str) -> List[Tuple[int, str]]:
    """Add a new sigil entry. Auto-numbers and FIFO-evicts if at capacity."""
    entries = load(stream_id)
    next_idx = (entries[-1][0] + 1) if entries else 1
    entries.append((next_idx, body))
    # FIFO eviction
    if len(entries) > MAX_ENTRIES:
        entries = entries[-MAX_ENTRIES:]
    save(stream_id, entries)
    return entries


def snapshot(stream_id: str) -> str:
    """Return sigil state as plain text for prompt injection."""
    entries = load(stream_id)
    if not entries:
        return "(no sigils)"
    return "\n".join(f"\u03c3{idx}: {body}" for idx, body in entries)


# ── Deterministic sigil generators ──────────────────────────────────

# Rule-based patterns that detect sigil-worthy events from messages.
# Each rule: (regex_on_content, sigil_body_template)
_SIGIL_RULES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"fork(?:ed|ing)?\s*(?:to|into|→)\s*(\S+)", re.I),
     "fork\u2192{0}"),
    (re.compile(r"token[_\s]*burn", re.I),
     "token_burn\u2192compress"),
    (re.compile(r"rewrite[_\s]*impulse", re.I),
     "rewrite_impulse\u2192layer"),
    (re.compile(r"context[_\s]*sov(?:ereignty)?", re.I),
     "context_sov\u2192active"),
    (re.compile(r"budget[_\s]*cap(?:ped)?", re.I),
     "budget\u2192capped"),
    (re.compile(r"rate[_\s]*limit", re.I),
     "rate_limit\u2192detected"),
    (re.compile(r"provider[_\s]*switch(?:ed)?", re.I),
     "provider\u2192switched"),
    (re.compile(r"compaction[_\s]*trigger", re.I),
     "compaction\u2192triggered"),
]


def generate_from_message(content: str) -> Optional[str]:
    """Apply deterministic rules to a message. Returns sigil body or None."""
    for pattern, template in _SIGIL_RULES:
        m = pattern.search(content)
        if m:
            # Fill template with captured groups if any
            try:
                return template.format(*m.groups())
            except (IndexError, KeyError):
                return template
    return None
