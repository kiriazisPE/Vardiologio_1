# -*- coding: utf-8 -*-
"""
Pydantic Data Models for Shift Scheduling
Provides type-safe, validated data structures for the entire scheduling system.
"""

from typing import List, Dict, Literal, Optional
from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime


# Type aliases for clarity
Weekday = Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
ShiftType = Literal["morning", "afternoon", "evening", "day", "night"]
Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
Role = str  # e.g., "Manager", "Barista", "Cashier"


class Employee(BaseModel):
    """
    Represents an employee with their constraints and preferences.
    """
    id: str = Field(description="Unique employee identifier")
    name: str = Field(description="Employee full name")
    role: Role = Field(description="Primary role (Manager, Barista, etc.)")
    roles: List[Role] = Field(default_factory=list, description="All roles employee can perform")
    max_hours_per_week: int = Field(default=40, description="Maximum weekly hours allowed")
    max_hours_per_day: int = Field(default=8, description="Maximum daily hours allowed")
    min_rest_hours: int = Field(default=11, description="Minimum rest hours between shifts")
    max_consecutive_days: int = Field(default=6, description="Maximum consecutive working days")
    preferred_shifts: Optional[List[ShiftType]] = Field(default=None, description="Preferred shift types")
    seniority: Optional[str] = Field(default=None, description="Seniority level (senior, mid, junior)")
    
    @field_validator('roles')
    @classmethod
    def ensure_role_in_roles(cls, v, info):
        """Ensure primary role is in roles list."""
        if info.data.get('role') and info.data['role'] not in v:
            v.append(info.data['role'])
        return v


class Availability(BaseModel):
    """
    Represents when an employee is available to work.
    """
    employee_id: str = Field(description="Employee ID")
    day: Weekday = Field(description="Day of the week")
    date: Optional[str] = Field(default=None, description="Specific date (YYYY-MM-DD)")
    available_shifts: List[ShiftType] = Field(description="Shifts employee is available for")
    unavailable: bool = Field(default=False, description="If True, employee is unavailable this day")
    note: Optional[str] = Field(default=None, description="Additional notes (vacation, sick, etc.)")


class ShiftAssignment(BaseModel):
    """
    Represents a specific shift assignment for an employee.
    """
    day: Weekday = Field(description="Day of the week")
    date: str = Field(description="Specific date (YYYY-MM-DD)")
    shift: ShiftType = Field(description="Shift type")
    employee_id: str = Field(description="Employee ID")
    employee_name: Optional[str] = Field(default=None, description="Employee name for display")
    role: Role = Field(description="Role for this shift")
    hours: float = Field(default=8.0, description="Number of hours for this shift")
    
    @field_validator('date')
    @classmethod
    def validate_date_format(cls, v):
        """Ensure date is in YYYY-MM-DD format."""
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Date must be in YYYY-MM-DD format, got: {v}")
        return v


class Schedule(BaseModel):
    """
    Represents a complete schedule for a week or period.
    """
    week_start: str = Field(description="ISO date for Monday of the week (YYYY-MM-DD)")
    week_end: Optional[str] = Field(default=None, description="ISO date for end of period")
    assignments: List[ShiftAssignment] = Field(description="All shift assignments")
    metadata: Optional[Dict] = Field(default_factory=dict, description="Additional metadata")
    
    @field_validator('week_start')
    @classmethod
    def validate_week_start(cls, v):
        """Ensure week_start is a valid date."""
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"week_start must be in YYYY-MM-DD format, got: {v}")
        return v


class Constraints(BaseModel):
    """
    Global scheduling constraints and rules.
    """
    min_staff_per_shift: Dict[ShiftType, int] = Field(
        description="Minimum staff required per shift type"
    )
    max_staff_per_shift: Dict[ShiftType, int] = Field(
        description="Maximum staff allowed per shift type"
    )
    min_staff_per_role: Optional[Dict[Role, Dict[ShiftType, int]]] = Field(
        default=None,
        description="Minimum staff per role per shift"
    )
    max_consecutive_days: int = Field(default=6, description="Max consecutive working days")
    max_daily_hours: int = Field(default=8, description="Maximum hours per day")
    max_weekly_hours: int = Field(default=40, description="Maximum hours per week")
    min_rest_hours: int = Field(default=11, description="Minimum rest between shifts")
    respect_roles: bool = Field(default=True, description="Enforce role matching")
    hard_rules: List[str] = Field(
        default_factory=list,
        description="Hard constraints that must be satisfied"
    )
    soft_rules: List[str] = Field(
        default_factory=list,
        description="Soft constraints to optimize for"
    )
    business_model: str = Field(default="5ήμερο", description="Work model (5ήμερο, 6ήμερο)")


class Violation(BaseModel):
    """
    Represents a constraint violation in a schedule.
    """
    type: str = Field(description="Violation type (e.g., MAX_HOURS_EXCEEDED)")
    severity: Severity = Field(description="How critical the violation is")
    employee_id: Optional[str] = Field(default=None, description="Affected employee")
    employee_name: Optional[str] = Field(default=None, description="Employee name")
    day: Optional[Weekday] = Field(default=None, description="Day of violation")
    date: Optional[str] = Field(default=None, description="Date of violation")
    shift: Optional[ShiftType] = Field(default=None, description="Shift involved")
    description: str = Field(description="Human-readable violation description")
    rule_violated: str = Field(description="Which rule was violated")
    current_value: Optional[float] = Field(default=None, description="Current value")
    max_allowed: Optional[float] = Field(default=None, description="Maximum allowed value")


