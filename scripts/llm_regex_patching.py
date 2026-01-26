"""
LLM-based regex pattern patching.

This module runs an optional patching phase after the main training pipeline:
- Finds weak questions where regex + model struggle
- Uses Qwen LLM to propose new topic-specific keyword/regex candidates  
- Evaluates candidates on the labelled corpus
- Merges good patterns into topic_subtopics_patched.json

Usage:
    python llm_regex_patching.py --exam-code 0450 --questions data/0450/questions_llm_labeled.json ...
"""

from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

try:
    from ollama import Client
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    Client = None  # type: ignore


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Any:
    """Load JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load JSONL file (one JSON object per line)."""
    items = []
    for line in path.read_text(encoding="utf-8").strip().split("\n"):
        if line.strip():
            items.append(json.loads(line))
    return items


def _write_json(path: Path, data: Any) -> None:
    """Write JSON file."""
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, items: List[Dict[str, Any]]) -> None:
    """Write JSONL file."""
    lines = [json.dumps(item, ensure_ascii=False) for item in items]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _normalize_topic_patterns(raw: Any) -> Tuple[Dict[str, Any], bool]:
    """
    Normalize topic_patterns to a dict keyed by topic name.
    
    Handles two input shapes:
    1. List-based: {"topics": [{"name": "...", "patterns": [...]}, ...]}
    2. Dict-based: {"topic_name": {"patterns": [...], ...}, ...}
    
    Returns:
        (normalized_dict, was_list_based) - the second flag is used for
        preserving the original shape on write.
    """
    if "topics" in raw and isinstance(raw.get("topics"), list):
        # List-based shape
        return {t["name"]: t for t in raw["topics"]}, True
    else:
        # Already a mapping
        return raw, False


def _denormalize_topic_patterns(
    topic_patterns: Dict[str, Any],
    was_list_based: bool,
) -> Any:
    """
    Convert normalized topic_patterns back to original shape for writing.
    """
    if was_list_based:
        return {"topics": list(topic_patterns.values())}
    return topic_patterns


def _clean_text(value: str) -> str:
    """Lightly normalise question text."""
    if not value:
        return ""
    cleaned = value.replace("\u00a0", " ")
    # Collapse whitespace
    cleaned = " ".join(cleaned.split())
    return cleaned.strip()


def _escape_for_regex(phrase: str) -> str:
    """Escape special regex characters in a phrase."""
    return re.escape(phrase)


def _phrase_to_pattern(phrase: str) -> str:
    """
    Convert a phrase to a word-boundary regex pattern.
    E.g. "market segment" -> r"\bmarket segment(s)?\b"
    """
    escaped = _escape_for_regex(phrase.lower().strip())
    # Allow optional plural 's' at the end
    if not escaped.endswith("s"):
        return f"\\b{escaped}(s)?\\b"
    return f"\\b{escaped}\\b"


def _parse_json_response(raw: str) -> Dict[str, Any]:
    """Parse JSON from LLM output, tolerating code fences and thinking blocks."""
    if raw is None:
        raise ValueError("Empty response")
    
    def _clean(text: str) -> str:
        # Strip <think>...</think> blocks
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        return text.strip()

    candidates: List[str] = []
    
    # 1. Clean the raw text first
    cleaned = _clean(raw)
    if cleaned:
        candidates.append(cleaned)
    
    # 2. Find JSON-like object
    m_full = re.search(r"\{.*\}", cleaned, re.S)
    if m_full:
        candidates.append(m_full.group(0))

    stripped = raw.strip()
    # 3. Code fence fallback
    if stripped.startswith("```"):
        inner = stripped.strip("` \n\t")
        if inner.lower().startswith("json"):
            inner = inner[4:].strip()
        if inner.endswith("```"):
            inner = inner[:-3].strip()
        candidates.append(_clean(inner))

    # Try candidates
    for cand in reversed(candidates):
        try:
            return json.loads(cand)
        except Exception:
            try:
                return json.loads(cand.replace("'", '"'))
            except Exception:
                continue
                
    raise ValueError(f"Could not parse JSON response. Raw: {raw!r}")


# ---------------------------------------------------------------------------
# Phase 1: Collect patch candidates
# ---------------------------------------------------------------------------

