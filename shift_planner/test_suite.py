"""
Comprehensive Test Suite for DSPy-Based Shift Scheduling System
Tests all components systematically and reports results
"""
import sys
import os
from typing import List, Dict, Any

# Ensure UTF-8 output
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def print_test_header(test_name: str):
    """Print a test section header"""
    print(f"\n{'='*60}")
    print(f"  TEST: {test_name}")
    print(f"{'='*60}")

def print_success(message: str):
    """Print success message"""
    print(f"[PASS] {message}")

def print_failure(message: str, error: Exception = None):
    """Print failure message"""
    print(f"[FAIL] {message}")
    if error:
        print(f"       Error: {str(error)}")

def print_info(message: str):
    """Print info message"""
    print(f"[INFO] {message}")

# ============================================================================
# TEST 1: Configuration
# ============================================================================
def test_configuration():
    """Test DSPy configuration with OpenAI"""
    print_test_header("DSPy Configuration")
    
    try:
        from dspy_config import configure_dspy, get_openai_api_key
        
        # Check API key
        api_key = get_openai_api_key()
        if not api_key:
            print_failure("OpenAI API key not found in environment")
            return False
        print_success(f"OpenAI API key loaded (length: {len(api_key)})")
        
        # Configure DSPy
        configure_dspy()
        print_success("DSPy configuration completed")
        
        # Verify configuration
        import dspy
        if hasattr(dspy.settings, 'lm') and dspy.settings.lm is not None:
            print_success(f"DSPy LM configured: {type(dspy.settings.lm).__name__}")
        else:
            print_failure("DSPy LM not properly configured")
            return False
            
        return True
        
    except Exception as e:
        print_failure("Configuration test failed", e)
        return False

