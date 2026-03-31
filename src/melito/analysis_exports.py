"""Build validation and derivative artifacts from compact Melito analysis JSONL batches."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BATCH_RE = re.compile(r"analysis_(\d{4})_(\d{4})\.jsonl$")
KNOWN_KEYS = {"sl", "src", "ana", "emd", "tok", "lit", "sm", "syn"}


def nfc(text: str) -> str:
    """Return NFC-normalized text."""
    return unicodedata.normalize("NFC", text)


def normalize_value(value: Any) -> Any:
    """Recursively NFC-normalize all strings in a nested JSON value."""
    if isinstance(value, str):
        return nfc(value)
    if isinstance(value, list):
        return [normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_value(item) for key, item in value.items()}
    return value


def load_json(path: Path) -> dict[str, Any]:
    """Load a UTF-8 JSON document."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_source_lines(path: Path) -> list[str]:
    """Load source lines while preserving the exact line count."""
    return nfc(path.read_text(encoding="utf-8")).splitlines()


def get_reading_text(record: dict[str, Any]) -> str:
    """Return the best reading text for export, or blank for deleted/omitted lines."""
    text = record.get("ana") or record["src"]
    if text == "[DELETED]":
        return ""
    if isinstance(text, str) and text.startswith("<UNCERTAIN:"):
        return ""
    return nfc(text)


def collect_uncertain_reasons(record: dict[str, Any]) -> list[str]:
    """Collect strings containing explicit uncertainty markers from a record."""
    reasons: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            if "<UNCERTAIN:" in value:
                reasons.append(nfc(value))
            return
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if isinstance(value, dict):
            for item in value.values():
                walk(item)

    walk(record)
    return list(dict.fromkeys(reasons))


def parse_batch_range(name: str) -> tuple[int, int]:
    """Parse the encoded source-line range from a batch filename."""
    match = BATCH_RE.fullmatch(name)
    if not match:
        raise ValueError(f"Unrecognized batch filename: {name}")
    return int(match.group(1)), int(match.group(2))


def record_status(record: dict[str, Any]) -> str:
    """Classify a record for lightweight frontend filtering."""
    ana = record.get("ana", "")
    if ana == "[DELETED]":
        return "deleted"
    if isinstance(ana, str) and ana.startswith("<UNCERTAIN:"):
        return "omitted"
    if collect_uncertain_reasons(record):
        return "uncertain"
    return "normal"


