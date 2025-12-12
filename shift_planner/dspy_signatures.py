# -*- coding: utf-8 -*-
"""
DSPy Signatures for Shift Scheduling
Provides structured input/output schemas for predictable AI responses.
"""

import dspy
from typing import List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# Pydantic Models for Structured Output
# ============================================================================

class ShiftPerDay(BaseModel):
    """Represents shifts required for a specific day."""
    date: str = Field(description="Date in YYYY-MM-DD format")
    day_name: str = Field(description="Day of the week (e.g., Monday)")
    shifts: List[dict] = Field(
        description="List of shifts with details: {shift_type, start_hour, required_count, role}"
    )
    total_staff_needed: int = Field(description="Total number of staff needed for the day")
    is_weekend: bool = Field(description="Whether this is a weekend day")
    special_notes: Optional[str] = Field(default=None, description="Any special requirements or notes")


class EmployeeAvailability(BaseModel):
    """Represents employee availability and constraints."""
    name: str = Field(description="Employee name")
    available_dates: List[str] = Field(description="List of dates the employee is available (YYYY-MM-DD)")
    roles: List[str] = Field(description="Roles the employee can fulfill")
    preferred_shifts: List[str] = Field(default_factory=list, description="Preferred shift types")
    max_weekly_hours: float = Field(description="Maximum hours the employee can work per week")
    current_weekly_hours: float = Field(default=0.0, description="Hours already scheduled this week")
    unavailable_dates: List[str] = Field(default_factory=list, description="Dates when unavailable")
    constraints: Optional[str] = Field(default=None, description="Any special constraints or notes")


class Violation(BaseModel):
    """Represents a scheduling rule violation."""
    violation_type: str = Field(description="Type of violation (e.g., 'MAX_HOURS_EXCEEDED', 'INSUFFICIENT_REST')")
    severity: str = Field(description="Severity level: CRITICAL, HIGH, MEDIUM, LOW")
    employee: Optional[str] = Field(default=None, description="Employee affected by the violation")
    date: Optional[str] = Field(default=None, description="Date of the violation (YYYY-MM-DD)")
    shift: Optional[str] = Field(default=None, description="Shift type involved")
    description: str = Field(description="Human-readable description of the violation")
    rule_violated: str = Field(description="The specific rule that was violated")
    current_value: Optional[float] = Field(default=None, description="Current value (e.g., 45 hours)")
    max_allowed: Optional[float] = Field(default=None, description="Maximum allowed value (e.g., 40 hours)")


class Suggestion(BaseModel):
    """Represents an optimization suggestion for the schedule."""
    suggestion_type: str = Field(
        description="Type of suggestion: SWAP, REASSIGN, ADD_EMPLOYEE, REMOVE_SHIFT, ADJUST_HOURS"
    )
    priority: str = Field(description="Priority level: HIGH, MEDIUM, LOW")
    employee: Optional[str] = Field(default=None, description="Primary employee involved")
    employee2: Optional[str] = Field(default=None, description="Second employee (for swaps)")
    date: Optional[str] = Field(default=None, description="Date affected (YYYY-MM-DD)")
    shift: Optional[str] = Field(default=None, description="Shift type affected")
    role: Optional[str] = Field(default=None, description="Role involved")
    description: str = Field(description="Human-readable description of the suggestion")
    expected_benefit: str = Field(description="Expected benefit from implementing this suggestion")
    impact_score: Optional[float] = Field(default=None, description="Estimated impact score (0-100)")


# ============================================================================
# DSPy Signatures
# ============================================================================

