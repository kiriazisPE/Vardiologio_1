#!/usr/bin/env python3
"""
CI Evaluation Script - Test reasoning artifacts against golden datasets.

This script is run by CI/CD to ensure reasoning quality before deployment.

Usage:
    python ci/evaluate_reasoning.py
    
Exit Codes:
    0 - All tests passed
    1 - Reasoning regression detected
    2 - Hard constraint violations found
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from reasoning.modules import load_planner
from reasoning.evaluation import score_schedule, detect_regression


def load_golden_cases() -> List[Dict[str, Any]]:
    """Load all golden test cases from datasets/golden/"""
    golden_dir = Path(__file__).parent.parent / "datasets" / "golden"
    cases = []
    
    for json_file in golden_dir.glob("*.json"):
        with open(json_file, "r", encoding="utf-8") as f:
            case = json.load(f)
            case["_filename"] = json_file.name
            cases.append(case)
    
    return cases


def evaluate_case(planner, case: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate planner on a single test case.
    
    Returns:
        {
            "case_name": str,
            "passed": bool,
            "metrics": {...},
            "expected": {...},
            "failures": [str]
        }
    """
    print(f"\n📋 Testing: {case['name']}")
    print(f"   {case.get('description', '')}")
    
    # Generate schedule using reasoning engine
    result = planner(
        employees=case["employees"],
        shifts_required=case["shifts_required"],
        roles_required=case["roles_required"],
        constraints=case["constraints"],
        week_start=case["week_start"]
    )
    
    schedule = result["schedule"]
    
    # Score the schedule
    metrics = score_schedule(
        schedule=schedule,
        constraints=case["constraints"],
        employees=case["employees"],
        roles_required=case["roles_required"]
    )
    
    # Check against expected thresholds
    expected = case["expected"]
    failures = []
    
    if metrics["hard_violations"] > expected["max_hard_violations"]:
        failures.append(
            f"❌ Hard violations: {metrics['hard_violations']} > {expected['max_hard_violations']} (expected)"
        )
    
    if metrics["soft_violations"] > expected["max_soft_violations"]:
        failures.append(
            f"⚠️  Soft violations: {metrics['soft_violations']} > {expected['max_soft_violations']} (expected)"
        )
    
    if metrics["coverage_score"] < expected["min_coverage_score"]:
        failures.append(
            f"❌ Coverage: {metrics['coverage_score']:.1f}% < {expected['min_coverage_score']}% (expected)"
        )
    
    if metrics["overall_score"] < expected["min_overall_score"]:
        failures.append(
            f"⚠️  Overall score: {metrics['overall_score']:.1f} < {expected['min_overall_score']} (expected)"
        )
    
    passed = len(failures) == 0
    
    # Print results
    if passed:
        print(f"   ✅ PASSED")
    else:
        print(f"   ❌ FAILED:")
        for failure in failures:
            print(f"      {failure}")
    
    print(f"   Metrics: hard={metrics['hard_violations']}, soft={metrics['soft_violations']}, " +
          f"coverage={metrics['coverage_score']:.1f}%, overall={metrics['overall_score']:.1f}")
    
    return {
        "case_name": case["name"],
        "passed": passed,
        "metrics": metrics,
        "expected": expected,
        "failures": failures
    }


def main():
    """Main CI evaluation runner."""
    print("=" * 70)
    print("🧪 DSPy Reasoning Evaluation - CI Gate")
    print("=" * 70)
    
    # Load reasoning artifact
    print("\n📦 Loading reasoning artifact...")
    try:
        planner = load_planner(version="latest", reasoning_mode="chain_of_thought")
        print("   ✅ Loaded: ShiftPlanner (chain_of_thought)")
    except Exception as e:
        print(f"   ❌ Failed to load planner: {e}")
        return 2
    
    # Load golden cases
    print("\n📂 Loading golden test cases...")
    cases = load_golden_cases()
    print(f"   Found {len(cases)} test case(s)")
    
    if not cases:
        print("   ⚠️  No golden cases found! Create test cases in datasets/golden/")
        return 0  # Don't fail if no tests yet (early development)
    
    # Evaluate each case
    print("\n" + "=" * 70)
    print("Running Tests")
    print("=" * 70)
    
    results = []
    for case in cases:
        result = evaluate_case(planner, case)
        results.append(result)
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Summary")
    print("=" * 70)
    
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = len(results) - passed_count
    
    print(f"\nTotal Cases: {len(results)}")
    print(f"✅ Passed: {passed_count}")
    print(f"❌ Failed: {failed_count}")
    
    # Check for hard violations (CI blocker)
    hard_violations_found = any(
        r["metrics"]["hard_violations"] > r["expected"]["max_hard_violations"]
        for r in results
    )
    
    if hard_violations_found:
        print("\n🚨 HARD CONSTRAINT VIOLATIONS DETECTED - BLOCKING DEPLOYMENT")
        return 2
    
    if failed_count > 0:
        print("\n⚠️  SOFT CONSTRAINT VIOLATIONS - REVIEW REQUIRED")
        print("   (Deployment allowed but quality degraded)")
        return 1
    
    print("\n✅ ALL TESTS PASSED - READY FOR DEPLOYMENT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
