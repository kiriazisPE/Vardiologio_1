# -*- coding: utf-8 -*-
"""
Backend Helper Functions for Shift Scheduling
Provides high-level API for Streamlit and other frontends.
"""

import json
from typing import List, Dict, Any, Optional, Type
from datetime import date, datetime, timedelta
from pydantic import BaseModel

from models import (
    Employee, Availability, Constraints, Schedule, ShiftAssignment,
    Violation, Suggestion, ScheduleAnalysis, ScheduleRequest, ScheduleResponse
)
from dspy_scheduler import (
    SchedulePlanner, ScheduleAnalyzer, ScheduleFixer, ScheduleOptimizer,
    ComprehensiveScheduler
)
from dspy_config import is_configured, configure_dspy


# ============================================================================
# Module-level instances (lazy initialization)
# ============================================================================

_planner: Optional[SchedulePlanner] = None
_analyzer: Optional[ScheduleAnalyzer] = None
_fixer: Optional[ScheduleFixer] = None
_optimizer: Optional[ScheduleOptimizer] = None
_comprehensive: Optional[ComprehensiveScheduler] = None


def _ensure_modules():
    """Ensure DSPy modules are initialized."""
    global _planner, _analyzer, _fixer, _optimizer, _comprehensive
    
    if not is_configured():
        success = configure_dspy()
        if not success:
            raise RuntimeError("Failed to configure DSPy. Check your OPENAI_API_KEY.")
    
    if _planner is None:
        _planner = SchedulePlanner()
    if _analyzer is None:
        _analyzer = ScheduleAnalyzer()
    if _fixer is None:
        _fixer = ScheduleFixer()
    if _optimizer is None:
        _optimizer = ScheduleOptimizer()
    if _comprehensive is None:
        _comprehensive = ComprehensiveScheduler()


# ============================================================================
# Helper Functions - Data Conversion
# ============================================================================

def pydantic_to_json(obj: BaseModel) -> Dict[str, Any]:
    """Convert any Pydantic model to JSON-serializable dictionary."""
    from pydantic import BaseModel
    return obj.model_dump() if hasattr(obj, 'model_dump') else obj.dict()


def json_to_pydantic(data: Dict[str, Any], model_class):
    """Convert JSON dictionary to Pydantic model instance."""
    return model_class(**data)


def employees_to_json(employees: List[Employee]) -> str:
    """Convert list of Employee objects to JSON string."""
    return json.dumps([e.dict() for e in employees], ensure_ascii=False, indent=2)


def availability_to_json(availability: List[Availability]) -> str:
    """Convert list of Availability objects to JSON string."""
    return json.dumps([a.dict() for a in availability], ensure_ascii=False, indent=2)


def constraints_to_json(constraints: Constraints) -> str:
    """Convert Constraints object to JSON string."""
    return json.dumps(constraints.dict(), ensure_ascii=False, indent=2)


def schedule_to_json(schedule: Schedule) -> str:
    """Convert Schedule object to JSON string."""
    return json.dumps(schedule.dict(), ensure_ascii=False, indent=2)


def json_to_schedule(schedule_json: str) -> Schedule:
    """Convert JSON string to Schedule object."""
    data = json.loads(schedule_json) if isinstance(schedule_json, str) else schedule_json
    return Schedule(**data)


def json_to_violations(violations_json: str) -> List[Violation]:
    """Convert JSON string to list of Violation objects."""
    data = json.loads(violations_json) if isinstance(violations_json, str) else violations_json
    return [Violation(**v) for v in data]


def json_to_suggestions(suggestions_json: str) -> List[Suggestion]:
    """Convert JSON string to list of Suggestion objects."""
    data = json.loads(suggestions_json) if isinstance(suggestions_json, str) else suggestions_json
    return [Suggestion(**s) for s in data]


# ============================================================================
# Main API Functions
# ============================================================================

