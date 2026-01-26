#!/usr/bin/env python3
"""
Plugin Generation Pipeline Comparison Test Runner

Runs both plugin generation pipelines (with and without regex enrichment + Simplified)
across all exam codes and collects evaluation metrics for comparison.

Usage:
    # Dry run (shows what would be done)
    python scripts/run_comparison_tests.py --dry-run
    
    # Test single exam, all variants
    python scripts/run_comparison_tests.py --exams 0478 --variants all
    
    # Full test suite
    python scripts/run_comparison_tests.py --exams all --variants all
    
    # Specific variants
    python scripts/run_comparison_tests.py --exams 0478 --variants original_no_enrich,simplified
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

PIPELINE_ORIGINAL = SCRIPTS_DIR / "Plugin Generation"
PIPELINE_SIMPLIFIED = SCRIPTS_DIR / "Plugin Generation Simplified"

STAGED_ORIGINAL = PIPELINE_ORIGINAL / "_staged_plugins"
STAGED_SIMPLIFIED = PIPELINE_SIMPLIFIED / "_staged_plugins"
RESOURCES_ORIGINAL = PIPELINE_ORIGINAL / "_resources"
RESOURCES_SIMPLIFIED = PIPELINE_SIMPLIFIED / "_resources"

RESULTS_DIR = SCRIPTS_DIR / "comparison_results"


@dataclass
class TestVariant:
    """Configuration for a test variant."""
    name: str
    display_name: str
    pipeline_dir: Path
    staged_dir: Path
    stages: str  # Comma-separated stage numbers
    enrich: bool = False
    skip_llm: bool = True  # Assume LLM labels exist
    eval_script_path: str = ""  # Relative to pipeline_dir


# Define test variants
VARIANTS = {
    "original_no_enrich": TestVariant(
        name="original_no_enrich",
        display_name="Original (No Regex Enrich)",
        pipeline_dir=PIPELINE_ORIGINAL,
        staged_dir=STAGED_ORIGINAL,
        stages="1,2,3,4,5,6",
        enrich=False,
        eval_script_path="6) Build Model/evaluate_model.py"
    ),
    "original_with_enrich": TestVariant(
        name="original_with_enrich",
        display_name="Original (With Regex Enrich)", 
        pipeline_dir=PIPELINE_ORIGINAL,
        staged_dir=STAGED_ORIGINAL,
        stages="1,2,3,4,5,6",
        enrich=True,
        eval_script_path="6) Build Model/evaluate_model.py"
    ),
    "simplified": TestVariant(
        name="simplified",
        display_name="Simplified (LLM-First)",
        pipeline_dir=PIPELINE_SIMPLIFIED,
        staged_dir=STAGED_SIMPLIFIED,
        stages="1,2,3,4,5",
        enrich=False,
        skip_llm=True,
        eval_script_path="5) Build Model/evaluate_model.py"
    ),
}


def get_available_exam_codes() -> list[str]:
    """Get exam codes that are available in the Original pipeline's _resources."""
    if not RESOURCES_ORIGINAL.exists():
        logger.error(f"Resources directory not found: {RESOURCES_ORIGINAL}")
        return []
    
    exam_codes = []
    for d in RESOURCES_ORIGINAL.iterdir():
        if d.is_dir() and d.name.isdigit():
            exam_codes.append(d.name)
    return sorted(exam_codes)


def clean_staged_plugins(staged_dir: Path, dry_run: bool = False) -> None:
    """Remove all exam directories within _staged_plugins."""
    if not staged_dir.exists():
        logger.info(f"Staged directory does not exist, skipping cleanup: {staged_dir}")
        return
    
    exam_dirs = [d for d in staged_dir.iterdir() if d.is_dir()]
    
    if dry_run:
        logger.info(f"[DRY RUN] Would clean {len(exam_dirs)} directories from {staged_dir}")
        return
    
    for exam_dir in exam_dirs:
        try:
            shutil.rmtree(exam_dir)
            logger.debug(f"Removed: {exam_dir}")
        except Exception as e:
            logger.warning(f"Failed to remove {exam_dir}: {e}")
    
    logger.info(f"Cleaned {len(exam_dirs)} directories from {staged_dir}")


