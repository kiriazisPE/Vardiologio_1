# -*- coding: utf-8 -*-
"""
DSPy Scheduler - Core Scheduling Logic using DSPy Signatures
Implements the main scheduling pipeline with strict I/O schemas.
"""

import dspy
import json
from typing import List, Dict, Any, Optional
from datetime import date, timedelta

from models import (
    Employee, Availability, Constraints, Schedule, ShiftAssignment,
    Violation, Suggestion, ScheduleAnalysis, Weekday, ShiftType
)
from dspy_config import configure_dspy, is_configured


# ============================================================================
# DSPy Signatures - Define strict I/O schemas
# ============================================================================

class GenerateSchedule(dspy.Signature):
    """
    Given employees, availability and constraints,
    produce a feasible weekly schedule as structured JSON.
    
    The schedule must:
      - Respect employee availability
      - Respect max weekly hours and rest constraints
      - Respect min/max staff per shift
      - Minimize violations of soft rules
      - Assign appropriate roles to employees
    """
    
    employees = dspy.InputField(
        desc="List of employees with roles, hour limits, and preferences in JSON format"
    )
    availability = dspy.InputField(
        desc="List of employee availabilities per day/shift in JSON format"
    )
    constraints = dspy.InputField(
        desc="Global scheduling constraints and rules (hard & soft) in JSON format"
    )
    week_start = dspy.InputField(
        desc="ISO date for Monday of the week (YYYY-MM-DD)"
    )
    days_count = dspy.InputField(
        desc="Number of days to schedule (typically 7 for a week)"
    )
    
    # Output
    schedule_json = dspy.OutputField(
        desc="JSON with list of shift assignments: [{day, date, shift, employee_id, role, hours}]"
    )
    reasoning = dspy.OutputField(
        desc="Brief explanation of the scheduling decisions made"
    )


class AnalyzeSchedule(dspy.Signature):
    """
    Analyze a schedule for constraint violations and suggest improvements.
    
    Checks for:
      - Overtime violations (exceeding max hours)
      - Insufficient rest between shifts
      - Understaffing or overstaffing
      - Role mismatches
      - Consecutive day limits
      - Availability violations
    """
    
    employees = dspy.InputField(desc="List of employees in JSON format")
    availability = dspy.InputField(desc="Employee availabilities in JSON format")
    constraints = dspy.InputField(desc="Scheduling constraints in JSON format")
    schedule_json = dspy.InputField(desc="Current schedule in JSON format")
    
    # Outputs
    violations_json = dspy.OutputField(
        desc="JSON list of violations: [{type, severity, employee_id, description, current_value, max_allowed}]"
    )
    analysis = dspy.OutputField(
        desc="Natural language explanation of violations and overall schedule quality"
    )
    quality_score = dspy.OutputField(
        desc="Overall schedule quality score from 0-100"
    )


class FixSchedule(dspy.Signature):
    """
    Given a schedule with violations, suggest specific fixes and produce an improved schedule.
    
    Fix strategies:
      - Swap shifts between employees
      - Reassign shifts to different employees
      - Remove problematic shifts
      - Adjust shift hours
    """
    
    employees = dspy.InputField(desc="List of employees in JSON format")
    availability = dspy.InputField(desc="Employee availabilities in JSON format")
    constraints = dspy.InputField(desc="Scheduling constraints in JSON format")
    schedule_json = dspy.InputField(desc="Current schedule with violations in JSON format")
    violations_json = dspy.InputField(desc="List of detected violations in JSON format")
    
    # Outputs
    suggestions_json = dspy.OutputField(
        desc="JSON list of suggestions: [{type, priority, employee_id, description, expected_benefit, impact_score}]"
    )
    fixed_schedule_json = dspy.OutputField(
        desc="Improved schedule JSON with fewer or no violations"
    )
    improvement_explanation = dspy.OutputField(
        desc="Explanation of what was fixed and why"
    )


class OptimizeSchedule(dspy.Signature):
    """
    Optimize a valid schedule to improve soft constraints like fairness, preferences, and workload balance.
    """
    
    employees = dspy.InputField(desc="List of employees in JSON format")
    constraints = dspy.InputField(desc="Scheduling constraints including soft rules in JSON format")
    schedule_json = dspy.InputField(desc="Current valid schedule in JSON format")
    optimization_goals = dspy.InputField(
        desc="Specific optimization goals (e.g., 'balance workload', 'maximize preference satisfaction')"
    )
    
    # Outputs
    optimized_schedule_json = dspy.OutputField(
        desc="Optimized schedule JSON with improved soft constraint satisfaction"
    )
    improvements_json = dspy.OutputField(
        desc="JSON list of improvements made: [{metric, before, after, benefit}]"
    )
    optimization_explanation = dspy.OutputField(
        desc="Explanation of optimization changes"
    )