def build_site_payload(
    meta: dict[str, Any],
    qa_report: dict[str, Any],
    records: list[dict[str, Any]],
    lemma_data: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    """Build the self-contained frontend payload for the static site."""
    pos_counts: Counter[str] = Counter()
    line_lengths: list[int] = []
    for record in records:
        reading = get_reading_text(record)
        if reading:
            line_lengths.append(len(record.get("tok", [])))
        for token in record.get("tok", []):
            if isinstance(token, list) and len(token) == 5:
                pos_counts[token[2]] += 1

    top_lemmas = [
        {"lemma": lemma, "pos": pos, "count": entry["count"]}
        for (lemma, pos), entry in sorted(
            lemma_data.items(),
            key=lambda item: (-item[1]["count"], item[0][0], item[0][1]),
        )[:24]
    ]
    records_payload = []
    for record in records:
        uncertain = collect_uncertain_reasons(record)
        records_payload.append(
            {
                "sl": record["sl"],
                "src": record["src"],
                "ana": record.get("ana", ""),
                "reading": get_reading_text(record),
                "status": record_status(record),
                "emd": record.get("emd", ""),
                "unc": uncertain,
                "tok": record.get("tok", []),
                "lit": record.get("lit", ""),
                "sm": record.get("sm", ""),
                "syn": record.get("syn", {}),
            }
        )

    return {
        "title": "Melito of Sardis — Peri Pascha",
        "subtitle": "Interactive reading edition built from the full structured corpus.",
        "meta": {
            "source": meta["src"],
            "changeLog": meta["log"],
            "format": meta["fmt"],
            "completionStatus": meta["completion_status"],
            "completedRange": meta["completed_source_line_range"],
            "totalSourceLines": meta["total_source_lines"],
            "blankLinesOmitted": meta["blank_lines_omitted"],
            "policy": meta["policy"],
            "src": meta["src"],
            "log": meta["log"],
            "fmt": meta["fmt"],
            "completion_status": meta["completion_status"],
            "completed_source_line_range": meta["completed_source_line_range"],
            "total_source_lines": meta["total_source_lines"],
            "blank_lines_omitted": meta["blank_lines_omitted"],
            "completed_nonblank_records": qa_report["record_count"],
        },
        "qa": {
            **qa_report,
            "recordCount": qa_report["record_count"],
            "blankSourceLineCount": qa_report["blank_source_line_count"],
            "tokenCount": qa_report["token_count"],
            "lemmaCount": qa_report["lemma_count"],
            "uncertainRecordCount": qa_report["uncertain_record_count"],
            "deletedRecordCount": qa_report["deleted_or_omitted_record_count"],
            "deletedOrOmittedLines": qa_report["deleted_or_omitted_record_lines"],
            "cleanTextOmittedLines": qa_report["clean_text_omitted_record_lines"],
        },
        "stats": {
            "posCounts": dict(sorted(pos_counts.items())),
            "topLemmas": top_lemmas,
            "averageTokensPerExtantLine": (
                round(sum(line_lengths) / len(line_lengths), 2) if line_lengths else 0
            ),
        },
        "records": records_payload,
    }


def iter_records(meta: dict[str, Any], root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load and validate batch records, returning all records and batch summaries."""
    all_records: list[dict[str, Any]] = []
    batch_summaries: list[dict[str, Any]] = []

    for batch_name in meta["batch_files"]:
        batch_path = root / batch_name
        start, end = parse_batch_range(batch_name)
        batch_records: list[dict[str, Any]] = []
        for raw_line in batch_path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            record = normalize_value(json.loads(raw_line))
            batch_records.append(record)
            all_records.append(record)

        batch_summaries.append(
            {
                "file": batch_name,
                "range_start": start,
                "range_end": end,
                "record_count": len(batch_records),
                "first_record": batch_records[0]["sl"] if batch_records else None,
                "last_record": batch_records[-1]["sl"] if batch_records else None,
            }
        )

    return all_records, batch_summaries


def build_outputs(root: Path) -> dict[str, Any]:
    """Validate the corpus and build derivative artifacts in *root*."""
    meta_path = root / "analysis_meta.json"
    schema_path = root / "analysis_schema.json"
    meta = load_json(meta_path)
    _schema = load_json(schema_path)
    source_lines = load_source_lines(root / meta["src"])
    records, batch_summaries = iter_records(meta, root)

    duplicate_lines: list[int] = []
    missing_nonblank_lines: list[int] = []
    out_of_range_records: list[int] = []
    batch_range_violations: list[dict[str, Any]] = []
    schema_key_violations: list[dict[str, Any]] = []
    token_shape_violations: list[int] = []
    non_nfc_lines: list[int] = []
    ascii_quote_readings: list[int] = []

    by_line: dict[int, dict[str, Any]] = {}
    token_rows: list[list[str]] = []
    lemma_data: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "forms": Counter(), "lines": set()}
    )
    uncertain_rows: list[list[str]] = []

    for record in records:
        sl = int(record["sl"])
        if sl in by_line:
            duplicate_lines.append(sl)
        by_line[sl] = record

        if sl < 1 or sl > len(source_lines):
            out_of_range_records.append(sl)

        extras = sorted(set(record) - KNOWN_KEYS)
        if extras:
            schema_key_violations.append({"sl": sl, "extra_keys": extras})

        reading = get_reading_text(record)
        if reading != nfc(reading):
            non_nfc_lines.append(sl)
        if any(ch in reading for ch in ['"', "'"]):
            ascii_quote_readings.append(sl)

        tokens = record.get("tok", [])
        if not isinstance(tokens, list):
            token_shape_violations.append(sl)
            continue

        for index, token in enumerate(tokens, start=1):
            if not (isinstance(token, list) and len(token) == 5 and all(isinstance(x, str) for x in token)):
                token_shape_violations.append(sl)
                continue
            form, lemma, pos, morph, gloss = token
            token_rows.append([str(sl), str(index), reading, form, lemma, pos, morph, gloss])
            lemma_entry = lemma_data[(lemma, pos)]
            lemma_entry["count"] += 1
            lemma_entry["forms"][form] += 1
            lemma_entry["lines"].add(sl)

        uncertain_reasons = collect_uncertain_reasons(record)
        if uncertain_reasons:
            uncertain_rows.append(
                [
                    str(sl),
                    record["src"],
                    reading,
                    " | ".join(uncertain_reasons),
                    record.get("lit", ""),
                    record.get("sm", ""),
                ]
            )

    for batch in batch_summaries:
        first_record = batch["first_record"]
        last_record = batch["last_record"]
        if first_record is None:
            continue
        if not (batch["range_start"] <= first_record <= batch["range_end"]):
            batch_range_violations.append(batch)
            continue
        if not (batch["range_start"] <= last_record <= batch["range_end"]):
            batch_range_violations.append(batch)

    sorted_lines = sorted(by_line)
    if sorted_lines != list(dict.fromkeys(sorted_lines)):
        duplicate_lines = sorted(set(duplicate_lines))

    blank_source_line_count = 0
    clean_lines: list[str] = []
    omitted_clean_lines: list[int] = []
    for line_no, raw_line in enumerate(source_lines, start=1):
        if raw_line == "":
            blank_source_line_count += 1
            clean_lines.append("")
            continue
        record = by_line.get(line_no)
        if record is None:
            missing_nonblank_lines.append(line_no)
            clean_lines.append("")
            continue
        reading = get_reading_text(record)
        if reading == "":
            omitted_clean_lines.append(line_no)
            clean_lines.append("")
        else:
            clean_lines.append(reading)

    all_path = root / "analysis_all.jsonl"
    with all_path.open("w", encoding="utf-8") as handle:
        for line_no in sorted_lines:
            handle.write(json.dumps(by_line[line_no], ensure_ascii=False))
            handle.write("\n")

    clean_path = root / "clean_greek_full.txt"
    clean_path.write_text("\n".join(clean_lines), encoding="utf-8")

    uncertain_path = root / "uncertain_readings.csv"
    with uncertain_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sl", "src", "reading", "reason", "literal_translation", "smooth_translation"])
        writer.writerows(uncertain_rows)

    tokens_path = root / "tokens.csv"
    with tokens_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sl", "token_index", "reading", "form", "lemma", "pos", "morph", "gloss"])
        writer.writerows(token_rows)

    lemma_path = root / "lemma_index.csv"
    with lemma_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["lemma", "pos", "occurrences", "forms", "lines"])
        for (lemma, pos), entry in sorted(lemma_data.items()):
            forms = "; ".join(
                f"{form} ({count})" for form, count in sorted(entry["forms"].items())
            )
            lines = "; ".join(str(line_no) for line_no in sorted(entry["lines"]))
            writer.writerow([lemma, pos, entry["count"], forms, lines])

    deleted_records = sorted(
        record["sl"]
        for record in records
        if record.get("ana") == "[DELETED]" or record.get("ana", "").startswith("<UNCERTAIN:")
    )
    qa_report = {
        "status": (
            "ok"
            if not any(
                [
                    duplicate_lines,
                    missing_nonblank_lines,
                    out_of_range_records,
                    batch_range_violations,
                    schema_key_violations,
                    token_shape_violations,
                    non_nfc_lines,
                    ascii_quote_readings,
                ]
            )
            else "issues"
        ),
        "meta_source": str(meta_path.name),
        "source_text": meta["src"],
        "total_source_lines": len(source_lines),
        "blank_source_line_count": blank_source_line_count,
        "record_count": len(records),
        "meta_record_count": meta["completed_nonblank_records"],
        "batch_count": len(meta["batch_files"]),
        "deleted_or_omitted_record_lines": deleted_records,
        "deleted_or_omitted_record_count": len(deleted_records),
        "uncertain_record_count": len(uncertain_rows),
        "token_count": len(token_rows),
        "lemma_count": len(lemma_data),
        "duplicate_source_lines": duplicate_lines,
        "missing_nonblank_source_lines": missing_nonblank_lines,
        "out_of_range_record_lines": out_of_range_records,
        "batch_range_violations": batch_range_violations,
        "schema_key_violations": schema_key_violations,
        "token_shape_violations": token_shape_violations,
        "non_nfc_reading_lines": non_nfc_lines,
        "ascii_quote_reading_lines": ascii_quote_readings,
        "clean_text_omitted_record_lines": omitted_clean_lines,
        "batch_summaries": batch_summaries,
        "artifacts": {
            "analysis_all_jsonl": all_path.name,
            "clean_greek_full_txt": clean_path.name,
            "uncertain_readings_csv": uncertain_path.name,
            "tokens_csv": tokens_path.name,
            "lemma_index_csv": lemma_path.name,
        },
    }

    site_dir = root / "site"
    site_dir.mkdir(exist_ok=True)
    site_payload = build_site_payload(meta, qa_report, records, lemma_data)
    site_data_path = site_dir / "data.js"
    site_data_path.write_text(
        "window.PERI_PASCHA_DATA = "
        + json.dumps(site_payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    qa_report["artifacts"]["site_data_js"] = str(site_data_path.relative_to(root))

    qa_path = root / "analysis_qa_report.json"
    qa_path.write_text(json.dumps(qa_report, ensure_ascii=False, indent=2), encoding="utf-8")
    return qa_report


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root containing analysis_meta.json (default: current directory).",
    )
    args = parser.parse_args()
    report = build_outputs(args.root.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
