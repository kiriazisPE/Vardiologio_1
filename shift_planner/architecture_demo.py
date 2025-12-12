# -*- coding: utf-8 -*-
"""
Complete Architecture Demo
Demonstrates the full DSPy scheduling pipeline from models to schedule generation.
"""

import json
from datetime import date, timedelta
from typing import List

# Import our architecture components
from models import (
    Employee, Availability, Constraints, Schedule,
    create_example_employee, create_example_constraints
)
from backend import (
    generate_schedule,
    analyze_schedule,
    fix_schedule,
    optimize_schedule,
    comprehensive_schedule_pipeline
)
from dspy_config import is_configured, configure_dspy


def print_section(title: str, char: str = "="):
    """Print a section header."""
    print(f"\n{char * 70}")
    print(f" {title}")
    print(f"{char * 70}\n")


def create_demo_data():
    """Create demo employees, availability, and constraints."""
    
    # Create employees
    employees = [
        Employee(
            id="emp_001",
            name="Γιάννης Παπαδόπουλος",
            role="Manager",
            roles=["Manager", "Barista"],
            max_hours_per_week=40,
            max_hours_per_day=8,
            preferred_shifts=["day", "morning"],
            seniority="senior"
        ),
        Employee(
            id="emp_002",
            name="Μαρία Κωνσταντίνου",
            role="Barista",
            roles=["Barista", "Cashier"],
            max_hours_per_week=40,
            max_hours_per_day=8,
            preferred_shifts=["day", "afternoon"],
            seniority="mid"
        ),
        Employee(
            id="emp_003",
            name="Νίκος Γεωργίου",
            role="Barista",
            roles=["Barista"],
            max_hours_per_week=30,
            max_hours_per_day=8,
            preferred_shifts=["evening", "night"],
            seniority="junior"
        ),
        Employee(
            id="emp_004",
            name="Ελένη Δημητρίου",
            role="Cashier",
            roles=["Cashier", "Barista"],
            max_hours_per_week=40,
            max_hours_per_day=8,
            preferred_shifts=["morning", "day"],
            seniority="mid"
        )
    ]
    
    # Create availability (all available for simplicity)
    availability = []
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    start_date = date(2025, 12, 15)
    
    for i, day in enumerate(days):
        current_date = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        
        for emp in employees:
            # Everyone available most days, with some variety
            if emp.id == "emp_003" and day in ["Mon", "Tue"]:
                # Νίκος unavailable Mon-Tue
                continue
            
            available_shifts = ["day", "morning", "afternoon", "evening", "night"]
            if emp.seniority == "junior":
                # Junior employees prefer specific shifts
                available_shifts = emp.preferred_shifts or available_shifts
            
            availability.append(Availability(
                employee_id=emp.id,
                day=day,
                date=current_date,
                available_shifts=available_shifts
            ))
    
    # Create constraints
    constraints = Constraints(
        min_staff_per_shift={
            "morning": 1,
            "day": 2,
            "afternoon": 1,
            "evening": 1,
            "night": 1
        },
        max_staff_per_shift={
            "morning": 3,
            "day": 4,
            "afternoon": 3,
            "evening": 2,
            "night": 2
        },
        min_staff_per_role={
            "Manager": {"day": 1, "morning": 1},
            "Barista": {"day": 1, "afternoon": 1, "evening": 1, "night": 1},
        },
        max_consecutive_days=6,
        max_daily_hours=8,
        max_weekly_hours=40,
        min_rest_hours=11,
        respect_roles=True,
        hard_rules=[
            "No employee works more than max_hours_per_week",
            "Respect min_rest_hours between consecutive shifts",
            "Each shift must have minimum required staff",
            "Respect employee availability",
            "Respect role requirements"
        ],
        soft_rules=[
            "Try to satisfy preferred shifts",
            "Distribute weekends fairly",
            "Balance workload across employees",
            "Minimize consecutive working days",
            "Assign senior employees to critical shifts"
        ],
        business_model="6ήμερο"
    )
    
    return employees, availability, constraints


