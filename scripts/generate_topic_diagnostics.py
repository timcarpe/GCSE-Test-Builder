#!/usr/bin/env python3
"""Generate topic classification diagnostics at part level.

Analyzes questions.jsonl files to identify question PARTS with "Unknown" topic
classification and creates diagnostic data for fixing regex patterns.

Usage:
    python scripts/generate_topic_diagnostics.py [--exam-code CODE]
"""

import argparse
import json
import random
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from datetime import datetime

# Add src to path for classification imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

SLICES_ROOT = Path("workspace/slices_cache")
OUTPUT_ROOT = Path("workspace/topic_diagnostics")
PLUGINS_ROOT = Path("src/gcse_toolkit/plugins")

# Pattern to remove answer lines (dots, underscores, brackets for writing)
ANSWER_LINE_PATTERN = re.compile(
    r'\.{4,}|_{4,}|\[[\d\s]+\]$|\.{2,}\s*\[[\d\s]+\]',
    re.MULTILINE
)


def sanitize_text(text: str) -> str:
    """Remove answer lines and clean up text for readability."""
    if not text:
        return ""
    
    # Remove dot/underscore answer lines
    text = ANSWER_LINE_PATTERN.sub('', text)
    
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    
    # Remove page references like "0478/12/F/M/17 © UCLES 2017 7"
    text = re.sub(r'\d{4}/\d{2}/[A-Z]/[A-Z]/\d{2}\s*©\s*UCLES\s*\d{4}\s*\d*', '', text)
    
    return text.strip()


EXAMS_DIR = Path("scripts/Plugin Generation/_Exams")