def run_pipeline(variant: TestVariant, exam_codes: list[str], dry_run: bool = False) -> dict:
    """Run the pipeline for a variant and return timing info."""
    controller_script = variant.pipeline_dir / "generate-plugin.py"
    
    if not controller_script.exists():
        logger.error(f"Controller script not found: {controller_script}")
        return {"error": "Controller script not found"}
    
    # Build command
    cmd = [
        sys.executable,
        str(controller_script),
        "--exams", ",".join(exam_codes),
        "--stages", variant.stages,
    ]
    
    if variant.enrich:
        cmd.append("--enrich")
    
    if variant.skip_llm and "skip-llm" in get_script_args(controller_script):
        cmd.append("--skip-llm")
    
    logger.info(f"Running: {' '.join(cmd)}")
    
    if dry_run:
        logger.info(f"[DRY RUN] Would execute: {' '.join(cmd)}")
        return {"dry_run": True}
    
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout per variant
        )
        elapsed = time.time() - start_time
        
        if result.returncode != 0:
            logger.error(f"Pipeline failed for {variant.name}:\n{result.stderr}")
            return {"error": result.stderr, "elapsed_seconds": elapsed}
        
        return {"success": True, "elapsed_seconds": elapsed, "stdout": result.stdout}
        
    except subprocess.TimeoutExpired:
        logger.error(f"Pipeline timed out for {variant.name}")
        return {"error": "Timeout", "elapsed_seconds": 3600}
    except Exception as e:
        logger.error(f"Pipeline error for {variant.name}: {e}")
        return {"error": str(e)}


def get_script_args(script_path: Path) -> list[str]:
    """Get available arguments from a script by running --help."""
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.lower()
    except Exception:
        return ""


def run_evaluation(variant: TestVariant, exam_code: str, dry_run: bool = False) -> Optional[dict]:
    """Run evaluation for a specific exam and collect results."""
    eval_script = variant.pipeline_dir / variant.eval_script_path
    
    if not eval_script.exists():
        logger.warning(f"Evaluation script not found: {eval_script}")
        return None
    
    output_json = variant.staged_dir / exam_code / "data" / "evaluation_results.json"
    
    cmd = [
        sys.executable,
        str(eval_script),
        "-e", exam_code,
        "--output-json", str(output_json)
    ]
    
    if dry_run:
        logger.info(f"[DRY RUN] Would run: {' '.join(cmd)}")
        return {"dry_run": True}
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            logger.warning(f"Evaluation failed for {exam_code}: {result.stderr}")
            return None
        
        # Read the generated JSON
        if output_json.exists():
            with open(output_json) as f:
                return json.load(f)
        else:
            logger.warning(f"Output JSON not created: {output_json}")
            return None
            
    except Exception as e:
        logger.error(f"Evaluation error for {exam_code}: {e}")
        return None


def collect_all_evaluations(variant: TestVariant, exam_codes: list[str], dry_run: bool = False) -> dict:
    """Collect evaluation results for all exam codes."""
    results = {}
    
    for exam_code in exam_codes:
        logger.info(f"Evaluating {exam_code}...")
        eval_result = run_evaluation(variant, exam_code, dry_run)
        if eval_result:
            results[exam_code] = eval_result
        else:
            results[exam_code] = {"error": "Evaluation failed or no data"}
    
    return results