def demo_1_basic_generation():
    """Demo 1: Basic schedule generation."""
    print_section("Demo 1: Basic Schedule Generation")
    
    employees, availability, constraints = create_demo_data()
    
    print("📊 Setup:")
    print(f"  Employees: {len(employees)}")
    for emp in employees:
        print(f"    - {emp.name} ({emp.role}, {emp.seniority})")
    print(f"  Availability records: {len(availability)}")
    print(f"  Business model: {constraints.business_model}")
    print(f"  Hard rules: {len(constraints.hard_rules)}")
    print(f"  Soft rules: {len(constraints.soft_rules)}")
    
    print("\n🚀 Generating schedule...")
    
    result = generate_schedule(
        employees=employees,
        availability=availability,
        constraints=constraints,
        week_start="2025-12-15",
        days_count=7
    )
    
    schedule = result['schedule']
    
    print(f"\n✅ Schedule generated!")
    print(f"  Week: {schedule.week_start} to {schedule.week_end}")
    print(f"  Total assignments: {len(schedule.assignments)}")
    print(f"\n  Reasoning: {result['reasoning'][:200]}...")
    
    # Show first few assignments
    print(f"\n  First 5 assignments:")
    for i, assignment in enumerate(schedule.assignments[:5]):
        print(f"    {i+1}. {assignment.date} ({assignment.day}) - {assignment.shift}")
        print(f"       Employee: {assignment.employee_name or assignment.employee_id}")
        print(f"       Role: {assignment.role}, Hours: {assignment.hours}")
    
    return schedule, employees, availability, constraints


def demo_2_analysis(schedule, employees, availability, constraints):
    """Demo 2: Analyze the schedule for violations."""
    print_section("Demo 2: Schedule Analysis")
    
    print("🔍 Analyzing schedule for violations...")
    
    result = analyze_schedule(
        employees=employees,
        availability=availability,
        constraints=constraints,
        schedule=schedule
    )
    
    violations = result['violations']
    quality_score = result['quality_score']
    
    print(f"\n📊 Analysis Results:")
    print(f"  Quality Score: {quality_score}/100")
    print(f"  Violations Found: {len(violations)}")
    
    if violations:
        # Group by severity
        critical = [v for v in violations if v.severity == "CRITICAL"]
        high = [v for v in violations if v.severity == "HIGH"]
        medium = [v for v in violations if v.severity == "MEDIUM"]
        low = [v for v in violations if v.severity == "LOW"]
        
        if critical:
            print(f"\n  🚨 CRITICAL ({len(critical)}):")
            for v in critical[:3]:
                print(f"    - {v.description}")
        
        if high:
            print(f"\n  ⚠️  HIGH ({len(high)}):")
            for v in high[:3]:
                print(f"    - {v.description}")
        
        if medium:
            print(f"\n  ⚡ MEDIUM ({len(medium)}):")
            for v in medium[:2]:
                print(f"    - {v.description}")
        
        if low:
            print(f"\n  ℹ️  LOW ({len(low)}):")
            for v in low[:2]:
                print(f"    - {v.description}")
    else:
        print("  ✅ No violations detected!")
    
    print(f"\n  Analysis: {result['analysis'][:200]}...")
    
    return violations


