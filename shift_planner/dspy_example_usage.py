# -*- coding: utf-8 -*-
"""
DSPy Signatures Usage Examples for Shift Scheduling
Demonstrates how to use structured input/output with DSPy.
"""

import os
import json
import datetime as dt
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check if we have the API key
if not os.getenv("OpenAI_API_KEY"):
    print("⚠️  Warning: OpenAI_API_KEY not set in environment")
    print("Please set it in .env file or environment variables")
    exit(1)

from ai_scheduler import (
    get_shifts_per_day_structured,
    get_employee_availability_structured,
    get_violations_structured,
    get_suggestions_structured,
    get_comprehensive_analysis_structured,
    DSPY_AVAILABLE
)

import pandas as pd


def print_section(title: str):
    """Print a section header."""
    print("\n" + "="*70)
    print(f" {title}")
    print("="*70)


def example_1_shifts_per_day():
    """Example 1: Get structured shifts per day."""
    print_section("Example 1: Shifts Per Day (Structured Output)")
    
    shifts = get_shifts_per_day_structured(
        business_model="5ήμερο",
        start_date=dt.date(2025, 12, 15),
        days_count=7,
        active_shifts=["day", "night"],
        roles=["Manager", "Barista", "Cashier"],
        role_requirements={
            "Manager": {"day": 1, "night": 1},
            "Barista": {"day": 2, "night": 1},
            "Cashier": {"day": 1, "night": 1}
        },
        special_requirements="Weekend shifts need extra Barista coverage"
    )
    
    print(f"\n📅 Planned {len(shifts)} days of shifts:")
    for day in shifts[:3]:  # Show first 3 days
        print(f"\n  Date: {day['date']} ({day['day_name']})")
        print(f"  Weekend: {day['is_weekend']}")
        print(f"  Total Staff Needed: {day['total_staff_needed']}")
        print(f"  Shifts: {len(day['shifts'])} shift-role combinations")
        for shift in day['shifts'][:2]:  # Show first 2 shifts
            print(f"    - {shift['shift_type']} {shift['role']}: {shift['required_count']} person(s)")
    
    print(f"\n... and {len(shifts) - 3} more days")
    return shifts


def example_2_employee_availability():
    """Example 2: Get structured employee availability."""
    print_section("Example 2: Employee Availability (Structured Output)")
    
    employees = [
        {
            "name": "Γιάννης Παπαδόπουλος",
            "roles": ["Manager"],
            "availability": ["2025-12-15", "2025-12-16", "2025-12-17"],
            "preferred_shifts": ["day"]
        },
        {
            "name": "Μαρία Κωνσταντίνου",
            "roles": ["Barista", "Cashier"],
            "availability": ["2025-12-15", "2025-12-16", "2025-12-18"],
            "preferred_shifts": ["day", "night"]
        },
        {
            "name": "Νίκος Γεωργίου",
            "roles": ["Barista"],
            "availability": ["2025-12-16", "2025-12-17", "2025-12-18", "2025-12-19"],
            "preferred_shifts": ["night"]
        }
    ]
    
    # Empty schedule for this example
    current_schedule = pd.DataFrame()
    
    work_rules = {
        "max_daily_hours_5days": 8,
        "weekly_hours_5days": 40,
        "min_daily_rest": 11,
        "max_consecutive_days": 6
    }
    
    availability = get_employee_availability_structured(
        employees=employees,
        schedule_start=dt.date(2025, 12, 15),
        schedule_days=7,
        current_schedule=current_schedule,
        work_rules=work_rules
    )
    
    print(f"\n👥 Availability for {len(availability)} employees:")
    for emp in availability:
        print(f"\n  {emp['name']}")
        print(f"    Roles: {', '.join(emp['roles'])}")
        print(f"    Available dates: {len(emp['available_dates'])} days")
        print(f"    Preferred shifts: {', '.join(emp.get('preferred_shifts', []))}")
        print(f"    Weekly hours: {emp['current_weekly_hours']}/{emp['max_weekly_hours']}")
        if emp.get('constraints'):
            print(f"    Constraints: {emp['constraints']}")
    
    return availability


