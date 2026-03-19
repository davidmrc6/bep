"""
Filter PR comments to keep only Romanian-language text.

Uses lingua-language-detector for accurate deterministic language detection.

Reads pr_comments.json, runs each comment through language detection,
and produces:
  - ro_comments.json          — high confidence Romanian (>= threshold)
  - ro_comments_review.json   — borderline cases (between review_floor and threshold)
                                 for manual review
  - lang_stats.json           — per-language distribution summary
"""
import argparse
import json
import logging

from pathlib import Path
from lingua import Language, LanguageDetectorBuilder
from constants.constants import OUTPUT_DIR

DEFAULT_THRESHOLD = 0.7
DEFAULT_REVIEW_FLOOR = 0.4
MIN_BODY_LENGTH = 15  # skip very short comments as they are too noisy for n-gram model lang detection


def build_detector():
    """Build a lingua detector tuned for Romanian detection."""
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
    threshold: float = DEFAULT_THRESHOLD,
    review_floor: float = DEFAULT_REVIEW_FLOOR,
    min_length: int = MIN_BODY_LENGTH,
) -> tuple[list[dict], list[dict]]:
    """Run language detection. Returns (accepted, review) comment lists."""
    log.info("Building language detector...")
    detector = build_detector()
    log.info("Detector ready")

    comments = json.loads(input_path.read_text(encoding="utf-8"))
    log.info("Loaded %d comments from %s", len(comments), input_path)

    accepted = []
    review = []
    lang_counts: dict[str, int] = {}
    skipped_short = 0

    for i, c in enumerate(comments):
        if (i + 1) % 2000 == 0:
            log.info("Progress: %d/%d", i + 1, len(comments))

        body = c.get("body", "")
        if len(body) < min_length:
            skipped_short += 1
            continue

        # Compute per-language confidence values
        confidence_values = detector.compute_language_confidence_values(body)

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

        record = {**c, "ro_confidence": round(ro_prob, 4)}

        if ro_prob >= threshold:
            accepted.append(record)
        elif ro_prob >= review_floor:
            review.append(record)

    # Save outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    accepted_path = output_dir / "ro_comments.json"
    accepted_path.write_text(json.dumps(accepted, indent=2, ensure_ascii=False))
    log.info("Saved %d accepted comments to %s", len(accepted), accepted_path)

    review_path = output_dir / "ro_comments_review.json"
    review_path.write_text(json.dumps(review, indent=2, ensure_ascii=False))
    log.info("Saved %d review comments to %s", len(review), review_path)

    # Sort lang stats descending
    sorted_langs = sorted(lang_counts.items(), key=lambda x: -x[1])
    stats_path = output_dir / "lang_stats.json"
    stats_path.write_text(json.dumps(dict(sorted_langs), indent=2))
    log.info("Saved language stats to %s", stats_path)

    log.info("Skipped (too short, <%d chars): %d", min_length, skipped_short)
    log.info("Accepted (ro >= %.2f): %d", threshold, len(accepted))
    log.info("For review (%.2f <= ro < %.2f): %d", review_floor, threshold, len(review))

    log.info("Top languages detected:")
    for lang, count in sorted_langs[:10]:
        log.info("  %5s: %d", lang, count)

    log.info("Outputs written to %s", output_dir.resolve())
    return accepted, review


if __name__ == "__main__":
    from helpers.log import setup_logging

    p = argparse.ArgumentParser(description="Filter PR comments for Romanian language")
    p.add_argument("--input", type=Path, default=OUTPUT_DIR / "pr_comments.json")
    p.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    p.add_argument("--review-floor", type=float, default=DEFAULT_REVIEW_FLOOR)
    p.add_argument("--min-length", type=int, default=MIN_BODY_LENGTH)
    args = p.parse_args()

    run_lang_filter(
        input_path=args.input,
        output_dir=args.output_dir,
        log=setup_logging(),
        threshold=args.threshold,
        review_floor=args.review_floor,
        min_length=args.min_length,
    )