def demo_3_comprehensive_pipeline():
    """Demo 3: Complete pipeline (Generate → Analyze → Fix → Optimize)."""
    print_section("Demo 3: Comprehensive Pipeline")
    
    employees, availability, constraints = create_demo_data()
    
    print("🚀 Running complete pipeline:")
    print("  1️⃣  Generate initial schedule")
    print("  2️⃣  Analyze for violations")
    print("  3️⃣  Fix violations")
    print("  4️⃣  Optimize for soft constraints")
    
    print("\n⏳ Processing... (this may take a minute)")
    
    result = comprehensive_schedule_pipeline(
        employees=employees,
        availability=availability,
        constraints=constraints,
        week_start="2025-12-15",
        days_count=7,
        auto_fix=True,
        auto_optimize=True
    )
    
    print("\n✅ Pipeline completed!")
    
    # Show results
    print("\n📊 Results:")
    
    if 'initial_schedule' in result:
        print(f"\n  Initial Schedule:")
        print(f"    Assignments: {len(result['initial_schedule'].assignments)}")
        if 'initial_reasoning' in result:
            print(f"    Reasoning: {result['initial_reasoning'][:150]}...")
    
    if 'violations' in result:
        print(f"\n  Violations Detected: {len(result['violations'])}")
        if result['violations']:
            print(f"    Severities: ", end="")
            severities = {}
            for v in result['violations']:
                severities[v.severity] = severities.get(v.severity, 0) + 1
            print(", ".join([f"{k}: {v}" for k, v in severities.items()]))
    
    if 'quality_score' in result:
        print(f"\n  Quality Score: {result['quality_score']}/100")
    
    if 'suggestions' in result:
        print(f"\n  Suggestions Generated: {len(result['suggestions'])}")
        if result['suggestions']:
            high_priority = [s for s in result['suggestions'] if s.priority == "HIGH"]
            print(f"    High priority: {len(high_priority)}")
            if high_priority:
                print(f"\n    Top suggestion:")
                print(f"      {high_priority[0].description}")
                print(f"      Expected benefit: {high_priority[0].expected_benefit}")
    
    if 'fixed_schedule' in result:
        print(f"\n  Fixed Schedule:")
        print(f"    Assignments: {len(result['fixed_schedule'].assignments)}")
        if 'improvement_explanation' in result:
            print(f"    Improvements: {result['improvement_explanation'][:150]}...")
    
    if 'final_schedule' in result:
        print(f"\n  Final Optimized Schedule:")
        print(f"    Assignments: {len(result['final_schedule'].assignments)}")
        if 'optimization_explanation' in result:
            print(f"    Optimizations: {result['optimization_explanation'][:150]}...")
    
    if 'improvements' in result and result['improvements']:
        print(f"\n  Optimization Improvements:")
        for improvement in result['improvements'][:3]:
            if isinstance(improvement, dict):
                metric = improvement.get('metric', 'Unknown')
                benefit = improvement.get('benefit', 'N/A')
                print(f"    - {metric}: {benefit}")
    
    return result


def main():
    """Run all demos."""
    print("\n" + "🎯 " + "="*68)
    print(" DSPy Scheduler Architecture - Complete Demo")
    print("="*70)
    
    # Check configuration
    if not is_configured():
        print("\n⚠️  DSPy not configured. Attempting auto-configuration...")
        success = configure_dspy()
        if not success:
            print("\n❌ Failed to configure DSPy!")
            print("   Please set OPENAI_API_KEY environment variable.")
            return
    
    print("\n✅ DSPy configured and ready!")
    
    try:
        # Run demos
        schedule, employees, availability, constraints = demo_1_basic_generation()
        
        input("\nPress Enter to continue to analysis demo...")
        violations = demo_2_analysis(schedule, employees, availability, constraints)
        
        input("\nPress Enter to continue to comprehensive pipeline demo...")
        comprehensive_result = demo_3_comprehensive_pipeline()
        
        print("\n" + "="*70)
        print(" ✅ All demos completed successfully!")
        print("="*70)
        
        print("\n📚 What you've seen:")
        print("  1. Pydantic models for type-safe data")
        print("  2. DSPy signatures for structured LLM I/O")
        print("  3. Backend API for clean integration")
        print("  4. Complete pipeline: Generate → Analyze → Fix → Optimize")
        
        print("\n🚀 Next steps:")
        print("  - Integrate with Streamlit UI")
        print("  - Add persistence layer (SQLite)")
        print("  - Collect training examples")
        print("  - Train DSPy optimizer")
        
        print("\n📖 See README_ARCHITECTURE.md for full documentation")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