def generate_schedule(
    employees: List[Employee],
    availability: List[Availability],
    constraints: Constraints,
    week_start: str,
    days_count: int = 7
) -> Dict[str, Any]:
    """
    Generate a new schedule using DSPy.
    
    Args:
        employees: List of Employee objects
        availability: List of Availability objects
        constraints: Constraints object
        week_start: Week start date (YYYY-MM-DD)
        days_count: Number of days to schedule
    
    Returns:
        Dict with:
            - schedule: Schedule object
            - schedule_json: Raw JSON string
            - reasoning: Explanation of scheduling decisions
    """
    _ensure_modules()
    
    # Convert to JSON
    employees_json = employees_to_json(employees)
    availability_json = availability_to_json(availability)
    constraints_json = constraints_to_json(constraints)
    
    # Generate schedule
    result = _planner(
        employees=employees_json,
        availability=availability_json,
        constraints=constraints_json,
        week_start=week_start,
        days_count=days_count
    )
    
    # Parse result
    try:
        schedule_data = json.loads(result.schedule_json)
        
        # Ensure it's in the right format
        if isinstance(schedule_data, list):
            # Convert to Schedule object
            schedule = Schedule(
                week_start=week_start,
                week_end=(datetime.strptime(week_start, "%Y-%m-%d") + timedelta(days=days_count-1)).strftime("%Y-%m-%d"),
                assignments=[ShiftAssignment(**a) for a in schedule_data]
            )
        else:
            schedule = Schedule(**schedule_data)
    except Exception as e:
        print(f"Warning: Failed to parse schedule JSON: {e}")
        # Return empty schedule
        schedule = Schedule(week_start=week_start, assignments=[])
    
    return {
        "schedule": schedule,
        "schedule_json": result.schedule_json,
        "reasoning": result.reasoning
    }


def analyze_schedule(
    employees: List[Employee],
    availability: List[Availability],
    constraints: Constraints,
    schedule: Schedule
) -> Dict[str, Any]:
    """
    Analyze a schedule for violations.
    
    Args:
        employees: List of Employee objects
        availability: List of Availability objects
        constraints: Constraints object
        schedule: Schedule object to analyze
    
    Returns:
        Dict with:
            - violations: List of Violation objects
            - analysis: Natural language analysis
            - quality_score: Score 0-100
    """
    _ensure_modules()
    
    # Convert to JSON
    employees_json = employees_to_json(employees)
    availability_json = availability_to_json(availability)
    constraints_json = constraints_to_json(constraints)
    schedule_json = schedule_to_json(schedule)
    
    # Analyze
    result = _analyzer(
        employees=employees_json,
        availability=availability_json,
        constraints=constraints_json,
        schedule_json=schedule_json
    )
    
    # Parse violations
    try:
        violations = json_to_violations(result.violations_json)
    except Exception as e:
        print(f"Warning: Failed to parse violations: {e}")
        violations = []
    
    # Parse quality score
    try:
        quality_score = float(result.quality_score)
    except:
        quality_score = 0.0
    
    return {
        "violations": violations,
        "violations_json": result.violations_json,
        "analysis": result.analysis,
        "quality_score": quality_score
    }


def fix_schedule(
    employees: List[Employee],
    availability: List[Availability],
    constraints: Constraints,
    schedule: Schedule,
    violations: List[Violation]
) -> Dict[str, Any]:
    """
    Fix violations in a schedule.
    
    Args:
        employees: List of Employee objects
        availability: List of Availability objects
        constraints: Constraints object
        schedule: Schedule object with violations
        violations: List of Violation objects
    
    Returns:
        Dict with:
            - suggestions: List of Suggestion objects
            - fixed_schedule: Improved Schedule object
            - improvement_explanation: Explanation of fixes
    """
    _ensure_modules()
    
    # Convert to JSON
    employees_json = employees_to_json(employees)
    availability_json = availability_to_json(availability)
    constraints_json = constraints_to_json(constraints)
    schedule_json = schedule_to_json(schedule)
    violations_json = json.dumps([v.dict() for v in violations], ensure_ascii=False)
    
    # Fix
    result = _fixer(
        employees=employees_json,
        availability=availability_json,
        constraints=constraints_json,
        schedule_json=schedule_json,
        violations_json=violations_json
    )
    
    # Parse results
    try:
        suggestions = json_to_suggestions(result.suggestions_json)
    except Exception as e:
        print(f"Warning: Failed to parse suggestions: {e}")
        suggestions = []
    
    try:
        fixed_schedule = json_to_schedule(result.fixed_schedule_json)
    except Exception as e:
        print(f"Warning: Failed to parse fixed schedule: {e}")
        fixed_schedule = schedule  # Return original if parsing fails
    
    return {
        "suggestions": suggestions,
        "suggestions_json": result.suggestions_json,
        "fixed_schedule": fixed_schedule,
        "fixed_schedule_json": result.fixed_schedule_json,
        "improvement_explanation": result.improvement_explanation
    }