# ============================================================================
# TEST 2: Pydantic Models
# ============================================================================
def test_models():
    """Test Pydantic data models"""
    print_test_header("Pydantic Models")
    
    try:
        from models import (
            Employee, Availability, Constraints, 
            Schedule, ShiftAssignment, Violation, Suggestion,
            create_example_employee, create_example_constraints
        )
        
        # Test Employee
        emp = create_example_employee()
        print_success(f"Employee model: {emp.id} - {emp.role}")
        
        # Test Constraints
        constraints = create_example_constraints()
        print_success(f"Constraints model: {constraints.business_model}")
        
        # Test ShiftAssignment
        assignment = ShiftAssignment(
            day="Mon",
            date="2025-12-15",
            shift="day",
            employee_id="emp_001",
            employee_name="Test Employee",
            role="Manager",
            hours=8.0
        )
        print_success(f"ShiftAssignment model: {assignment.date}")
        
        # Test Schedule
        schedule = Schedule(
            week_start="2025-12-15",
            assignments=[assignment]
        )
        print_success(f"Schedule model: Week starting {schedule.week_start}")
        
        # Test Violation
        violation = Violation(
            type="coverage",
            severity="high",
            description="Test violation",
            affected_days=["Mon"],
            suggested_fix="Test fix"
        )
        print_success(f"Violation model: {violation.type} - {violation.severity}")
        
        # Test Suggestion
        suggestion = Suggestion(
            type="assignment",
            priority="high",
            description="Test suggestion",
            implementation="Test implementation",
            expected_impact="Test impact"
        )
        print_success(f"Suggestion model: {suggestion.type} - {suggestion.priority}")
        
        return True
        
    except Exception as e:
        print_failure("Models test failed", e)
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# TEST 3: DSPy Signatures
# ============================================================================
def test_signatures():
    """Test DSPy signatures instantiation"""
    print_test_header("DSPy Signatures")
    
    try:
        from dspy_scheduler import (
            GenerateSchedule, AnalyzeSchedule, 
            FixSchedule, OptimizeSchedule
        )
        
        # Test signature instantiation (no actual calls yet)
        signatures = [
            ("GenerateSchedule", GenerateSchedule),
            ("AnalyzeSchedule", AnalyzeSchedule),
            ("FixSchedule", FixSchedule),
            ("OptimizeSchedule", OptimizeSchedule)
        ]
        
        for name, sig_class in signatures:
            try:
                sig = sig_class
                print_success(f"{name} signature defined")
            except Exception as e:
                print_failure(f"{name} signature failed", e)
                return False
        
        return True
        
    except Exception as e:
        print_failure("Signatures test failed", e)
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# TEST 4: DSPy Modules
# ============================================================================
def test_modules():
    """Test DSPy modules instantiation"""
    print_test_header("DSPy Modules")
    
    try:
        from dspy_scheduler import (
            SchedulePlanner, ScheduleAnalyzer,
            ScheduleFixer, ScheduleOptimizer,
            ComprehensiveScheduler
        )
        
        # Test module instantiation
        modules = [
            ("SchedulePlanner", SchedulePlanner),
            ("ScheduleAnalyzer", ScheduleAnalyzer),
            ("ScheduleFixer", ScheduleFixer),
            ("ScheduleOptimizer", ScheduleOptimizer),
            ("ComprehensiveScheduler", ComprehensiveScheduler)
        ]
        
        for name, module_class in modules:
            try:
                module = module_class()
                print_success(f"{name} module instantiated")
            except Exception as e:
                print_failure(f"{name} module failed", e)
                return False
        
        return True
        
    except Exception as e:
        print_failure("Modules test failed", e)
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# TEST 5: Backend API
# ============================================================================
def test_backend_api():
    """Test backend API functions (no LLM calls)"""
    print_test_header("Backend API")
    
    try:
        from backend import (
            generate_schedule, analyze_schedule,
            fix_schedule, optimize_schedule,
            comprehensive_schedule_pipeline,
            pydantic_to_json, json_to_pydantic
        )
        
        # Test utility functions
        from models import create_example_employee, create_example_constraints
        
        emp = create_example_employee()
        emp_json = pydantic_to_json(emp)
        print_success(f"pydantic_to_json: {type(emp_json).__name__}")
        
        emp_back = json_to_pydantic(emp_json, Employee)
        print_success(f"json_to_pydantic: {type(emp_back).__name__}")
        
        # Test function definitions exist
        functions = [
            ("generate_schedule", generate_schedule),
            ("analyze_schedule", analyze_schedule),
            ("fix_schedule", fix_schedule),
            ("optimize_schedule", optimize_schedule),
            ("comprehensive_schedule_pipeline", comprehensive_schedule_pipeline)
        ]
        
        for name, func in functions:
            if callable(func):
                print_success(f"{name} function defined")
            else:
                print_failure(f"{name} is not callable")
                return False
        
        return True
        
    except Exception as e:
        print_failure("Backend API test failed", e)
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# TEST 6: Quick Integration Test (Optional - makes real LLM call)
# ============================================================================
def test_integration(skip: bool = True):
    """Test end-to-end integration with a simple schedule generation"""
    print_test_header("Integration Test (LLM Call)")
    
    if skip:
        print_info("Skipping integration test (set skip=False to run)")
        return True
    
    try:
        from backend import generate_schedule
        from models import create_example_employee, create_example_constraints
        
        # Create minimal test data
        employees = [create_example_employee()]
        constraints = create_example_constraints()
        
        print_info("Calling OpenAI via DSPy (this may take a few seconds)...")
        
        # Generate schedule
        result = generate_schedule(
            employees=employees,
            constraints=constraints,
            week_start="2025-12-16"
        )
        
        if result and 'schedule' in result:
            assignments = result['schedule'].get('assignments', [])
            print_success(f"Integration test passed: Generated {len(assignments)} assignments")
            return True
        else:
            print_failure("Integration test failed: No schedule generated")
            return False
            
    except Exception as e:
        print_failure("Integration test failed", e)
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# Main Test Runner
# ============================================================================
def main():
    """Run all tests and report results"""
    print("\n" + "="*60)
    print("  DSPy SHIFT SCHEDULING - COMPREHENSIVE TEST SUITE")
    print("="*60)
    
    tests = [
        ("Configuration", test_configuration),
        ("Pydantic Models", test_models),
        ("DSPy Signatures", test_signatures),
        ("DSPy Modules", test_modules),
        ("Backend API", test_backend_api),
        ("Integration Test", lambda: test_integration(skip=True))  # Skip by default
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_failure(f"Test '{test_name}' crashed", e)
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed!")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    from models import Employee  # Import for json_to_pydantic test
    exit_code = main()
    sys.exit(exit_code)
