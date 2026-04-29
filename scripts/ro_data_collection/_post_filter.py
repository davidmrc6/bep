"""
Post-process Romanian-detected PR comments to remove content that doesn't
represent real-world software dev conversation.
It drops low-confidence Romanian entries, uni/homework repos,
translation repos, comments containing quoted-reply content, and duplicate bodies.
"""
import logging
import re

from collections import Counter
from pathlib import Path

from helpers.aggregation import load_json, _save_json

DEFAULT_MIN_CONFIDENCE = 0.20

# Substring keywords (matched against lowercased repo name)
UNI_SUBSTRINGS = (
    "apprenticeship", "internship", "bootcamp",
    "homework", "hackademy", "pentastagiu",
    "infoeducatie", "softvision-university", "hermes-internship",
    "cegekaacademy", "skillbrain",
    "summerschool", "summer-school",
    "preemployment", "pre-employment",
    "training", "unibuc", "uaic", "politehnic",
)

# Specific repos identified by manual review as uni/training but not caught by
# the regex/substring rules
MANUAL_UNI_REPOS = {
    "mariuspodean/NATIONAL-PYTHON-01",
    "MirceaOvidiu/CleanCoding-GIT-PA",
    "BERDA2024/Exam-Scheduler",
}

# University repo regex
UNI_REPO_RE = re.compile(
    r"(?i)("
    r"\bpractica"                           # practica, PracticaEB2020
    r"|\blabs?(?:\d|[-_]|$)"                # labs, lab3, lab-react
    r"|\bcurs(?:\d|[-_/]|$|uri)"            # curs, curs_2020
    r"|\btema(?:\d|[-_/]|$|le)"             # tema, Tema_X, temele
    r"|\bstagiu"                            # stagiu, stagiul
    r"|\bscoala"                            # scoala, scoala-informala
    r"|\blaborator"                         # laborator, laboratorul
    r"|/oop-\d"
    r"|/dsa-\d"
    r"|cs-utcn"
    r"|aut-eng"
    r"|^ro-msg-"
    r"|\bupb\b"                             # MPS-UPB, UPB-CS, etc. (avoids `upbeat`)
    r"|\bfii\b"                             # FII-2A1-2024, /FII-ASET (avoids `fiipregatit`)
    r")"
)


def _is_uni_repo(repo_full_name: str) -> bool:
    if repo_full_name in MANUAL_UNI_REPOS:
        return True
    lower = repo_full_name.lower()
    if any(s in lower for s in UNI_SUBSTRINGS):
        return True
    return bool(UNI_REPO_RE.search(repo_full_name))

# PR-title patterns indicating an assignment submission
UNI_TITLE_RE = re.compile(
    r"(?i)\b("
    r"tema|lab(?:orator)?\s*\d|homework|exercit|proiect\s*\d|seminar|"
    r"assignment|hw\s*\d|saptamana\s*\d|week\s*\d|midterm"
    r")\b"
)

# Comment types to drop
# NOTE: empty on purpose for possible future additions
DROPPED_COMMENT_TYPES: set[str] = set()

# Hardcoded list of translation/documentation/tutorial repos
TRANSLATION_REPOS = {
    "javascript-tutorial/ro.javascript.info",
    "roalgo-discord/arhiva-educationala",
    "infoeducatie/docs",
    "livepeer/docs",
    "terrastruct/d2-docs",
    "yandex-cloud/docs",
    "spatialthoughts/qgis-tutorials",
}

# Annotation-only patterns
_CODE_RE = re.compile(r"```.*?```|`[^`]+`", re.DOTALL)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")


def _has_quoted_reply(body: str) -> bool:
    """True if any line starts with `>` (markdown quote prefix). These comments
    quote prior content the reader can't see, so the standalone text is often
    not interpretable for sentiment annotation."""
    return any(l.lstrip().startswith(">") for l in body.split("\n"))

def _code_ratio(body: str) -> float:
    if not body:
        return 0.0
    in_code = sum(len(m.group()) for m in _CODE_RE.finditer(body))
    return round(in_code / len(body), 4)

def _drop_reasons(entry: dict, min_confidence: float) -> list[str]:
    reasons = []

    conf = entry.get("ro_confidence")
    if conf is not None and conf < min_confidence:
        reasons.append("low_confidence")

    ctype = entry.get("comment_type")
    if ctype in DROPPED_COMMENT_TYPES:
        reasons.append(f"type_{ctype}")

    repo = entry.get("repo_full_name") or ""
    if _is_uni_repo(repo):
        reasons.append("uni_repo")
    if repo in TRANSLATION_REPOS:
        reasons.append("translation_or_docs")

    title = entry.get("pr_title") or ""
    if UNI_TITLE_RE.search(title):
        reasons.append("uni_title")

    body = entry.get("body") or ""
    if _has_quoted_reply(body):
        reasons.append("quoted_reply")

    return reasons

def run_post_filter(
    input_path: Path,
    clean_path: Path,
    rejected_path: Path,
    log: logging.Logger,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> tuple[list[dict], list[dict]]:
    entries = load_json(input_path, log)
    log.info("LOAD       [post_filter] %d entries from %s", len(entries), input_path)

    clean: list[dict] = []
    rejected: list[dict] = []
    reason_counts: Counter = Counter()
    seen_bodies: set[str] = set()

    for e in entries:
        body = e.get("body") or ""
        annotated = {
            **e,
            "code_ratio": _code_ratio(body),
            "has_email": bool(_EMAIL_RE.search(body)),
        }

        reasons = _drop_reasons(annotated, min_confidence)

        # Dedup after other reasons
        if not reasons:
            key = body.strip()
            if key in seen_bodies:
                reasons.append("duplicate_body")
            else:
                seen_bodies.add(key)

        if reasons:
            for r in reasons:
                reason_counts[r] += 1
            rejected.append({**annotated, "_drop_reasons": reasons})
        else:
            clean.append(annotated)

    _save_json(clean, clean_path)
    _save_json(rejected, rejected_path)

    log.info("SAVE       [post_filter] %d clean → %s", len(clean), clean_path)
    log.info("SAVE       [post_filter] %d rejected → %s", len(rejected), rejected_path)

    log.info("INFO       [post_filter] reason counts (entries can have multiple reasons):")
    for reason, n in reason_counts.most_common():
        log.info("INFO       [post_filter]   %-22s %5d", reason, n)
    log.info(
        "INFO       [post_filter] kept %d / %d (%.1f%%)",
        len(clean), len(entries), 100 * len(clean) / max(len(entries), 1),
    )

    return clean, rejected