def collect_patch_candidates(
    exam_code: str,
    questions: List[Dict[str, Any]],
    topic_patterns: Dict[str, Any],
    classification_index: Optional[List[Dict[str, Any]]],
    max_candidates_per_topic: int,
    logger: callable = print,
) -> List[Dict[str, Any]]:
    """
    Collect questions that are patch candidates for their topics.
    
    A question is a candidate if:
    - It has no/few pattern matches for its true topic
    - The model misclassified it (if classification_index provided)
    
    Note: Uses topic NAMES directly (not T1/T2 IDs) for robustness.
    classification_index is expected to have:
    - predicted_topic_name or predicted_topic (topic name string)
    - pattern_matches: list of dicts with "topic" key (topic name)
    """
    topic_names = set(topic_patterns.keys())
    
    # Build classification index lookup by question_id
    cls_lookup: Dict[str, Dict[str, Any]] = {}
    if classification_index:
        for row in classification_index:
            # Support multiple key formats
            qid = row.get("question_id", "")
            paper_id = row.get("paper_id", "")
            key = f"{paper_id}_{qid}" if paper_id else qid
            cls_lookup[key] = row
    
    # Collect candidates by topic
    candidates_by_topic: Dict[str, List[Dict[str, Any]]] = {name: [] for name in topic_names}
    
    for q in questions:
        # Try multiple locations for exam_code
        q_exam_code = str(
            q.get("exam_code", "") or 
            q.get("metadata", {}).get("exam_code", "")
        )
        if q_exam_code != exam_code:
            continue
            
        topic_primary = q.get("llm_topic", "")
        if not topic_primary or topic_primary not in topic_names:
            continue
            
        question_id = q.get("question_id", "")
        paper_id = q.get("paper_id", "")
        text = _clean_text(q.get("text_clean") or q.get("text_raw") or "")
        
        if not text:
            continue
        
        reasons: List[str] = []
        
        # Check classification index for this question
        cls_key = f"{paper_id}_{question_id}" if paper_id else question_id
        cls_row = cls_lookup.get(cls_key)
        
        if cls_row:
            # Check if no patterns matched
            # Supports both list of dicts and list of tuples
            pattern_matches = cls_row.get("pattern_matches", [])
            if not pattern_matches:
                reasons.append("no_patterns")
            else:
                # Check if patterns for true topic exist
                # Handle both {"topic": "..."} dicts and (topic_id, ...) tuples
                true_topic_matches = []
                for m in pattern_matches:
                    if isinstance(m, dict):
                        match_topic = m.get("topic", m.get("topic_name", ""))
                    elif isinstance(m, (list, tuple)) and len(m) > 0:
                        match_topic = m[0]  # Assume first element is topic
                    else:
                        continue
                    if match_topic == topic_primary:
                        true_topic_matches.append(m)
                
                if not true_topic_matches:
                    reasons.append("no_patterns_for_true_topic")
            
            # Check model prediction - use topic name directly
            predicted_topic = (
                cls_row.get("predicted_topic_name") or
                cls_row.get("predicted_topic") or
                cls_row.get("topic_pred", "")
            )
            if predicted_topic:
                if predicted_topic != topic_primary:
                    reasons.append("model_misclass")
            else:
                reasons.append("model_no_prediction")
        else:
            # No classification data - check patterns directly
            patterns = topic_patterns.get(topic_primary, {}).get("patterns", [])
            has_match = False
            for pattern in patterns:
                try:
                    if re.search(pattern, text, re.IGNORECASE):
                        has_match = True
                        break
                except re.error:
                    continue
            if not has_match:
                reasons.append("no_patterns")
        
        if reasons:
            candidates_by_topic[topic_primary].append({
                "question_id": question_id,
                "paper_id": paper_id,
                "exam_code": exam_code,
                "topic_primary": topic_primary,
                "text": text,
                "reason": reasons,
            })
    
    # Cap candidates per topic
    all_candidates: List[Dict[str, Any]] = []
    for topic_name, topic_candidates in candidates_by_topic.items():
        if topic_candidates:
            # Sort by number of reasons (more reasons = higher priority)
            topic_candidates.sort(key=lambda x: len(x["reason"]), reverse=True)
            capped = topic_candidates[:max_candidates_per_topic]
            all_candidates.extend(capped)
            logger(f"[patch] Topic '{topic_name}': {len(capped)}/{len(topic_candidates)} candidates")
    
    logger(f"[patch] Total patch candidates: {len(all_candidates)}")
    return all_candidates