def optimize_schedule(
    employees: List[Employee],
    constraints: Constraints,
    schedule: Schedule,
    optimization_goals: str = "balance workload, maximize preference satisfaction, fair distribution"
) -> Dict[str, Any]:
    """
    Optimize a schedule for soft constraints.
    
    Args:
        employees: List of Employee objects
        constraints: Constraints object
        schedule: Schedule object to optimize
        optimization_goals: Optimization goals as string
    
    Returns:
        Dict with:
            - optimized_schedule: Optimized Schedule object
            - improvements: List of improvements made
            - optimization_explanation: Explanation of changes
    """
    _ensure_modules()
    
    # Convert to JSON
    employees_json = employees_to_json(employees)
    constraints_json = constraints_to_json(constraints)
    schedule_json = schedule_to_json(schedule)
    
    # Optimize
    result = _optimizer(
        employees=employees_json,
        constraints=constraints_json,
        schedule_json=schedule_json,
        optimization_goals=optimization_goals
    )
    
    # Parse results
    try:
        optimized_schedule = json_to_schedule(result.optimized_schedule_json)
    except Exception as e:
        print(f"Warning: Failed to parse optimized schedule: {e}")
        optimized_schedule = schedule
    
    try:
        improvements = json.loads(result.improvements_json)
    except Exception as e:
        print(f"Warning: Failed to parse improvements: {e}")
        improvements = []
    
    return {
        "optimized_schedule": optimized_schedule,
        "optimized_schedule_json": result.optimized_schedule_json,
        "improvements": improvements,
        "improvements_json": result.improvements_json,
        "optimization_explanation": result.optimization_explanation
    }


def comprehensive_schedule_pipeline(
    employees: List[Employee],
    availability: List[Availability],
    constraints: Constraints,
    week_start: str,
    days_count: int = 7,
    auto_fix: bool = True,
    auto_optimize: bool = True
) -> Dict[str, Any]:
    """
    Complete scheduling pipeline: Generate → Analyze → Fix → Optimize
    
    Args:
        employees: List of Employee objects
        availability: List of Availability objects
        constraints: Constraints object
        week_start: Week start date (YYYY-MM-DD)
        days_count: Number of days to schedule
        auto_fix: Automatically fix violations
        auto_optimize: Automatically optimize for soft constraints
    
    Returns:
        Dict with all pipeline outputs including:
            - initial_schedule
            - violations
            - suggestions
            - fixed_schedule
            - final_schedule
            - quality_score
            - analysis
            - etc.
    """
    _ensure_modules()
    
    # Convert to JSON
    employees_json = employees_to_json(employees)
    availability_json = availability_to_json(availability)
    constraints_json = constraints_to_json(constraints)
    
    # Run comprehensive pipeline
    result = _comprehensive(
        employees=employees_json,
        availability=availability_json,
        constraints=constraints_json,
        week_start=week_start,
        days_count=days_count,
        auto_fix=auto_fix,
        auto_optimize=auto_optimize
    )
    
    # Parse all outputs
    parsed_result = {}
    
    # Parse schedules
    for key in ['initial_schedule', 'fixed_schedule', 'final_schedule']:
        if key in result:
            try:
                parsed_result[key] = json_to_schedule(result[key])
                parsed_result[f"{key}_json"] = result[key]
            except Exception as e:
                print(f"Warning: Failed to parse {key}: {e}")
    
    # Parse violations
    if 'violations' in result:
        try:
            parsed_result['violations'] = json_to_violations(result['violations'])
            parsed_result['violations_json'] = result['violations']
        except Exception as e:
            print(f"Warning: Failed to parse violations: {e}")
            parsed_result['violations'] = []
    
    # Parse suggestions
    if 'suggestions' in result:
        try:
            parsed_result['suggestions'] = json_to_suggestions(result['suggestions'])
            parsed_result['suggestions_json'] = result['suggestions']
        except Exception as e:
            print(f"Warning: Failed to parse suggestions: {e}")
            parsed_result['suggestions'] = []
    
    # Parse improvements
    if 'improvements' in result:
        try:
            parsed_result['improvements'] = json.loads(result['improvements'])
            parsed_result['improvements_json'] = result['improvements']
        except Exception as e:
            print(f"Warning: Failed to parse improvements: {e}")
            parsed_result['improvements'] = []
    
    # Copy other fields
    for key in ['initial_reasoning', 'analysis', 'quality_score', 'improvement_explanation', 'optimization_explanation']:
        if key in result:
            parsed_result[key] = result[key]
    
    return parsed_result