def load_questions(exam_code: str) -> list[dict]:
    """Load all questions from questions.jsonl for an exam code."""
    # Try new Plugin Generation location first
    jsonl_path = EXAMS_DIR / exam_code / "_metadata" / "questions.jsonl"
    
    # Fallback to legacy workspace location
    if not jsonl_path.exists():
        jsonl_path = SLICES_ROOT / exam_code / "_metadata" / "questions.jsonl"
        
    if not jsonl_path.exists():
        return []
    
    questions = []
    with open(jsonl_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


def get_classification_stats(text: str, exam_code: str, paper: int = 1) -> dict:
    """
    Get detailed classification statistics for a text.
    
    Returns dict with:
    - all_scores: {topic: score} for all topics with matches
    - matched_patterns: {topic: [patterns that matched]}
    - top_topic: best scoring topic (or None)
    - is_tie: whether there was a close second
    - margin: score difference between top 2
    - total_matches: total pattern matches across all topics
    """
    from gcse_toolkit.extractor_v2.classification import (
        _get_topic_patterns, _compile_patterns, _get_exam_stats, _build_pattern_weights
    )
    
    if not text or not text.strip():
        return {
            "all_scores": {},
            "matched_patterns": {},
            "top_topic": None,
            "is_tie": False,
            "margin": 0,
            "total_matches": 0,
            "reason": "empty_text",
        }
    
    patterns = _get_topic_patterns(exam_code, paper)
    if not patterns:
        return {
            "all_scores": {},
            "matched_patterns": {},
            "top_topic": None,
            "is_tie": False,
            "margin": 0,
            "total_matches": 0,
            "reason": "no_patterns",
        }
    
    compiled = _compile_patterns(patterns)
    stats = _get_exam_stats(exam_code)
    pattern_weights = _build_pattern_weights(stats) if stats else {}
    use_weights = len(pattern_weights) > 0
    
    scores = {}
    matched_patterns = {}
    total_matches = 0
    
    for topic, regexes in compiled.items():
        original_strings = list(patterns[topic])
        p_weights = pattern_weights.get(topic) or pattern_weights.get(topic.lower()) or {}
        
        topic_score = 0.0
        topic_matches = []
        
        for i, pattern in enumerate(regexes):
            pat_str = original_strings[i] if i < len(original_strings) else None
            
            if use_weights:
                weight = p_weights.get(pat_str, 0.5) if pat_str else 0.5
            else:
                weight = 1.0
            
            match = pattern.search(text)
            if match:
                topic_score += weight
                topic_matches.append({
                    "pattern": pat_str,
                    "weight": round(weight, 2),
                    "matched_text": match.group()[:50],  # First 50 chars of match
                })
                total_matches += 1
        
        if topic_matches:
            scores[topic] = round(topic_score, 2)
            matched_patterns[topic] = topic_matches
    
    # Determine classification result
    if not scores:
        return {
            "all_scores": {},
            "matched_patterns": {},
            "top_topic": None,
            "is_tie": False,
            "margin": 0,
            "total_matches": 0,
            "reason": "no_matches",
        }
    
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_topic, top_score = sorted_scores[0]
    
    # Check confidence
    is_tie = False
    margin = top_score
    reason = "classified"
    
    if top_score < 0.8:
        reason = "score_too_low"
        top_topic = None
    elif len(sorted_scores) > 1:
        second_topic, second_score = sorted_scores[1]
        margin = round(top_score - second_score, 2)
        if margin < 0.4:
            is_tie = True
            reason = "tie_no_margin"
            top_topic = None
    
    return {
        "all_scores": dict(sorted_scores),  # Sorted by score desc
        "matched_patterns": matched_patterns,
        "top_topic": top_topic,
        "is_tie": is_tie,
        "margin": margin,
        "total_matches": total_matches,
        "reason": reason,
    }


def classify_parts_for_diagnostics(question: dict, exam_code: str) -> list[dict]:
    """
    Classify each part of a question with full diagnostic statistics.
    
    Returns list of part records with classification info.
    """
    parts = []
    paper = question.get("paper", 1)
    
    # Root part
    root_text = question.get("root_text", "")
    root_label = str(question.get("question_number", ""))
    root_stats = get_classification_stats(root_text, exam_code, paper)
    
    parts.append({
        "part_label": root_label,
        "part_type": "root",
        "text": sanitize_text(root_text),
        "classified_topic": root_stats["top_topic"] or "00. Unknown",
        "is_unknown": root_stats["top_topic"] is None,
        "classification_stats": root_stats,
    })
    
    # Child parts
    child_text = question.get("child_text", {})
    for label, text in child_text.items():
        stats = get_classification_stats(text, exam_code, paper)
        parts.append({
            "part_label": label,
            "part_type": "child",
            "text": sanitize_text(text),
            "classified_topic": stats["top_topic"] or "00. Unknown",
            "is_unknown": stats["top_topic"] is None,
            "classification_stats": stats,
        })
    
    return parts


def process_questions_part_level(questions: list[dict], exam_code: str) -> tuple[list, list]:
    """
    Process all questions at part level, returning uncategorized and regression samples.
    
    Returns:
        (uncategorized_parts, categorized_parts) - Both as flat lists of part records
    """
    uncategorized = []
    categorized = []
    
    for q in questions:
        parts = classify_parts_for_diagnostics(q, exam_code)
        
        # Common question metadata
        q_meta = {
            "question_id": q.get("question_id", ""),
            "exam_code": q.get("exam_code", ""),
            "year": q.get("year"),
            "paper": q.get("paper"),
            "question_number": q.get("question_number"),
            "final_topic": q.get("topic", ""),  # The final assigned topic after consensus
        }
        
        for part in parts:
            record = {**q_meta, **part}
            
            if part["is_unknown"]:
                uncategorized.append(record)
            else:
                # For regression sample, strip heavy stats to reduce size
                record_light = {**record}
                record_light["classification_stats"] = {
                    "top_topic": part["classification_stats"]["top_topic"],
                    "margin": part["classification_stats"]["margin"],
                    "total_matches": part["classification_stats"]["total_matches"],
                }
                categorized.append(record_light)
    
    return uncategorized, categorized


def sample_stratified(items: list[dict], sample_size: int) -> list[dict]:
    """Sample items stratified by topic."""
    if len(items) <= sample_size:
        return items
    
    by_topic = defaultdict(list)
    for item in items:
        by_topic[item.get("classified_topic", "")].append(item)
    
    topics = list(by_topic.keys())
    if not topics:
        return random.sample(items, sample_size)
    
    samples_per_topic = max(1, sample_size // len(topics))
    
    sampled = []
    for topic in topics:
        topic_items = by_topic[topic]
        n = min(samples_per_topic, len(topic_items))
        sampled.extend(random.sample(topic_items, n))
    
    # Fill remaining slots
    if len(sampled) < sample_size:
        remaining = [i for i in items if i not in sampled]
        extra_needed = sample_size - len(sampled)
        if remaining and extra_needed > 0:
            sampled.extend(random.sample(remaining, min(extra_needed, len(remaining))))
    
    return sampled[:sample_size]


def generate_summary(uncategorized: list, regression: list, exam_code: str, total_parts: int) -> str:
    """Generate human-readable summary - full text, no truncation."""
    lines = [
        f"Topic Classification Diagnostics: {exam_code}",
        f"Generated: {datetime.now().isoformat()}",
        "",
        f"Total question parts analyzed: {total_parts}",
        f"Uncategorized parts: {len(uncategorized)}",
        f"Regression sample size: {len(regression)}",
        f"Uncategorized rate: {len(uncategorized)/total_parts*100:.1f}%" if total_parts else "N/A",
        "",
        "=" * 80,
        "CLASSIFICATION FAILURE REASONS",
        "=" * 80,
        "",
    ]
    
    # Analyze failure reasons
    by_reason = defaultdict(int)
    for part in uncategorized:
        reason = part.get("classification_stats", {}).get("reason", "unknown")
        by_reason[reason] += 1
    
    for reason, count in sorted(by_reason.items(), key=lambda x: -x[1]):
        lines.append(f"  {reason}: {count} ({count/len(uncategorized)*100:.1f}%)")
    
    lines.extend([
        "",
        "=" * 80,
        "UNCATEGORIZED PARTS (with classification stats)",
        "=" * 80,
        "",
    ])
    
    # Group by question for readability
    by_question = defaultdict(list)
    for part in uncategorized:
        by_question[part["question_id"]].append(part)
    
    for q_id, parts in sorted(by_question.items()):
        lines.append(f"### {q_id}")
        lines.append(f"    Final topic: {parts[0].get('final_topic', 'N/A')}")
        
        for part in parts:
            stats = part.get("classification_stats", {})
            lines.append(f"")
            lines.append(f"    [{part['part_label']}] Reason: {stats.get('reason', 'N/A')}")
            
            # Show scores if any
            all_scores = stats.get("all_scores", {})
            if all_scores:
                lines.append(f"    Scores: {all_scores}")
                lines.append(f"    Margin: {stats.get('margin', 0)}, Total matches: {stats.get('total_matches', 0)}")
            
            # Show matched patterns
            matched = stats.get("matched_patterns", {})
            if matched:
                lines.append(f"    Matched patterns by topic:")
                for topic, pats in matched.items():
                    pat_strs = [p["pattern"][:40] for p in pats[:3]]
                    lines.append(f"      {topic}: {pat_strs}")
            
            # Full text
            text = part.get("text", "")
            if text:
                lines.append(f"    Text:")
                for text_line in text.split('\n')[:10]:  # First 10 lines
                    if text_line.strip():
                        lines.append(f"        {text_line.strip()}")
            lines.append("")
        lines.append("")
    
    return "\n".join(lines)


def process_exam_code(exam_code: str) -> dict:
    """Process a single exam code and generate part-level diagnostics."""
    questions = load_questions(exam_code)
    if not questions:
        return {"exam_code": exam_code, "uncategorized": 0, "total_parts": 0, "skipped": True}
    
    print(f"  Analyzing {len(questions)} questions at part level...")
    uncategorized, categorized = process_questions_part_level(questions, exam_code)
    
    total_parts = len(uncategorized) + len(categorized)
    
    # Sample regression set to match uncategorized count
    regression = sample_stratified(categorized, len(uncategorized))
    
    # Create output directories
    output_dir = OUTPUT_ROOT / exam_code
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Write uncategorized.json (all parts that classified as Unknown, with full stats)
    with open(data_dir / "uncategorized.json", "w") as f:
        json.dump(uncategorized, f, indent=2)
    
    # Write regression_sample.json (stratified sample of categorized parts, lighter stats)
    with open(data_dir / "regression_sample.json", "w") as f:
        json.dump(regression, f, indent=2)
    
    # Copy topic_subtopics.json
    source_patterns = PLUGINS_ROOT / exam_code / "topic_subtopics.json"
    if source_patterns.exists():
        shutil.copy(source_patterns, data_dir / "topic_subtopics.json")
    
    # Write full summary (no truncation) - keep at root level
    summary = generate_summary(uncategorized, regression, exam_code, total_parts)
    with open(output_dir / "summary.txt", "w") as f:
        f.write(summary)
    
    return {
        "exam_code": exam_code,
        "total_questions": len(questions),
        "total_parts": total_parts,
        "uncategorized_parts": len(uncategorized),
        "categorized_parts": len(categorized),
        "regression_sample": len(regression),
        "uncategorized_rate": f"{len(uncategorized)/total_parts*100:.1f}%" if total_parts else "0%",
        "skipped": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate topic classification diagnostics at part level")
    parser.add_argument("--exam-code", "-e", help="Process specific exam code only")
    args = parser.parse_args()
    
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    
    # Find exam codes to process
    if args.exam_code:
        exam_codes = [args.exam_code]
    else:
        # Check both locations
        legacy_codes = {
            d.name for d in SLICES_ROOT.iterdir()
            if d.is_dir() and not d.name.startswith(".")
            and (d / "_metadata" / "questions.jsonl").exists()
        }
        
        new_codes = set()
        if EXAMS_DIR.exists():
            new_codes = {
                d.name for d in EXAMS_DIR.iterdir()
                if d.is_dir() and not d.name.startswith(".")
                and (d / "_metadata" / "questions.jsonl").exists()
            }
            
        exam_codes = sorted(list(legacy_codes | new_codes))
    
    if not exam_codes:
        print("No exam codes found with questions.jsonl")
        return
    
    results = []
    for code in sorted(exam_codes):
        print(f"Processing {code}...")
        result = process_exam_code(code)
        results.append(result)
        
        if result["skipped"]:
            print(f"  Skipped (no questions)")
        else:
            print(f"  Parts: {result['uncategorized_parts']} uncategorized / {result['total_parts']} total ({result['uncategorized_rate']})")
    
    # Write cross-exam summary
    summary = {
        "generated_at": datetime.now().isoformat(),
        "analysis_level": "part",
        "exam_codes": results,
        "total_uncategorized_parts": sum(r["uncategorized_parts"] for r in results if not r.get("skipped")),
        "total_parts": sum(r["total_parts"] for r in results if not r.get("skipped")),
    }
    with open(OUTPUT_ROOT / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nDiagnostics written to: {OUTPUT_ROOT}")
    print(f"Total uncategorized parts: {summary['total_uncategorized_parts']} / {summary['total_parts']}")


if __name__ == "__main__":
    main()