def example_3_violations():
    """Example 3: Detect violations with structured output."""
    print_section("Example 3: Violation Detection (Structured Output)")
    
    # Sample schedule with violations
    schedule_data = pd.DataFrame([
        {"Υπάλληλος": "Γιάννης", "Ημερομηνία": "2025-12-15", "Βάρδια": "day", "Ρόλος": "Manager", "Ώρες": 8},
        {"Υπάλληλος": "Γιάννης", "Ημερομηνία": "2025-12-15", "Βάρδια": "night", "Ρόλος": "Manager", "Ώρες": 8},  # Double shift
        {"Υπάλληλος": "Γιάννης", "Ημερομηνία": "2025-12-16", "Βάρδια": "day", "Ρόλος": "Manager", "Ώρες": 8},
        {"Υπάλληλος": "Μαρία", "Ημερομηνία": "2025-12-15", "Βάρδια": "day", "Ρόλος": "Barista", "Ώρες": 10},  # Over daily limit
        {"Υπάλληλος": "Μαρία", "Ημερομηνία": "2025-12-16", "Βάρδια": "day", "Ρόλος": "Barista", "Ώρες": 10},
        {"Υπάλληλος": "Μαρία", "Ημερομηνία": "2025-12-17", "Βάρδια": "day", "Ρόλος": "Barista", "Ώρες": 10},
        {"Υπάλληλος": "Μαρία", "Ημερομηνία": "2025-12-18", "Βάρδια": "day", "Ρόλος": "Barista", "Ώρες": 10},
    ])
    
    employees = [
        {"name": "Γιάννης", "roles": ["Manager"], "max_weekly_hours": 40},
        {"name": "Μαρία", "roles": ["Barista"], "max_weekly_hours": 40}
    ]
    
    work_rules = {
        "max_daily_hours_5days": 8,
        "weekly_hours_5days": 40,
        "min_daily_rest": 11,
        "max_consecutive_days": 5
    }
    
    role_requirements = {
        "Manager": {"min_experience_months": 12},
        "Barista": {"min_experience_months": 3}
    }
    
    violations = get_violations_structured(
        schedule_df=schedule_data,
        employees=employees,
        work_rules=work_rules,
        role_requirements=role_requirements,
        business_constraints="No employee should work both day and night shift on same day"
    )
    
    print(f"\n⚠️  Found {len(violations)} violations:")
    
    # Group by severity
    by_severity = {}
    for v in violations:
        severity = v.get('severity', 'UNKNOWN')
        by_severity.setdefault(severity, []).append(v)
    
    for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        if severity in by_severity:
            print(f"\n  {severity} ({len(by_severity[severity])}):")
            for v in by_severity[severity][:2]:  # Show first 2 of each severity
                print(f"    - {v['violation_type']}: {v['description']}")
                if v.get('employee'):
                    print(f"      Employee: {v['employee']}")
                if v.get('current_value') and v.get('max_allowed'):
                    print(f"      Value: {v['current_value']} (max: {v['max_allowed']})")
    
    return violations


def example_4_suggestions():
    """Example 4: Get optimization suggestions."""
    print_section("Example 4: Optimization Suggestions (Structured Output)")
    
    # Use violations from previous example
    violations = [
        {
            "violation_type": "MAX_DAILY_HOURS_EXCEEDED",
            "severity": "HIGH",
            "employee": "Μαρία",
            "date": "2025-12-15",
            "description": "Working 10 hours, exceeds max 8 hours",
            "current_value": 10.0,
            "max_allowed": 8.0
        },
        {
            "violation_type": "INSUFFICIENT_REST",
            "severity": "CRITICAL",
            "employee": "Γιάννης",
            "date": "2025-12-15",
            "description": "Day shift followed by night shift - only 4 hours rest"
        }
    ]
    
    schedule_data = pd.DataFrame([
        {"Υπάλληλος": "Γιάννης", "Ημερομηνία": "2025-12-15", "Βάρδια": "day", "Ρόλος": "Manager", "Ώρες": 8},
        {"Υπάλληλος": "Μαρία", "Ημερομηνία": "2025-12-15", "Βάρδια": "day", "Ρόλος": "Barista", "Ώρες": 10},
    ])
    
    employees = [
        {"name": "Γιάννης", "roles": ["Manager"], "available": True},
        {"name": "Μαρία", "roles": ["Barista"], "available": True},
        {"name": "Νίκος", "roles": ["Barista", "Manager"], "available": True}
    ]
    
    suggestions = get_suggestions_structured(
        schedule_df=schedule_data,
        violations=violations,
        employees=employees,
        roles=["Manager", "Barista", "Cashier"],
        active_shifts=["day", "night"],
        optimization_goals="Fix all violations, balance workload, ensure fairness"
    )
    
    print(f"\n💡 Generated {len(suggestions)} suggestions:")
    
    # Group by priority
    by_priority = {}
    for s in suggestions:
        priority = s.get('priority', 'UNKNOWN')
        by_priority.setdefault(priority, []).append(s)
    
    for priority in ['HIGH', 'MEDIUM', 'LOW']:
        if priority in by_priority:
            print(f"\n  {priority} Priority ({len(by_priority[priority])}):")
            for s in by_priority[priority]:
                print(f"    - {s['suggestion_type']}: {s['description']}")
                print(f"      Benefit: {s['expected_benefit']}")
                if s.get('impact_score'):
                    print(f"      Impact: {s['impact_score']}/100")
                if s.get('employee'):
                    print(f"      Employee: {s['employee']}")
    
    return suggestions