class ShiftsPerDaySignature(dspy.Signature):
    """
    Analyzes scheduling requirements and returns structured shifts per day.
    
    Input: Business context, date range, roles, and staffing rules.
    Output: Structured list of required shifts per day.
    """
    
    # Input fields
    business_model: str = dspy.InputField(desc="Work model (e.g., 5ήμερο, 6ήμερο)")
    start_date: str = dspy.InputField(desc="Start date (YYYY-MM-DD)")
    days_count: int = dspy.InputField(desc="Number of days to schedule")
    active_shifts: str = dspy.InputField(desc="Comma-separated list of active shift types")
    roles: str = dspy.InputField(desc="Comma-separated list of roles")
    role_requirements: str = dspy.InputField(desc="JSON string of role requirements per shift")
    special_requirements: str = dspy.InputField(desc="Any special requirements or constraints")
    
    # Output field
    shifts_per_day: str = dspy.OutputField(
        desc="JSON array of ShiftPerDay objects with date, shifts, and requirements"
    )


class EmployeeAvailabilitySignature(dspy.Signature):
    """
    Analyzes employee data and returns structured availability information.
    
    Input: Employee list with their constraints, preferences, and current workload.
    Output: Structured employee availability data with constraints.
    """
    
    # Input fields
    employees_data: str = dspy.InputField(desc="JSON string of employee data with roles and preferences")
    schedule_start: str = dspy.InputField(desc="Schedule start date (YYYY-MM-DD)")
    schedule_days: int = dspy.InputField(desc="Number of days in schedule")
    current_schedule: str = dspy.InputField(desc="JSON string of current schedule assignments")
    work_rules: str = dspy.InputField(desc="JSON string of work rules (max hours, rest periods, etc.)")
    
    # Output field
    employee_availability: str = dspy.OutputField(
        desc="JSON array of EmployeeAvailability objects with availability and constraints"
    )


class ViolationsSignature(dspy.Signature):
    """
    Analyzes a schedule and identifies all rule violations.
    
    Input: Current schedule, employees, rules, and constraints.
    Output: Structured list of violations with severity and details.
    """
    
    # Input fields
    schedule_data: str = dspy.InputField(desc="JSON string of current schedule assignments")
    employees: str = dspy.InputField(desc="JSON string of employee data")
    work_rules: str = dspy.InputField(desc="JSON string of work rules to check against")
    role_requirements: str = dspy.InputField(desc="JSON string of role-specific requirements")
    business_constraints: str = dspy.InputField(desc="Any business-specific constraints")
    
    # Output field
    violations: str = dspy.OutputField(
        desc="JSON array of Violation objects describing all rule violations found"
    )


class SuggestionsSignature(dspy.Signature):
    """
    Generates optimization suggestions to improve the schedule.
    
    Input: Current schedule, violations, employee data, and constraints.
    Output: Structured list of actionable suggestions with priorities.
    """
    
    # Input fields
    schedule_data: str = dspy.InputField(desc="JSON string of current schedule")
    violations: str = dspy.InputField(desc="JSON string of identified violations")
    employees: str = dspy.InputField(desc="JSON string of employee data with availability")
    roles: str = dspy.InputField(desc="Comma-separated list of roles")
    active_shifts: str = dspy.InputField(desc="Comma-separated list of active shifts")
    optimization_goals: str = dspy.InputField(
        desc="Optimization goals (e.g., 'minimize violations, balance workload, reduce costs')"
    )
    
    # Output field
    suggestions: str = dspy.OutputField(
        desc="JSON array of Suggestion objects with actionable improvements ranked by priority"
    )


class ScheduleOptimizationSignature(dspy.Signature):
    """
    Comprehensive schedule analysis combining all aspects.
    
    Input: Complete scheduling context including employees, rules, and current state.
    Output: Complete analysis with shifts, availability, violations, and suggestions.
    """
    
    # Input fields
    business_context: str = dspy.InputField(desc="JSON string of business settings and model")
    employees_data: str = dspy.InputField(desc="JSON string of all employee data")
    schedule_parameters: str = dspy.InputField(desc="JSON string of schedule parameters (dates, shifts, roles)")
    current_schedule: str = dspy.InputField(desc="JSON string of current schedule (if any)")
    work_rules: str = dspy.InputField(desc="JSON string of all work rules and constraints")
    
    # Output fields
    shifts_analysis: str = dspy.OutputField(desc="JSON array of ShiftPerDay objects")
    employee_availability: str = dspy.OutputField(desc="JSON array of EmployeeAvailability objects")
    violations: str = dspy.OutputField(desc="JSON array of Violation objects")
    suggestions: str = dspy.OutputField(desc="JSON array of Suggestion objects")
    overall_score: str = dspy.OutputField(desc="Overall schedule quality score (0-100) with explanation")