def run_full_comparison(exam_codes: list[str], variant_names: list[str], dry_run: bool = False) -> dict:
    """Run full comparison across all variants and exam codes."""
    
    all_results = {
        "test_run": {
            "timestamp": datetime.now().isoformat(),
            "exam_codes": exam_codes,
            "variants_tested": variant_names,
        },
        "results": {}
    }
    
    for variant_name in variant_names:
        variant = VARIANTS.get(variant_name)
        if not variant:
            logger.error(f"Unknown variant: {variant_name}")
            continue
        
        logger.info(f"\n{'='*60}")
        logger.info(f"VARIANT: {variant.display_name}")
        logger.info(f"{'='*60}")
        
        # Clean staged plugins
        logger.info(f"Cleaning staged plugins for {variant.name}...")
        clean_staged_plugins(variant.staged_dir, dry_run)
        
        # Run pipeline
        logger.info(f"Running pipeline for {variant.name}...")
        pipeline_result = run_pipeline(variant, exam_codes, dry_run)
        
        if pipeline_result.get("error"):
            logger.error(f"Pipeline failed: {pipeline_result['error']}")
            all_results["results"][variant_name] = {
                "error": pipeline_result["error"],
                "exams": {}
            }
            continue
        
        # Collect evaluations
        logger.info(f"Collecting evaluations for {variant.name}...")
        eval_results = collect_all_evaluations(variant, exam_codes, dry_run)
        
        all_results["results"][variant_name] = {
            "pipeline_elapsed_seconds": pipeline_result.get("elapsed_seconds"),
            "exams": eval_results
        }
    
    return all_results


def save_results(results: dict, dry_run: bool = False) -> Path:
    """Save results to JSON file."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = RESULTS_DIR / f"comparison_{timestamp}.json"
    
    if dry_run:
        logger.info(f"[DRY RUN] Would save results to: {output_file}")
        return output_file
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Results saved to: {output_file}")
    
    # Also save as 'latest.json' for easy access
    latest_file = RESULTS_DIR / "latest.json"
    with open(latest_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="Plugin Generation Pipeline Comparison Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Variants:
  original_no_enrich   - Original pipeline without regex enrichment (stages 1-6)
  original_with_enrich - Original pipeline WITH regex enrichment (stages 1-6 + enrich)
  simplified           - Simplified LLM-first pipeline (stages 1-5)

Examples:
  %(prog)s --dry-run
  %(prog)s --exams 0478 --variants all
  %(prog)s --exams all --variants original_no_enrich,simplified
        """
    )
    
    parser.add_argument(
        "--exams",
        default="all",
        help="Comma-separated exam codes or 'all' (default: all)"
    )
    parser.add_argument(
        "--variants",
        default="all",
        help="Comma-separated variant names or 'all' (default: all)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without executing"
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Skip cleaning staged plugins between variants"
    )
    
    args = parser.parse_args()
    
    # Parse exam codes
    if args.exams.lower() == "all":
        exam_codes = get_available_exam_codes()
        if not exam_codes:
            logger.error("No exam codes found in _resources directory")
            sys.exit(1)
    else:
        exam_codes = [c.strip() for c in args.exams.split(",")]
    
    # Normalize exam codes
    exam_codes = [c.zfill(4) if c.isdigit() and len(c) < 4 else c for c in exam_codes]
    
    # Parse variants
    if args.variants.lower() == "all":
        variant_names = list(VARIANTS.keys())
    else:
        variant_names = [v.strip() for v in args.variants.split(",")]
        for v in variant_names:
            if v not in VARIANTS:
                logger.error(f"Unknown variant: {v}. Available: {list(VARIANTS.keys())}")
                sys.exit(1)
    
    logger.info(f"Exam codes: {exam_codes}")
    logger.info(f"Variants: {variant_names}")
    logger.info(f"Dry run: {args.dry_run}")
    
    # Run comparison
    results = run_full_comparison(exam_codes, variant_names, args.dry_run)
    
    # Save results
    output_file = save_results(results, args.dry_run)
    
    logger.info(f"\n{'='*60}")
    logger.info("COMPARISON COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Results: {output_file}")
    logger.info(f"To generate report: python scripts/generate_comparison_report.py")


if __name__ == "__main__":
    main()