# ============================================================================
# DSPy Modules - Wrap signatures with reasoning chains
# ============================================================================

class SchedulePlanner(dspy.Module):
    """
    Main module for generating schedules.
    Uses Chain of Thought for robust reasoning.
    """
    
    def __init__(self):
        super().__init__()
        self.generator = dspy.ChainOfThought(GenerateSchedule)
    
    def forward(
        self,
        employees: str,
        availability: str,
        constraints: str,
        week_start: str,
        days_count: int = 7
    ) -> dspy.Prediction:
        """
        Generate a schedule.
        
        Args:
            employees: JSON string of employee list
            availability: JSON string of availability list
            constraints: JSON string of constraints
            week_start: ISO date string (YYYY-MM-DD)
            days_count: Number of days to schedule
        
        Returns:
            Prediction with schedule_json and reasoning
        """
        return self.generator(
            employees=employees,
            availability=availability,
            constraints=constraints,
            week_start=week_start,
            days_count=str(days_count)
        )


class ScheduleAnalyzer(dspy.Module):
    """
    Module for analyzing schedules and detecting violations.
    """
    
    def __init__(self):
        super().__init__()
        self.analyzer = dspy.ChainOfThought(AnalyzeSchedule)
    
    def forward(
        self,
        employees: str,
        availability: str,
        constraints: str,
        schedule_json: str
    ) -> dspy.Prediction:
        """
        Analyze a schedule for violations.
        
        Args:
            employees: JSON string of employee list
            availability: JSON string of availability list
            constraints: JSON string of constraints
            schedule_json: JSON string of schedule
        
        Returns:
            Prediction with violations_json, analysis, and quality_score
        """
        return self.analyzer(
            employees=employees,
            availability=availability,
            constraints=constraints,
            schedule_json=schedule_json
        )


class ScheduleFixer(dspy.Module):
    """
    Module for fixing schedule violations.
    """
    
    def __init__(self):
        super().__init__()
        self.fixer = dspy.ChainOfThought(FixSchedule)
    
    def forward(
        self,
        employees: str,
        availability: str,
        constraints: str,
        schedule_json: str,
        violations_json: str
    ) -> dspy.Prediction:
        """
        Fix violations in a schedule.
        
        Args:
            employees: JSON string of employee list
            availability: JSON string of availability list
            constraints: JSON string of constraints
            schedule_json: JSON string of schedule
            violations_json: JSON string of violations
        
        Returns:
            Prediction with suggestions_json, fixed_schedule_json, improvement_explanation
        """
        return self.fixer(
            employees=employees,
            availability=availability,
            constraints=constraints,
            schedule_json=schedule_json,
            violations_json=violations_json
        )


class ScheduleOptimizer(dspy.Module):
    """
    Module for optimizing schedules for soft constraints.
    """
    
    def __init__(self):
        super().__init__()
        self.optimizer = dspy.ChainOfThought(OptimizeSchedule)
    
    def forward(
        self,
        employees: str,
        constraints: str,
        schedule_json: str,
        optimization_goals: str = "balance workload, maximize preference satisfaction, fair weekend distribution"
    ) -> dspy.Prediction:
        """
        Optimize a schedule.
        
        Args:
            employees: JSON string of employee list
            constraints: JSON string of constraints
            schedule_json: JSON string of schedule
            optimization_goals: Optimization goals as string
        
        Returns:
            Prediction with optimized_schedule_json, improvements_json, optimization_explanation
        """
        return self.optimizer(
            employees=employees,
            constraints=constraints,
            schedule_json=schedule_json,
            optimization_goals=optimization_goals
        )


# ============================================================================
# Convenience Classes - Complete Pipeline
# ============================================================================