# ============================================================================
# DSPy Modules (Predictors)
# ============================================================================

class ShiftPlannerModule(dspy.Module):
    """Module for planning shifts per day."""
    
    def __init__(self):
        super().__init__()
        self.predict = dspy.ChainOfThought(ShiftsPerDaySignature)
    
    def forward(self, business_model, start_date, days_count, active_shifts, 
                roles, role_requirements, special_requirements=""):
        return self.predict(
            business_model=business_model,
            start_date=start_date,
            days_count=days_count,
            active_shifts=active_shifts,
            roles=roles,
            role_requirements=role_requirements,
            special_requirements=special_requirements
        )


class AvailabilityAnalyzerModule(dspy.Module):
    """Module for analyzing employee availability."""
    
    def __init__(self):
        super().__init__()
        self.predict = dspy.ChainOfThought(EmployeeAvailabilitySignature)
    
    def forward(self, employees_data, schedule_start, schedule_days, 
                current_schedule, work_rules):
        return self.predict(
            employees_data=employees_data,
            schedule_start=schedule_start,
            schedule_days=schedule_days,
            current_schedule=current_schedule,
            work_rules=work_rules
        )


class ViolationDetectorModule(dspy.Module):
    """Module for detecting schedule violations."""
    
    def __init__(self):
        super().__init__()
        self.predict = dspy.ChainOfThought(ViolationsSignature)
    
    def forward(self, schedule_data, employees, work_rules, 
                role_requirements, business_constraints=""):
        return self.predict(
            schedule_data=schedule_data,
            employees=employees,
            work_rules=work_rules,
            role_requirements=role_requirements,
            business_constraints=business_constraints
        )


class SuggestionGeneratorModule(dspy.Module):
    """Module for generating optimization suggestions."""
    
    def __init__(self):
        super().__init__()
        self.predict = dspy.ChainOfThought(SuggestionsSignature)
    
    def forward(self, schedule_data, violations, employees, roles, 
                active_shifts, optimization_goals):
        return self.predict(
            schedule_data=schedule_data,
            violations=violations,
            employees=employees,
            roles=roles,
            active_shifts=active_shifts,
            optimization_goals=optimization_goals
        )


class ComprehensiveSchedulerModule(dspy.Module):
    """Comprehensive module combining all scheduling aspects."""
    
    def __init__(self):
        super().__init__()
        self.predict = dspy.ChainOfThought(ScheduleOptimizationSignature)
    
    def forward(self, business_context, employees_data, schedule_parameters, 
                current_schedule, work_rules):
        return self.predict(
            business_context=business_context,
            employees_data=employees_data,
            schedule_parameters=schedule_parameters,
            current_schedule=current_schedule,
            work_rules=work_rules
        )


# ============================================================================
# Helper Functions
# ============================================================================

