#!/usr/bin/env python3
"""
Generate Comparison Report from Pipeline Test Results

Reads the collected evaluation results and generates a comprehensive
markdown report comparing pipeline performance across all variants and exams.

Usage:
    python scripts/generate_comparison_report.py
    python scripts/generate_comparison_report.py --input comparison_results/specific_file.json
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
RESULTS_DIR = SCRIPTS_DIR / "comparison_results"


def load_results(input_file: Path) -> dict:
    """Load results from JSON file."""
    if not input_file.exists():
        raise FileNotFoundError(f"Results file not found: {input_file}")
    
    with open(input_file) as f:
        return json.load(f)


def extract_accuracy(result: dict, set_name: str) -> float | None:
    """Extract accuracy for a specific test set from results."""
    if not result or "results" not in result:
        return None
    
    for r in result.get("results", []):
        if r.get("name", "").lower() == set_name.lower():
            return r.get("accuracy")
    
    return None


def get_best_variant_for_exam(exam_results: dict, metric: str = "accuracy") -> tuple[str, float]:
    """Find the best performing variant for an exam."""
    best_variant = None
    best_score = -1
    
    for variant_name, variant_data in exam_results.items():
        if "error" in variant_data:
            continue
        
        exams = variant_data.get("exams", {})
        for exam_code, exam_result in exams.items():
            acc = extract_accuracy(exam_result, "Unknown") or extract_accuracy(exam_result, "Holdout")
            if acc and acc > best_score:
                best_score = acc
                best_variant = variant_name
    
    return best_variant, best_score


def generate_executive_summary(results: dict) -> str:
    """Generate executive summary section."""
    lines = [
        "## Executive Summary\n",
        f"**Test Run**: {results['test_run']['timestamp']}\n",
        f"**Exam Codes Tested**: {len(results['test_run']['exam_codes'])}\n",
        f"**Variants Tested**: {', '.join(results['test_run']['variants_tested'])}\n",
        ""
    ]
    
    # Calculate overall stats per variant
    variant_stats = {}
    
    for variant_name in results['test_run']['variants_tested']:
        variant_data = results['results'].get(variant_name, {})
        if "error" in variant_data:
            variant_stats[variant_name] = {"error": variant_data["error"]}
            continue
        
        exams = variant_data.get("exams", {})
        accuracies = []
        
        for exam_code, exam_result in exams.items():
            if "error" in exam_result:
                continue
            # Try Unknown for original, Holdout for simplified
            acc = extract_accuracy(exam_result, "Unknown") or extract_accuracy(exam_result, "Holdout")
            if acc is not None:
                accuracies.append(acc)
        
        if accuracies:
            variant_stats[variant_name] = {
                "mean_accuracy": sum(accuracies) / len(accuracies),
                "min_accuracy": min(accuracies),
                "max_accuracy": max(accuracies),
                "count": len(accuracies),
                "runtime": variant_data.get("pipeline_elapsed_seconds")
            }
        else:
            variant_stats[variant_name] = {"error": "No valid results"}
    
    lines.append("### Overall Performance\n")
    lines.append("| Variant | Mean Accuracy | Min | Max | Exams | Runtime |")
    lines.append("|---------|---------------|-----|-----|-------|---------|")
    
    for variant_name, stats in variant_stats.items():
        if "error" in stats:
            lines.append(f"| {variant_name} | Error: {stats['error'][:30]}... | - | - | - | - |")
        else:
            runtime = f"{stats['runtime']:.0f}s" if stats.get('runtime') else "N/A"
            lines.append(
                f"| {variant_name} | {stats['mean_accuracy']:.1%} | "
                f"{stats['min_accuracy']:.1%} | {stats['max_accuracy']:.1%} | "
                f"{stats['count']} | {runtime} |"
            )
    
    lines.append("")
    return "\n".join(lines)


def generate_per_exam_table(results: dict) -> str:
    """Generate per-exam comparison table."""
    lines = [
        "## Per-Exam Breakdown\n",
    ]
    
    exam_codes = results['test_run']['exam_codes']
    variant_names = results['test_run']['variants_tested']
    
    # Build header
    header = "| Exam |"
    separator = "|------|"
    for v in variant_names:
        short_name = v.replace("original_", "").replace("simplified", "simp").replace("_", " ").title()
        header += f" {short_name} |"
        separator += "--------|"
    
    lines.append(header)
    lines.append(separator)
    
    # Build rows
    for exam_code in exam_codes:
        row = f"| {exam_code} |"
        
        for variant_name in variant_names:
            variant_data = results['results'].get(variant_name, {})
            
            if "error" in variant_data:
                row += " ❌ Error |"
                continue
            
            exam_result = variant_data.get("exams", {}).get(exam_code)
            
            if not exam_result or "error" in exam_result:
                row += " ❌ N/A |"
                continue
            
            # Get primary accuracy metric
            acc = extract_accuracy(exam_result, "Unknown") or extract_accuracy(exam_result, "Holdout")
            unknown_count = 0
            total = 0
            
            for r in exam_result.get("results", []):
                if r.get("name") in ["Unknown", "Holdout"]:
                    unknown_count = r.get("unknown", 0)
                    total = r.get("total", 0)
                    break
            
            if acc is not None:
                # Mark best with bold
                row += f" {acc:.1%} |"
            else:
                row += " - |"
        
        lines.append(row)
    
    lines.append("")
    return "\n".join(lines)


def generate_detailed_breakdown(results: dict) -> str:
    """Generate detailed breakdown for each exam."""
    lines = [
        "## Detailed Results\n",
    ]
    
    exam_codes = results['test_run']['exam_codes']
    variant_names = results['test_run']['variants_tested']
    
    for exam_code in exam_codes:
        lines.append(f"### Exam: {exam_code}\n")
        
        for variant_name in variant_names:
            variant_data = results['results'].get(variant_name, {})
            
            if "error" in variant_data:
                lines.append(f"**{variant_name}**: ❌ Pipeline Error\n")
                continue
            
            exam_result = variant_data.get("exams", {}).get(exam_code)
            
            if not exam_result or "error" in exam_result:
                lines.append(f"**{variant_name}**: ❌ No evaluation data\n")
                continue
            
            lines.append(f"**{variant_name}**:\n")
            lines.append("| Set | Accuracy | Correct | Total | Unknown |")
            lines.append("|-----|----------|---------|-------|---------|")
            
            for r in exam_result.get("results", []):
                lines.append(
                    f"| {r['name']} | {r['accuracy']:.1%} | "
                    f"{r['correct']} | {r['total']} | {r['unknown']} |"
                )
            
            lines.append("")
        
        lines.append("---\n")
    
    return "\n".join(lines)


def generate_analysis(results: dict) -> str:
    """Generate analysis section."""
    lines = [
        "## Analysis\n",
    ]
    
    variant_names = results['test_run']['variants_tested']
    exam_codes = results['test_run']['exam_codes']
    
    # Find best variant per exam
    best_per_exam = {}
    
    for exam_code in exam_codes:
        best_variant = None
        best_acc = -1
        
        for variant_name in variant_names:
            variant_data = results['results'].get(variant_name, {})
            if "error" in variant_data:
                continue
            
            exam_result = variant_data.get("exams", {}).get(exam_code)
            if not exam_result or "error" in exam_result:
                continue
            
            acc = extract_accuracy(exam_result, "Unknown") or extract_accuracy(exam_result, "Holdout")
            if acc and acc > best_acc:
                best_acc = acc
                best_variant = variant_name
        
        if best_variant:
            best_per_exam[exam_code] = (best_variant, best_acc)
    
    # Count wins per variant
    wins = {}
    for variant_name in variant_names:
        wins[variant_name] = sum(1 for v, _ in best_per_exam.values() if v == variant_name)
    
    lines.append("### Winner Count by Variant\n")
    lines.append("| Variant | Wins |")
    lines.append("|---------|------|")
    
    for variant_name, win_count in sorted(wins.items(), key=lambda x: -x[1]):
        lines.append(f"| {variant_name} | {win_count} |")
    
    lines.append("")
    
    # Best variant per exam
    lines.append("### Best Variant per Exam\n")
    lines.append("| Exam | Best Variant | Accuracy |")
    lines.append("|------|--------------|----------|")
    
    for exam_code, (variant, acc) in sorted(best_per_exam.items()):
        lines.append(f"| {exam_code} | {variant} | {acc:.1%} |")
    
    lines.append("")
    
    return "\n".join(lines)


def generate_recommendations(results: dict) -> str:
    """Generate recommendations section."""
    lines = [
        "## Recommendations\n",
        "> [!NOTE]",
        "> These recommendations are auto-generated based on the test results.\n",
        ""
    ]
    
    # Calculate which approach wins overall
    variant_names = results['test_run']['variants_tested']
    exam_codes = results['test_run']['exam_codes']
    
    variant_scores = {v: [] for v in variant_names}
    
    for exam_code in exam_codes:
        for variant_name in variant_names:
            variant_data = results['results'].get(variant_name, {})
            if "error" in variant_data:
                continue
            
            exam_result = variant_data.get("exams", {}).get(exam_code)
            if not exam_result or "error" in exam_result:
                continue
            
            acc = extract_accuracy(exam_result, "Unknown") or extract_accuracy(exam_result, "Holdout")
            if acc:
                variant_scores[variant_name].append(acc)
    
    # Find overall best
    best_variant = None
    best_mean = -1
    
    for variant_name, scores in variant_scores.items():
        if scores:
            mean = sum(scores) / len(scores)
            if mean > best_mean:
                best_mean = mean
                best_variant = variant_name
    
    if best_variant:
        lines.append(f"**Overall Best Performer**: `{best_variant}` with mean accuracy of {best_mean:.1%}\n")
    
    # Check if enrichment helps
    if "original_no_enrich" in variant_scores and "original_with_enrich" in variant_scores:
        no_enrich = variant_scores["original_no_enrich"]
        with_enrich = variant_scores["original_with_enrich"]
        
        if no_enrich and with_enrich:
            no_mean = sum(no_enrich) / len(no_enrich)
            with_mean = sum(with_enrich) / len(with_enrich)
            diff = with_mean - no_mean
            
            if diff > 0.02:
                lines.append(f"- **Regex Enrichment adds value**: +{diff:.1%} improvement on average\n")
            elif diff < -0.02:
                lines.append(f"- **Regex Enrichment may not help**: -{abs(diff):.1%} difference on average\n")
            else:
                lines.append(f"- **Regex Enrichment impact is marginal**: {diff:+.1%} difference\n")
    
    lines.append("")
    return "\n".join(lines)


def generate_report(results: dict) -> str:
    """Generate the full comparison report."""
    lines = [
        "# Plugin Generation Pipeline Comparison Report\n",
        generate_executive_summary(results),
        generate_per_exam_table(results),
        generate_analysis(results),
        generate_detailed_breakdown(results),
        generate_recommendations(results),
        "---\n",
        f"*Generated: {datetime.now().isoformat()}*\n",
    ]
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate comparison report from test results")
    parser.add_argument(
        "--input",
        type=Path,
        default=RESULTS_DIR / "latest.json",
        help="Path to results JSON file (default: comparison_results/latest.json)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=SCRIPTS_DIR / "comparison_report.md",
        help="Path to output markdown report"
    )
    
    args = parser.parse_args()
    
    # Load results
    try:
        results = load_results(args.input)
    except FileNotFoundError as e:
        logger.error(str(e))
        logger.info("Run comparison tests first: python scripts/run_comparison_tests.py")
        return 1
    
    # Generate report
    report = generate_report(results)
    
    # Save report
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(report)
    
    logger.info(f"Report generated: {args.output}")
    
    # Also print summary
    print("\n" + "="*60)
    print("REPORT SUMMARY")
    print("="*60)
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print(f"Exams tested: {len(results['test_run']['exam_codes'])}")
    print(f"Variants: {', '.join(results['test_run']['variants_tested'])}")
    
    return 0


if __name__ == "__main__":
    exit(main())