class ComprehensiveScheduler(dspy.Module):
    """
    Complete scheduling pipeline: Generate → Analyze → Fix → Optimize
    """
    
    def __init__(self):
        super().__init__()
        self.planner = SchedulePlanner()
        self.analyzer = ScheduleAnalyzer()
        self.fixer = ScheduleFixer()
        self.optimizer = ScheduleOptimizer()
    
    def forward(
        self,
        employees: str,
        availability: str,
        constraints: str,
        week_start: str,
        days_count: int = 7,
        auto_fix: bool = True,
        auto_optimize: bool = True
    ) -> Dict[str, Any]:
        """
        Complete scheduling pipeline.
        
        Args:
            employees: JSON string of employee list
            availability: JSON string of availability list
            constraints: JSON string of constraints
            week_start: ISO date string
            days_count: Number of days to schedule
            auto_fix: Automatically fix violations
            auto_optimize: Automatically optimize for soft constraints
        
        Returns:
            Dict with all outputs (schedule, violations, suggestions, etc.)
        """
        # Step 1: Generate initial schedule
        gen_result = self.planner(
            employees=employees,
            availability=availability,
            constraints=constraints,
            week_start=week_start,
            days_count=days_count
        )
        
        current_schedule = gen_result.schedule_json
        
        # Step 2: Analyze for violations
        analysis_result = self.analyzer(
            employees=employees,
            availability=availability,
            constraints=constraints,
            schedule_json=current_schedule
        )
        
        violations = analysis_result.violations_json
        quality_score = analysis_result.quality_score
        
        # Step 3: Fix violations if requested and violations exist
        fixed_schedule = current_schedule
        suggestions = "[]"
        improvement_explanation = "No fixes needed"
        
        if auto_fix:
            try:
                violations_list = json.loads(violations)
                if violations_list:  # Has violations
                    fix_result = self.fixer(
                        employees=employees,
                        availability=availability,
                        constraints=constraints,
                        schedule_json=current_schedule,
                        violations_json=violations
                    )
                    fixed_schedule = fix_result.fixed_schedule_json
                    suggestions = fix_result.suggestions_json
                    improvement_explanation = fix_result.improvement_explanation
            except Exception as e:
                print(f"Warning: Fix step failed: {e}")
        
        # Step 4: Optimize if requested
        final_schedule = fixed_schedule
        improvements = "[]"
        optimization_explanation = "No optimization performed"
        
        if auto_optimize:
            try:
                opt_result = self.optimizer(
                    employees=employees,
                    constraints=constraints,
                    schedule_json=fixed_schedule,
                    optimization_goals="balance workload, maximize preference satisfaction, fair distribution"
                )
                final_schedule = opt_result.optimized_schedule_json
                improvements = opt_result.improvements_json
                optimization_explanation = opt_result.optimization_explanation
            except Exception as e:
                print(f"Warning: Optimize step failed: {e}")
        
        return {
            "initial_schedule": current_schedule,
            "initial_reasoning": gen_result.reasoning,
            "violations": violations,
            "analysis": analysis_result.analysis,
            "quality_score": quality_score,
            "suggestions": suggestions,
            "fixed_schedule": fixed_schedule,
            "improvement_explanation": improvement_explanation,
            "final_schedule": final_schedule,
            "improvements": improvements,
            "optimization_explanation": optimization_explanation
        }


# ============================================================================
# Module Initialization
# ============================================================================

# Ensure DSPy is configured
if not is_configured():
    print("⚠️  DSPy not configured! Call configure_dspy() before using scheduler modules.")


if __name__ == "__main__":
    print("="*70)
    print(" DSPy Scheduler Module Test")
    print("="*70)
    
    # Ensure configuration
    if not is_configured():
        print("\n⚠️  Configuring DSPy...")
        configure_dspy()
    
    if not is_configured():
        print("❌ Failed to configure DSPy. Cannot run tests.")
        exit(1)
    
    print("\n✅ DSPy configured successfully!")
    
    # Test module instantiation
    print("\nTesting module instantiation...")
    
    try:
        planner = SchedulePlanner()
        print("✓ SchedulePlanner created")
        
        analyzer = ScheduleAnalyzer()
        print("✓ ScheduleAnalyzer created")
        
        fixer = ScheduleFixer()
        print("✓ ScheduleFixer created")
        
        optimizer = ScheduleOptimizer()
        print("✓ ScheduleOptimizer created")
        
        comprehensive = ComprehensiveScheduler()
        print("✓ ComprehensiveScheduler created")
        
        print("\n✅ All modules instantiated successfully!")
        
    except Exception as e:
        print(f"\n❌ Module instantiation failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*70)
    print(" ✅ Tests completed!")
    print("="*70)