# ---------------------------------------------------------------------------
# Phase 2: Build topic bundles and call LLM
# ---------------------------------------------------------------------------

def build_topic_bundles(
    patch_candidates: List[Dict[str, Any]],
    topic_patterns: Dict[str, Any],
    max_examples_per_topic: int = 20,
    max_existing_patterns: int = 10,
) -> List[Dict[str, Any]]:
    """
    Build bundles for LLM processing, one per topic with candidates.
    """
    # Group candidates by topic
    by_topic: Dict[str, List[Dict[str, Any]]] = {}
    for cand in patch_candidates:
        topic = cand["topic_primary"]
        if topic not in by_topic:
            by_topic[topic] = []
        by_topic[topic].append(cand)
    
    bundles: List[Dict[str, Any]] = []
    for topic_name, candidates in by_topic.items():
        topic_data = topic_patterns.get(topic_name, {})
        description = topic_data.get("description", "")
        existing_patterns = topic_data.get("patterns", [])
        
        # Sample existing patterns for context
        sample_patterns = existing_patterns[:max_existing_patterns]
        
        # Get unmatched examples
        examples = [
            {"question_id": c["question_id"], "text": c["text"]}
            for c in candidates[:max_examples_per_topic]
        ]
        
        bundles.append({
            "topic_name": topic_name,
            "topic_description": description,
            "existing_patterns_sample": sample_patterns,
            "unmatched_examples": examples,
        })
    
    return bundles