def initialize_dspy(model: str = "gpt-4o-mini", api_key: Optional[str] = None):
    """
    Initialize DSPy with OpenAI language model.
    
    Args:
        model: OpenAI model name (default: gpt-4o-mini)
        api_key: OpenAI API key (uses env var if not provided)
    """
    import os
    
    if api_key is None:
        api_key = os.getenv("OpenAI_API_KEY")
    
    if not api_key:
        raise ValueError("OpenAI API key not found. Set OpenAI_API_KEY environment variable.")
    
    # Configure DSPy with OpenAI (compatible with DSPy 3.0+)
    try:
        # DSPy 3.0+ uses dspy.LM
        lm = dspy.LM(
            model=f"openai/{model}",
            api_key=api_key,
            max_tokens=2000,
            temperature=0.2
        )
    except (AttributeError, TypeError):
        # Fallback for older DSPy versions
        lm = dspy.OpenAI(model=model, api_key=api_key, max_tokens=2000)
    
    dspy.settings.configure(lm=lm)
    
    return lm


# ============================================================================
# Usage Examples
# ============================================================================

if __name__ == "__main__":
    import json
    import os
    
    # Initialize DSPy
    try:
        initialize_dspy()
        print("✓ DSPy initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize DSPy: {e}")
        exit(1)
    
    # Example 1: Shift Planning
    print("\n" + "="*60)
    print("Example 1: Planning Shifts Per Day")
    print("="*60)
    
    shift_planner = ShiftPlannerModule()
    
    result = shift_planner.forward(
        business_model="5ήμερο",
        start_date="2025-12-15",
        days_count=7,
        active_shifts="day,night",
        roles="Manager,Barista,Cashier",
        role_requirements=json.dumps({
            "Manager": {"day": 1, "night": 1},
            "Barista": {"day": 2, "night": 1},
            "Cashier": {"day": 1, "night": 1}
        }),
        special_requirements="Weekend shifts need extra coverage"
    )
    
    print("Shifts per day:")
    print(result.shifts_per_day)
    
    # Example 2: Violation Detection
    print("\n" + "="*60)
    print("Example 2: Detecting Violations")
    print("="*60)
    
    violation_detector = ViolationDetectorModule()
    
    sample_schedule = [
        {"employee": "John Doe", "date": "2025-12-15", "shift": "day", "role": "Manager", "hours": 8},
        {"employee": "John Doe", "date": "2025-12-16", "shift": "night", "role": "Manager", "hours": 8},
        {"employee": "John Doe", "date": "2025-12-17", "shift": "day", "role": "Manager", "hours": 8},
        {"employee": "Jane Smith", "date": "2025-12-15", "shift": "day", "role": "Barista", "hours": 10},
    ]
    
    result = violation_detector.forward(
        schedule_data=json.dumps(sample_schedule),
        employees=json.dumps([
            {"name": "John Doe", "roles": ["Manager"], "max_weekly_hours": 40},
            {"name": "Jane Smith", "roles": ["Barista"], "max_weekly_hours": 40}
        ]),
        work_rules=json.dumps({
            "max_daily_hours": 8,
            "max_weekly_hours": 40,
            "min_rest_hours": 11
        }),
        role_requirements=json.dumps({"Manager": {"min_experience": 12}}),
        business_constraints="No employee should work day followed by night shift"
    )
    
    print("Violations detected:")
    print(result.violations)
    
    # Example 3: Generating Suggestions
    print("\n" + "="*60)
    print("Example 3: Optimization Suggestions")
    print("="*60)
    
    suggestion_generator = SuggestionGeneratorModule()
    
    result = suggestion_generator.forward(
        schedule_data=json.dumps(sample_schedule),
        violations=json.dumps([
            {
                "type": "INSUFFICIENT_REST",
                "employee": "John Doe",
                "severity": "HIGH",
                "description": "Only 4 hours rest between day and night shift"
            }
        ]),
        employees=json.dumps([
            {"name": "John Doe", "roles": ["Manager"], "available": True},
            {"name": "Jane Smith", "roles": ["Manager", "Barista"], "available": True}
        ]),
        roles="Manager,Barista,Cashier",
        active_shifts="day,night",
        optimization_goals="Fix violations, balance workload, ensure fairness"
    )
    
    print("Suggestions:")
    print(result.suggestions)
    
    print("\n✓ All examples completed successfully!")