def example_5_comprehensive():
    """Example 5: Comprehensive analysis with all outputs."""
    print_section("Example 5: Comprehensive Analysis (All Structured Outputs)")
    
    business_settings = {
        "name": "Καφετέρια Αθήνα",
        "model": "5ήμερο",
        "shifts": ["day", "night"],
        "roles": ["Manager", "Barista", "Cashier"]
    }
    
    employees = [
        {"name": "Γιάννης", "roles": ["Manager"], "seniority": "senior"},
        {"name": "Μαρία", "roles": ["Barista", "Cashier"], "seniority": "mid"},
        {"name": "Νίκος", "roles": ["Barista"], "seniority": "junior"}
    ]
    
    schedule_params = {
        "start_date": dt.date(2025, 12, 15),
        "days_count": 7,
        "active_shifts": ["day", "night"],
        "roles": ["Manager", "Barista", "Cashier"],
        "role_requirements": {
            "Manager": {"day": 1, "night": 1},
            "Barista": {"day": 2, "night": 1},
            "Cashier": {"day": 1, "night": 1}
        }
    }
    
    current_schedule = pd.DataFrame()
    
    work_rules = {
        "max_daily_hours_5days": 8,
        "weekly_hours_5days": 40,
        "min_daily_rest": 11,
        "max_consecutive_days": 6
    }
    
    analysis = get_comprehensive_analysis_structured(
        business_settings=business_settings,
        employees=employees,
        schedule_params=schedule_params,
        current_schedule=current_schedule,
        work_rules=work_rules
    )
    
    print("\n📊 Comprehensive Analysis Results:")
    print(f"\n  Shifts Per Day: {len(analysis['shifts_per_day'])} days planned")
    print(f"  Employee Availability: {len(analysis['employee_availability'])} employees analyzed")
    print(f"  Violations: {len(analysis['violations'])} violations detected")
    print(f"  Suggestions: {len(analysis['suggestions'])} optimization suggestions")
    print(f"\n  Overall Score: {analysis['overall_score']}")
    
    # Show sample from each section
    if analysis['shifts_per_day']:
        print(f"\n  Sample shift (first day):")
        first_day = analysis['shifts_per_day'][0]
        print(f"    Date: {first_day['date']}")
        print(f"    Staff needed: {first_day['total_staff_needed']}")
    
    if analysis['violations']:
        print(f"\n  Sample violation:")
        print(f"    {analysis['violations'][0]['description']}")
    
    if analysis['suggestions']:
        print(f"\n  Top suggestion:")
        print(f"    {analysis['suggestions'][0]['description']}")
    
    return analysis


def main():
    """Run all examples."""
    print("\n" + "🚀 " + "="*68)
    print(" DSPy Structured Scheduling Examples")
    print("="*70)
    
    if not DSPY_AVAILABLE:
        print("\n⚠️  DSPy not available. Examples will use fallback implementations.")
        print("To use DSPy, install: pip install dspy-ai")
    else:
        print("\n✅ DSPy is available and initialized!")
    
    try:
        # Run examples
        example_1_shifts_per_day()
        example_2_employee_availability()
        example_3_violations()
        example_4_suggestions()
        example_5_comprehensive()
        
        print("\n" + "="*70)
        print(" ✅ All examples completed successfully!")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