class Suggestion(BaseModel):
    """
    Represents an optimization suggestion for improving the schedule.
    """
    type: str = Field(description="Suggestion type (SWAP, REASSIGN, ADD_EMPLOYEE, etc.)")
    priority: Literal["HIGH", "MEDIUM", "LOW"] = Field(description="Priority level")
    employee_id: Optional[str] = Field(default=None, description="Primary employee")
    employee_id2: Optional[str] = Field(default=None, description="Second employee (for swaps)")
    day: Optional[Weekday] = Field(default=None, description="Day affected")
    date: Optional[str] = Field(default=None, description="Date affected")
    shift: Optional[ShiftType] = Field(default=None, description="Shift affected")
    role: Optional[Role] = Field(default=None, description="Role involved")
    description: str = Field(description="Human-readable suggestion")
    expected_benefit: str = Field(description="Expected benefit from implementing")
    impact_score: Optional[float] = Field(default=None, ge=0, le=100, description="Impact score 0-100")


class ScheduleAnalysis(BaseModel):
    """
    Complete analysis of a schedule including violations and suggestions.
    """
    schedule: Schedule = Field(description="The analyzed schedule")
    violations: List[Violation] = Field(description="All detected violations")
    suggestions: List[Suggestion] = Field(description="Optimization suggestions")
    overall_score: float = Field(ge=0, le=100, description="Overall schedule quality 0-100")
    analysis_text: str = Field(description="Natural language analysis")
    metadata: Optional[Dict] = Field(default_factory=dict, description="Additional analysis data")


class ScheduleRequest(BaseModel):
    """
    Request to generate a new schedule.
    """
    employees: List[Employee] = Field(description="All available employees")
    availability: List[Availability] = Field(description="Employee availability data")
    constraints: Constraints = Field(description="Scheduling constraints")
    week_start: str = Field(description="Week start date (YYYY-MM-DD)")
    days_count: int = Field(default=7, ge=1, le=31, description="Number of days to schedule")
    preferences: Optional[Dict] = Field(default_factory=dict, description="Additional preferences")


class ScheduleResponse(BaseModel):
    """
    Response from schedule generation.
    """
    schedule: Schedule = Field(description="Generated schedule")
    violations: List[Violation] = Field(description="Any violations in the schedule")
    suggestions: List[Suggestion] = Field(description="Suggestions for improvement")
    success: bool = Field(description="Whether generation was successful")
    message: str = Field(description="Status message")
    metadata: Optional[Dict] = Field(default_factory=dict, description="Additional response data")


# Helper functions for model conversion

def employee_to_dict(employee: Employee) -> Dict:
    """Convert Employee to dict for JSON serialization."""
    return employee.dict()


def schedule_to_dict(schedule: Schedule) -> Dict:
    """Convert Schedule to dict for JSON serialization."""
    return schedule.dict()


def dict_to_employee(data: Dict) -> Employee:
    """Convert dict to Employee."""
    return Employee(**data)


def dict_to_schedule(data: Dict) -> Schedule:
    """Convert dict to Schedule."""
    return Schedule(**data)


# Example instances for testing

def create_example_employee() -> Employee:
    """Create an example employee."""
    return Employee(
        id="emp_001",
        name="Γιάννης Παπαδόπουλος",
        role="Manager",
        roles=["Manager", "Barista"],
        max_hours_per_week=40,
        max_hours_per_day=8,
        min_rest_hours=11,
        max_consecutive_days=5,
        preferred_shifts=["morning", "day"],
        seniority="senior"
    )


def create_example_constraints() -> Constraints:
    """Create example constraints."""
    return Constraints(
        min_staff_per_shift={
            "morning": 2,
            "afternoon": 2,
            "evening": 1,
            "day": 3,
            "night": 2
        },
        max_staff_per_shift={
            "morning": 5,
            "afternoon": 5,
            "evening": 3,
            "day": 8,
            "night": 5
        },
        min_staff_per_role={
            "Manager": {"day": 1, "night": 1},
            "Barista": {"day": 2, "night": 1}
        },
        max_consecutive_days=6,
        max_daily_hours=8,
        max_weekly_hours=40,
        min_rest_hours=11,
        respect_roles=True,
        hard_rules=[
            "No employee works more than max_hours_per_week",
            "Respect min_rest_hours between consecutive days",
            "Each shift must have minimum required staff"
        ],
        soft_rules=[
            "Try to satisfy preferred shifts",
            "Distribute weekends fairly",
            "Balance workload across employees"
        ],
        business_model="5ήμερο"
    )


if __name__ == "__main__":
    # Test models
    print("Testing Pydantic models...")
    
    emp = create_example_employee()
    print(f"[OK] Employee: {emp.name} ({emp.role})")
    
    constraints = create_example_constraints()
    print(f"[OK] Constraints: {constraints.business_model}")
    
    assignment = ShiftAssignment(
        day="Mon",
        date="2025-12-15",
        shift="day",
        employee_id="emp_001",
        employee_name="Γιάννης",
        role="Manager",
        hours=8.0
    )
    print(f"[OK] Assignment: {assignment.employee_name} on {assignment.date}")
    
    schedule = Schedule(
        week_start="2025-12-15",
        assignments=[assignment]
    )
    print(f"[OK] Schedule: Week starting {schedule.week_start} with {len(schedule.assignments)} assignments")
    
    print("\n[SUCCESS] All models validated successfully!")