# ============================================================================
# Convenience Functions
# ============================================================================

def create_schedule_from_request(request: ScheduleRequest) -> ScheduleResponse:
    """
    Create a schedule from a ScheduleRequest object.
    
    Args:
        request: ScheduleRequest with all parameters
    
    Returns:
        ScheduleResponse with schedule and analysis
    """
    try:
        # Generate schedule
        gen_result = generate_schedule(
            employees=request.employees,
            availability=request.availability,
            constraints=request.constraints,
            week_start=request.week_start,
            days_count=request.days_count
        )
        
        # Analyze it
        analysis_result = analyze_schedule(
            employees=request.employees,
            availability=request.availability,
            constraints=request.constraints,
            schedule=gen_result['schedule']
        )
        
        return ScheduleResponse(
            schedule=gen_result['schedule'],
            violations=analysis_result['violations'],
            suggestions=[],
            success=True,
            message=f"Schedule generated successfully. Quality score: {analysis_result['quality_score']:.1f}/100",
            metadata={
                "reasoning": gen_result['reasoning'],
                "analysis": analysis_result['analysis'],
                "quality_score": analysis_result['quality_score']
            }
        )
    
    except Exception as e:
        import traceback
        return ScheduleResponse(
            schedule=Schedule(week_start=request.week_start, assignments=[]),
            violations=[],
            suggestions=[],
            success=False,
            message=f"Failed to generate schedule: {str(e)}",
            metadata={"error": traceback.format_exc()}
        )


if __name__ == "__main__":
    print("="*70)
    print(" Backend Functions Test")
    print("="*70)
    
    from models import create_example_employee, create_example_constraints
    
    # Create test data
    employees = [create_example_employee()]
    availability = [
        Availability(
            employee_id="emp_001",
            day="Mon",
            date="2025-12-15",
            available_shifts=["day", "morning"]
        )
    ]
    constraints = create_example_constraints()
    
    print("\n✓ Test data created")
    print(f"  Employees: {len(employees)}")
    print(f"  Availability: {len(availability)}")
    
    # Test generate_schedule
    print("\nTesting generate_schedule...")
    try:
        result = generate_schedule(
            employees=employees,
            availability=availability,
            constraints=constraints,
            week_start="2025-12-15",
            days_count=7
        )
        print(f"✓ Schedule generated with {len(result['schedule'].assignments)} assignments")
        print(f"  Reasoning: {result['reasoning'][:100]}...")
    except Exception as e:
        print(f"✗ Failed: {e}")
    
    print("\n" + "="*70)
    print(" ✅ Backend tests completed!")
    print("="*70)
