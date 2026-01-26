"""
Benchmark script for Builder/Extractor V2 performance.
Measures execution time for core pipeline operations.
"""

import time
import statistics
from pathlib import Path
from typing import List, Optional
import shutil
import logging

import sys
from pathlib import Path

# Add src to path so we can import gcse_toolkit
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from gcse_toolkit.extractor_v2.pipeline import extract_question_paper, ExtractionConfig
    from gcse_toolkit.builder_v2 import build_exam, BuilderConfig
except ImportError as e:
    print(f"Error: Could not import V2 modules: {e}")
    exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("benchmark")

def benchmark_extraction(
    pdf_path: Path, 
    output_root: Path, 
    exam_code: str, 
    iterations: int = 3
):
    """Benchmark extraction performance."""
    print(f"\n--- Benchmarking Extraction (x{iterations}) ---")
    print(f"File: {pdf_path.name}")
    
    times = []
    
    for i in range(iterations):
        # Clean output dir to force fresh extraction
        if output_root.exists():
            shutil.rmtree(output_root)
        
        start = time.perf_counter()
        
        config = ExtractionConfig(debug_detections=False)  # Disable debug for fair speed test
        
        result = extract_question_paper(
            pdf_path=pdf_path,
            output_dir=output_root,
            exam_code=exam_code,
            config=config
        )
        
        duration = time.perf_counter() - start
        times.append(duration)
        print(f"Run {i+1}: {duration:.2f}s ({result.question_count} questions)")
    
    avg_time = statistics.mean(times)
    print(f"Average: {avg_time:.2f}s")
    print(f"Min: {min(times):.2f}s")
    print(f"Max: {max(times):.2f}s")
    
    return avg_time

def benchmark_build(
    cache_path: Path, 
    exam_code: str, 
    output_dir: Path, 
    target_marks: int = 50,
    iterations: int = 5
):
    """Benchmark build performance."""
    print(f"\n--- Benchmarking Build (x{iterations}) ---")
    print(f"Exam: {exam_code}, Target: {target_marks} marks")
    
    times = []
    
    for i in range(iterations):
        # Clean output
        if output_dir.exists():
            shutil.rmtree(output_dir)
            
        start = time.perf_counter()
        
        config = BuilderConfig(
            cache_path=cache_path,
            exam_code=exam_code,
            target_marks=target_marks,
            seed=12345 + i,  # Different seed
            output_dir=output_dir,
            tolerance=2
        )
        
        result = build_exam(config)
        
        duration = time.perf_counter() - start
        times.append(duration)
        print(f"Run {i+1}: {duration:.4f}s ({result.page_count} pages, {result.total_marks} marks)")
        
    avg_time = statistics.mean(times)
    print(f"Average: {avg_time:.4f}s")
    print(f"Min: {min(times):.4f}s")
    print(f"Max: {max(times):.4f}s")
    
    return avg_time

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Benchmark V2 Pipeline")
    parser.add_argument("--pdf", type=Path, help="Path to sample PDF for extraction benchmark")
    parser.add_argument("--cache", type=Path, help="Path to slices cache for build benchmark")
    parser.add_argument("--code", type=str, default="0478", help="Exam code")
    
    args = parser.parse_args()
    
    # Defaults for dev environment if not provided
    root = Path.cwd()
    tmp_out = root / "benchmark_output"
    
    if args.pdf and args.pdf.exists():
        benchmark_extraction(args.pdf, tmp_out / "extracted", args.code)
    else:
        print("Skipping extraction benchmark (provide --pdf)")
        
    if args.cache and args.cache.exists():
        benchmark_build(args.cache, args.code, tmp_out / "built")
    else:
        print("Skipping build benchmark (provide --cache)")
        
    # Cleanup
    if tmp_out.exists():
        shutil.rmtree(tmp_out)