def call_llm_for_suggestions(
    bundle: Dict[str, Any],
    client: Client,
    model_name: str,
    logger: callable = print,
) -> Dict[str, Any]:
    """
    Call LLM to get pattern suggestions for a topic bundle.
    """
    topic_name = bundle["topic_name"]
    description = bundle.get("topic_description", "")
    existing = bundle.get("existing_patterns_sample", [])
    examples = bundle.get("unmatched_examples", [])
    
    # Build example text
    example_texts = "\n".join([
        f"- Q{i+1}: {ex['text'][:300]}..." if len(ex['text']) > 300 else f"- Q{i+1}: {ex['text']}"
        for i, ex in enumerate(examples[:10])
    ])
    
    existing_str = ", ".join(existing[:8]) if existing else "(none provided)"
    
    prompt = f"""### TASK: SUGGEST KEYWORDS
        TOPIC: {topic_name}
        DESCRIPTION: {description}
        EXISTING PATTERNS (sample): {existing_str}

        The following questions SHOULD belong to this topic but our regex patterns are NOT matching them:
        {example_texts}

        Suggest 5-15 new keyword phrases or terms that appear in these questions and are SPECIFIC to this topic.

        RULES:
        - Only suggest topic-specific phrases (not generic words like "business", "company", "explain")
        - Suggest actual phrases/terms that appear in the question text
        - Avoid duplicating the existing patterns shown above
        - Focus on multi-word phrases when possible (more specific)

        Respond with JSON: {{"topic_name": "{topic_name}", "suggested_keywords": [{{"phrase": "...", "rationale": "..."}}]}}"""

    system_content = (
        "You are an expert iGCSE exam topic classifier specializing in identifying topic-specific keywords. "
        "You MUST respond with valid JSON only. "
        "First provide a 'rationale' for each keyword explaining why it is topic-specific. "
    )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": prompt},
    ]
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat(
                model=model_name,
                messages=messages,
                options={"num_predict": 515 + 512 * attempt, "temperature": 0.0, "top_p": 0.95},
            )
            content = response["message"]["content"].strip()
            if not content:
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                    continue
                return {"topic_name": topic_name, "suggested_keywords": [], "error": "Empty response"}
            
            result = _parse_json_response(content)
            result["topic_name"] = topic_name  # Ensure topic name is correct
            return result
            
        except Exception as e:
            logger(f"[patch] LLM error for '{topic_name}' (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
            else:
                return {"topic_name": topic_name, "suggested_keywords": [], "error": str(e)}
    
    return {"topic_name": topic_name, "suggested_keywords": [], "error": "Max retries exceeded"}


def _create_client() -> "Client":
    """Create a new Ollama client instance (thread-safe factory)."""
    if not OLLAMA_AVAILABLE:
        raise RuntimeError(
            "Ollama library not available. Install with: pip install ollama"
        )
    return Client()


def get_llm_suggestions(
    bundles: List[Dict[str, Any]],
    model_name: str,
    max_workers: int,
    logger: callable = print,
) -> Dict[str, Any]:
    """
    Get LLM suggestions for all topic bundles.
    Uses per-thread Client instances for thread safety.
    """
    # Sanity check with a single client (use /nothink for consistent behavior)
    test_client = _create_client()
    try:
        response = test_client.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": "/nothink You are a diagnostic helper."},
                {"role": "user", "content": "/nothink Respond with the single word READY."},
            ],
        )
        logger(f"[patch] LLM sanity check passed for model '{model_name}'")
    except Exception as e:
        raise RuntimeError(f"LLM sanity check failed: {e}")
    
    results: List[Dict[str, Any]] = []
    
    def _process_bundle(bundle: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single bundle with its own client instance."""
        client = _create_client()
        return call_llm_for_suggestions(bundle, client, model_name, logger)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_bundle, bundle): bundle
            for bundle in bundles
        }
        
        for future in as_completed(futures):
            bundle = futures[future]
            try:
                result = future.result()
                results.append(result)
                n_suggestions = len(result.get("suggested_keywords", []))
                logger(f"[patch] Got {n_suggestions} suggestions for '{bundle['topic_name']}'")
            except Exception as e:
                logger(f"[patch] Error processing '{bundle['topic_name']}': {e}")
                results.append({
                    "topic_name": bundle["topic_name"],
                    "suggested_keywords": [],
                    "error": str(e),
                })
    
    return {"topics": results}


# ---------------------------------------------------------------------------
# Phase 3: Build and evaluate pattern candidates
# ---------------------------------------------------------------------------

def build_pattern_candidates(
    llm_suggestions: Dict[str, Any],
    topic_patterns: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Convert LLM suggestions into pattern candidates.
    """
    candidates_by_topic: Dict[str, List[Dict[str, Any]]] = {}
    
    for topic_result in llm_suggestions.get("topics", []):
        topic_name = topic_result.get("topic_name", "")
        if not topic_name:
            continue
            
        existing_patterns = set(topic_patterns.get(topic_name, {}).get("patterns", []))
        candidates: List[Dict[str, Any]] = []
        
        for kw in topic_result.get("suggested_keywords", []):
            phrase = kw.get("phrase", "").strip()
            if not phrase:
                continue
                
            pattern = _phrase_to_pattern(phrase)
            
            # Skip if pattern already exists
            if pattern in existing_patterns:
                continue
            
            candidates.append({
                "pattern": pattern,
                "source": "llm_patch",
                "phrase": phrase,
                "rationale": kw.get("rationale", ""),
            })
        
        if candidates:
            candidates_by_topic[topic_name] = candidates
    
    return candidates_by_topic


def evaluate_pattern_candidates(
    questions: List[Dict[str, Any]],
    pattern_candidates_by_topic: Dict[str, List[Dict[str, Any]]],
    precision_min: float,
    tp_min: int,
    logger: callable = print,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Evaluate each candidate pattern on the whole corpus.
    """
    # Count questions per topic
    topic_counts: Dict[str, int] = {}
    for q in questions:
        topic = q.get("llm_topic", "")
        if topic:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
    
    evaluated: Dict[str, List[Dict[str, Any]]] = {}
    
    for topic_name, candidates in pattern_candidates_by_topic.items():
        evaluated_candidates: List[Dict[str, Any]] = []
        n_topic = topic_counts.get(topic_name, 0)
        
        for cand in candidates:
            pattern = cand["pattern"]
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                logger(f"[patch] Invalid pattern '{pattern}': {e}")
                continue
            
            tp = 0
            fp = 0
            
            for q in questions:
                text = _clean_text(q.get("text_clean") or q.get("text_raw") or "")
                if not text:
                    continue
                    
                if regex.search(text):
                    q_topic = q.get("llm_topic", "")
                    if q_topic == topic_name:
                        tp += 1
                    else:
                        fp += 1
            
            total = tp + fp
            precision = tp / total if total > 0 else 0.0
            coverage = tp / n_topic if n_topic > 0 else 0.0
            
            keep = tp >= tp_min and precision >= precision_min
            
            evaluated_candidates.append({
                "pattern": pattern,
                "phrase": cand.get("phrase", ""),
                "rationale": cand.get("rationale", ""),
                "tp": tp,
                "fp": fp,
                "precision": round(precision, 3),
                "coverage": round(coverage, 3),
                "keep": keep,
            })
        
        if evaluated_candidates:
            evaluated[topic_name] = evaluated_candidates
            kept = sum(1 for c in evaluated_candidates if c["keep"])
            logger(f"[patch] Topic '{topic_name}': {kept}/{len(evaluated_candidates)} patterns accepted")
    
    return evaluated


# ---------------------------------------------------------------------------
# Phase 4: Merge patched patterns
# ---------------------------------------------------------------------------

def merge_patched_patterns(
    topic_patterns: Dict[str, Any],
    evaluated_candidates: Dict[str, List[Dict[str, Any]]],
    logger: callable = print,
) -> Dict[str, Any]:
    """
    Merge accepted patterns into a new topic_subtopics structure.
    Preserves original pattern order and appends new patterns at the end.
    """
    # Deep copy the original
    patched = json.loads(json.dumps(topic_patterns))
    
    total_added = 0
    
    for topic_name, candidates in evaluated_candidates.items():
        if topic_name not in patched:
            continue
        
        # Preserve original pattern order (use list, not set)
        existing_patterns = patched[topic_name].get("patterns", [])
        existing_set = set(existing_patterns)  # For O(1) lookup only
        new_patterns: List[str] = []
        
        for cand in candidates:
            if cand.get("keep") and cand["pattern"] not in existing_set:
                new_patterns.append(cand["pattern"])
        
        if new_patterns:
            # Append to preserve original order
            patched[topic_name]["patterns"] = existing_patterns + new_patterns
            total_added += len(new_patterns)
            logger(f"[patch] Added {len(new_patterns)} patterns to '{topic_name}'")
    
    logger(f"[patch] Total patterns added: {total_added}")
    return patched


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM-based regex pattern patching for topic classification.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    # Required
    parser.add_argument("--exam-code", required=True, help="Exam code (e.g., 0450)")
    
    # Input files
    parser.add_argument("--questions", required=True, help="Path to questions_llm_labeled.json")
    parser.add_argument("--topic-patterns", required=True, help="Path to baseline topic_subtopics.json")
    parser.add_argument("--classification-index", help="Optional path to classification_index.jsonl")
    
    # Output files
    parser.add_argument("--patch-candidates", help="Output: patch_candidates.jsonl")
    parser.add_argument("--output-patch-suggestions", help="Output: llm_patch_suggestions.json")
    parser.add_argument("--output-patched-topics", help="Output: topic_subtopics_patched.json")
    
    # Thresholds
    parser.add_argument("--max-candidates-per-topic", type=int, default=40, help="Max candidates per topic")
    parser.add_argument("--precision-min", type=float, default=0.7, help="Min precision for pattern acceptance")
    parser.add_argument("--tp-min", type=int, default=2, help="Min true positives for pattern acceptance")
    
    # LLM settings
    parser.add_argument("--llm-model-name", default="qwen3:8b", help="Ollama model name")
    parser.add_argument("--max-workers", type=int, default=8, help="Parallel workers for LLM calls")
    
    # Flags
    parser.add_argument("--dry-run", action="store_true", help="Generate outputs but don't overwrite live files")
    
    args = parser.parse_args()
    
    def log(msg: str) -> None:
        print(msg)
    
    # Resolve paths
    questions_path = Path(args.questions)
    topic_patterns_path = Path(args.topic_patterns)
    
    if not questions_path.exists():
        raise FileNotFoundError(f"Questions file not found: {questions_path}")
    if not topic_patterns_path.exists():
        raise FileNotFoundError(f"Topic patterns file not found: {topic_patterns_path}")
    
    # Default output paths
    data_dir = questions_path.parent
    patch_candidates_path = Path(args.patch_candidates) if args.patch_candidates else data_dir / "patch_candidates.jsonl"
    suggestions_path = Path(args.output_patch_suggestions) if args.output_patch_suggestions else data_dir / "llm_patch_suggestions.json"
    patched_topics_path = Path(args.output_patched_topics) if args.output_patched_topics else topic_patterns_path.parent / "topic_subtopics_patched.json"
    
    # Load inputs
    log(f"[patch] Loading questions from {questions_path}")
    questions = _load_json(questions_path)
    
    log(f"[patch] Loading topic patterns from {topic_patterns_path}")
    topic_patterns_raw = _load_json(topic_patterns_path)
    topic_patterns, was_list_based = _normalize_topic_patterns(topic_patterns_raw)
    
    classification_index = None
    if args.classification_index:
        cls_path = Path(args.classification_index)
        if cls_path.exists():
            log(f"[patch] Loading classification index from {cls_path}")
            classification_index = _load_jsonl(cls_path)
    
    # Phase 1: Collect patch candidates
    log("\n=== Phase 1: Collecting patch candidates ===")
    patch_candidates = collect_patch_candidates(
        exam_code=args.exam_code,
        questions=questions,
        topic_patterns=topic_patterns,
        classification_index=classification_index,
        max_candidates_per_topic=args.max_candidates_per_topic,
        logger=log,
    )
    
    if not patch_candidates:
        log("[patch] No patch candidates found. Exiting.")
        return
    
    log(f"[patch] Writing patch candidates to {patch_candidates_path}")
    _write_jsonl(patch_candidates_path, patch_candidates)
    
    # Phase 2: Build bundles and call LLM
    log("\n=== Phase 2: Getting LLM suggestions ===")
    bundles = build_topic_bundles(
        patch_candidates=patch_candidates,
        topic_patterns=topic_patterns,
    )
    
    llm_suggestions = get_llm_suggestions(
        bundles=bundles,
        model_name=args.llm_model_name,
        max_workers=args.max_workers,
        logger=log,
    )
    
    log(f"[patch] Writing LLM suggestions to {suggestions_path}")
    _write_json(suggestions_path, llm_suggestions)
    
    # Phase 3: Build and evaluate pattern candidates
    log("\n=== Phase 3: Evaluating pattern candidates ===")
    pattern_candidates = build_pattern_candidates(
        llm_suggestions=llm_suggestions,
        topic_patterns=topic_patterns,
    )
    
    evaluated = evaluate_pattern_candidates(
        questions=questions,
        pattern_candidates_by_topic=pattern_candidates,
        precision_min=args.precision_min,
        tp_min=args.tp_min,
        logger=log,
    )
    
    eval_report_path = data_dir / "llm_pattern_eval.json"
    log(f"[patch] Writing pattern evaluation to {eval_report_path}")
    _write_json(eval_report_path, evaluated)
    
    # Phase 4: Merge patched patterns
    log("\n=== Phase 4: Merging patched patterns ===")
    patched = merge_patched_patterns(
        topic_patterns=topic_patterns,
        evaluated_candidates=evaluated,
        logger=log,
    )
    
    if args.dry_run:
        log(f"[patch] DRY RUN: Would write patched topics to {patched_topics_path}")
        # Still write to a temp location for inspection
        dry_run_path = data_dir / "topic_subtopics_patched_DRYRUN.json"
        log(f"[patch] Writing dry-run output to {dry_run_path}")
        output_data = _denormalize_topic_patterns(patched, was_list_based)
        _write_json(dry_run_path, output_data)
    else:
        log(f"[patch] Writing patched topics to {patched_topics_path}")
        output_data = _denormalize_topic_patterns(patched, was_list_based)
        _write_json(patched_topics_path, output_data)
    
    log("\n[patch] Done!")


if __name__ == "__main__":
    main()
