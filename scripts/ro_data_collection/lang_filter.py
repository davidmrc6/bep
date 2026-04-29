"""
Filter PR comments to keep only those where Romanian is the top detected language.
Uses lingua-language-detector for accurate deterministic language detection.
"""
import logging
import re

from pathlib import Path
from lingua import Language, LanguageDetectorBuilder
from helpers.aggregation import load_json, _save_json

MIN_BODY_LENGTH = 10  # skip very short comments as they are too noisy for n-gram model lang detection

# Markers that indicate a comment is an email-reply artifact rather than a
# genuine PR comment. If any marker is found, the whole comment is discarded
_EMAIL_ARTIFACT_MARKERS = [
    "Reply to this email directly",
    "reacted to your message",
    "You are receiving this because",
    "DISCLAIMER",
    "***@***.***>",               # GitHub-masked email addresses in forwarded mail
]


def _is_email_artifact(text: str) -> bool:
    """Return True if the comment looks like an email-reply artifact."""
    lower = text.lower()
    return any(m.lower() in lower for m in _EMAIL_ARTIFACT_MARKERS)


# Technical noise patterns (confuse n-gram model)
_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)           # fenced code blocks
_INLINE_CODE_RE = re.compile(r"`[^`]+`")                       # inline code
_URL_RE = re.compile(r"https?://\S+")                          # URLs
_MENTION_RE = re.compile(r"@[\w-]+")                           # @mentions
_PATH_RE = re.compile(r"[\w./\\-]+\.\w{1,5}")                  # file paths like src/foo.js
_MARKDOWN_RE = re.compile(r"!\[.*?\]\(.*?\)|\[.*?\]\(.*?\)")   # markdown links/images
_NONLATIN_RE = re.compile(r"[^\u0000-\u024F\u1E00-\u1EFF]+")   # non-Latin scripts (Cyrillic, CJK, etc.)


def _clean_for_detection(text: str) -> str:
    """Strip code, URLs, mentions, and non-Latin text before language detection."""
    text = _CODE_BLOCK_RE.sub(" ", text)
    text = _INLINE_CODE_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    text = _MENTION_RE.sub(" ", text)
    text = _MARKDOWN_RE.sub(" ", text)
    text = _PATH_RE.sub(" ", text)
    text = _NONLATIN_RE.sub(" ", text)
    # Collapse whitespace
    return " ".join(text.split())


def build_detector():
    return (
        LanguageDetectorBuilder
        .from_all_languages()
        .with_preloaded_language_models()
        .build()
    )


def run_lang_filter(
    input_path: Path,
    output_dir: Path,
    log: logging.Logger,
    min_length: int = MIN_BODY_LENGTH,
) -> list[dict]:
    """Run language detection. Returns list of Romanian detected comments."""
    log.info("INIT       [lang_filter] building language detector...")
    detector = build_detector()
    log.info("INIT       [lang_filter] detector ready")

    comments_raw = load_json(input_path, log)
    # Deduplicate
    seen = set()
    comments = []
    for c in comments_raw:
        key = (c.get("repo_full_name"), c.get("pr_number"),
               c.get("comment_type"), c.get("created_at"), c.get("author_login"))
        if key not in seen:
            seen.add(key)
            comments.append(c)
    if len(comments_raw) != len(comments):
        log.info("DEDUP      [lang_filter] %d → %d comments", len(comments_raw), len(comments))
    log.info("LOAD       [lang_filter] %d comments from %s", len(comments), input_path)

    ro_comments = []
    lang_counts: dict[str, int] = {}
    skipped_short = 0
    skipped_email = 0

    for i, c in enumerate(comments):
        if (i + 1) % 2000 == 0:
            log.info("PROGRESS   [lang_filter %d/%d]", i + 1, len(comments))

        body = c.get("body", "")

        if _is_email_artifact(body):
            skipped_email += 1
            continue

        cleaned = _clean_for_detection(body)
        if len(cleaned) < min_length:
            skipped_short += 1
            continue

        # Compute per-language confidence values on cleaned text
        confidence_values = detector.compute_language_confidence_values(cleaned)

        # Track top language for stats
        if confidence_values:
            top = confidence_values[0]
            top_lang = top.language.iso_code_639_1.name.lower()
        else:
            top_lang = "unknown"
        lang_counts[top_lang] = lang_counts.get(top_lang, 0) + 1

        # Find Romanian confidence
        ro_prob = 0.0
        for cv in confidence_values:
            if cv.language == Language.ROMANIAN:
                ro_prob = cv.value
                break

        # Keep all comments where Romanian is the top language
        if top_lang == "ro":
            record = {**c, "ro_confidence": round(ro_prob, 4)}
            ro_comments.append(record)

    ro_comments.sort(key=lambda r: r["ro_confidence"], reverse=True)

    review_path = output_dir / "ro_comments_review.json"
    _save_json(ro_comments, review_path)
    log.info("SAVE       [lang_filter] %d Romanian comments → %s", len(ro_comments), review_path)

    sorted_langs = sorted(lang_counts.items(), key=lambda x: -x[1])
    stats_path = output_dir / "lang_stats.json"
    _save_json(sorted_langs, stats_path)
    log.info("SAVE       [lang_filter] language stats → %s", stats_path)

    log.info("INFO       [lang_filter] skipped (email artifacts): %d", skipped_email)
    log.info("INFO       [lang_filter] skipped (too short, <%d chars): %d", min_length, skipped_short)
    log.info("INFO       [lang_filter] Romanian comments: %d", len(ro_comments))

    log.info("INFO       [lang_filter] top languages detected:")
    for lang, count in sorted_langs[:10]:
        log.info("INFO       [lang_filter]   %5s: %d", lang, count)

    log.info("DONE       [lang_filter] outputs written to %s", output_dir.resolve())
    return ro_comments
