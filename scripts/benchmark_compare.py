
import time
import statistics
import shutil
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any

# Add src to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

import gcse_toolkit.builder.config as builder_v1_config
import gcse_toolkit.builder.controller as builder_v1_controller
import gcse_toolkit.builder_v2 as builder_v2

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("benchmark")

def benchmark_v1_build(
    cache_path: Path,
    exam_code: str,
    output_dir: Path,
    target_marks: int = 50,
) -> float:
    """Run V1 Builder Benchmark."""
    if output_dir.exists():
        shutil.rmtree(output_dir)
    
    # Configure V1
    config = builder_v1_config.BuilderConfig.from_args(
        metadata_root=cache_path,
        topics=[],  # All topics
        sub_topics=None,
        target_marks=target_marks,
        exam_code=exam_code,
        output_dir=output_dir,
        output_format="pdf",
        include_markschemes=True
    )
    
    start = time.perf_counter()
    try:
        builder_v1_controller.run_builder(config)
    except SystemExit as e:
        print(f"V1 SystemExit: {e}")
    except Exception as e:
        print(f"V1 Failed: {e}")
        raise
        
    return time.perf_counter() - start

def benchmark_v2_build(
    cache_path: Path,
    exam_code: str,
    output_dir: Path,
    target_marks: int = 50,
) -> float:
    """Run V2 Builder Benchmark."""
    if output_dir.exists():
        shutil.rmtree(output_dir)
        
    start = time.perf_counter()
    
    # Configure V2
    config = builder_v2.BuilderConfig(
        cache_path=cache_path,
        exam_code=exam_code,
        target_marks=target_marks,
        output_dir=output_dir,
        include_markscheme=True,
        # Ensure parity
        topics=None, 
        seed=42
    )
    
    try:
        builder_v2.build_exam(config)
    except Exception as e:
        print(f"V2 Failed: {e}")
        raise
        
    return time.perf_counter() - start

def run_comparison(
    cache_path: Path,
    exam_code: str,
    output_root: Path,
    iterations: int = 3
):
    print(f"\n=== BENCHMARK COMPARISON: V1 vs V2 Builder ===")
    print(f"Exam: {exam_code}")
    print(f"Cache: {cache_path}")
    print(f"Iterations: {iterations}")
    print("==============================================\n")
    
    v1_times = []
    v2_times = []
    
    # Warmup ignored? No, let's include all for "cold start" feeling or do 1 warmup.
    
    for i in range(iterations):
        print(f"--- Iteration {i+1}/{iterations} ---")
        
        # Run V1
        v1_out = output_root / f"v1_run_{i}"
        t1 = benchmark_v1_build(cache_path, exam_code, v1_out)
        v1_times.append(t1)
        print(f"  V1: {t1:.4f}s")
        
        # Run V2
        v2_out = output_root / f"v2_run_{i}"
        t2 = benchmark_v2_build(cache_path, exam_code, v2_out)
        v2_times.append(t2)
        print(f"  V2: {t2:.4f}s")
        
        # Speedup
        print(f"  Speedup: {t1/t2:.2f}x")
        
    avg_v1 = statistics.mean(v1_times)
    avg_v2 = statistics.mean(v2_times)
    
    print("\n=== RESULTS ===")
    print(f"V1 Average: {avg_v1:.4f}s")
    print(f"V2 Average: {avg_v2:.4f}s")
    print(f"Overall Speedup: {avg_v1/avg_v2:.2f}x")
    print("===============")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=Path("workspace/slices_cache"))
    parser.add_argument("--code", type=str, default="0450")
    parser.add_argument("--out", type=Path, default=Path("workspace/benchmark_out"))
    args = parser.parse_args()
    
    if not args.cache.exists():
        print(f"Cache not found: {args.cache}")
        exit(1)
        
    run_comparison(args.cache, args.code, args.out)
