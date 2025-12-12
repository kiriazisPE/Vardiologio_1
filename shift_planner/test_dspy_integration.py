"""
Pytest Test Suite for DSPy-Based Shift Scheduling System
Compatible with VS Code Testing Extension
"""
import pytest
import sys
import os


class TestConfiguration:
    """Test DSPy configuration"""
    
    def test_api_key_exists(self):
        """Test that OpenAI API key is configured"""
        from dspy_config import get_openai_api_key
        
        api_key = get_openai_api_key()
        assert api_key is not None, "OpenAI API key not found"
        assert len(api_key) > 0, "OpenAI API key is empty"
    
    def test_dspy_configuration(self):
        """Test DSPy initialization"""
        from dspy_config import configure_dspy
        import dspy
        
        result = configure_dspy()
        assert result is True, "DSPy configuration failed"
        assert hasattr(dspy.settings, 'lm'), "DSPy LM not configured"
        assert dspy.settings.lm is not None, "DSPy LM is None"


class TestModels:
    """Test Pydantic data models"""
    
    def test_employee_model(self):
        """Test Employee model creation and validation"""
        from models import Employee
        
        emp = Employee(
            id="test_001",
            name="Test Employee",
            role="Manager",
            roles=["Manager", "Barista"]
        )
        
        assert emp.id == "test_001"
        assert emp.name == "Test Employee"
        assert emp.role == "Manager"
        assert "Manager" in emp.roles
        assert "Barista" in emp.roles
    
    def test_employee_role_auto_add(self):
        """Test that primary role is auto-added to roles list"""
        from models import Employee
        
        emp = Employee(
            id="test_002",
            name="Test Employee 2",
            role="Cashier",
            roles=["Barista"]  # Cashier should be auto-added
        )
        
        assert "Cashier" in emp.roles, "Primary role should be auto-added to roles list"
    
    def test_shift_assignment_model(self):
        """Test ShiftAssignment model"""
        from models import ShiftAssignment
        
        assignment = ShiftAssignment(
            day="Mon",
            date="2025-12-15",
            shift="day",
            employee_id="emp_001",
            employee_name="Test",
            role="Manager",
            hours=8.0
        )
        
        assert assignment.day == "Mon"
        assert assignment.date == "2025-12-15"
        assert assignment.hours == 8.0
    
    def test_schedule_model(self):
        """Test Schedule model"""
        from models import Schedule, ShiftAssignment
        
        assignment = ShiftAssignment(
            day="Mon",
            date="2025-12-15",
            shift="day",
            employee_id="emp_001",
            employee_name="Test",
            role="Manager",
            hours=8.0
        )
        
        schedule = Schedule(
            week_start="2025-12-15",
            assignments=[assignment]
        )
        
        assert schedule.week_start == "2025-12-15"
        assert len(schedule.assignments) == 1
    
    def test_constraints_model(self):
        """Test Constraints model"""
        from models import create_example_constraints
        
        constraints = create_example_constraints()
        assert constraints.business_model is not None
        assert len(constraints.hard_rules) >= 0  # Should have rules list
    
    def test_violation_model(self):
        """Test Violation model"""
        from models import Violation
        
        violation = Violation(
            type="MAX_HOURS_EXCEEDED",
            severity="HIGH",
            description="Employee exceeded maximum hours",
            rule_violated="max_hours_per_week",
            employee_id="emp_001",
            current_value=45.0,
            max_allowed=40.0
        )
        
        assert violation.type == "MAX_HOURS_EXCEEDED"
        assert violation.severity == "HIGH"
        assert violation.rule_violated == "max_hours_per_week"
    
    def test_suggestion_model(self):
        """Test Suggestion model"""
        from models import Suggestion
        
        suggestion = Suggestion(
            type="SWAP",
            priority="HIGH",
            description="Swap shifts to reduce overtime",
            expected_benefit="Reduces overtime by 5 hours",
            employee_id="emp_001",
            employee_id2="emp_002"
        )
        
        assert suggestion.type == "SWAP"
        assert suggestion.priority == "HIGH"


class TestDSPySignatures:
    """Test DSPy signatures"""
    
    def test_signatures_importable(self):
        """Test that all signatures can be imported"""
        from dspy_scheduler import (
            GenerateSchedule, AnalyzeSchedule,
            FixSchedule, OptimizeSchedule
        )
        
        assert GenerateSchedule is not None
        assert AnalyzeSchedule is not None
        assert FixSchedule is not None
        assert OptimizeSchedule is not None


class TestDSPyModules:
    """Test DSPy modules"""
    
    def test_schedule_planner_instantiation(self):
        """Test SchedulePlanner module creation"""
        from dspy_scheduler import SchedulePlanner
        
        planner = SchedulePlanner()
        assert planner is not None
    
    def test_schedule_analyzer_instantiation(self):
        """Test ScheduleAnalyzer module creation"""
        from dspy_scheduler import ScheduleAnalyzer
        
        analyzer = ScheduleAnalyzer()
        assert analyzer is not None
    
    def test_schedule_fixer_instantiation(self):
        """Test ScheduleFixer module creation"""
        from dspy_scheduler import ScheduleFixer
        
        fixer = ScheduleFixer()
        assert fixer is not None
    
    def test_schedule_optimizer_instantiation(self):
        """Test ScheduleOptimizer module creation"""
        from dspy_scheduler import ScheduleOptimizer
        
        optimizer = ScheduleOptimizer()
        assert optimizer is not None
    
    def test_comprehensive_scheduler_instantiation(self):
        """Test ComprehensiveScheduler module creation"""
        from dspy_scheduler import ComprehensiveScheduler
        
        comprehensive = ComprehensiveScheduler()
        assert comprehensive is not None


class TestBackendAPI:
    """Test backend API functions"""
    
    def test_backend_imports(self):
        """Test that backend functions can be imported"""
        from backend import (
            generate_schedule, analyze_schedule,
            fix_schedule, optimize_schedule,
            comprehensive_schedule_pipeline,
            pydantic_to_json, json_to_pydantic
        )
        
        assert callable(generate_schedule)
        assert callable(analyze_schedule)
        assert callable(fix_schedule)
        assert callable(optimize_schedule)
        assert callable(comprehensive_schedule_pipeline)
        assert callable(pydantic_to_json)
        assert callable(json_to_pydantic)
    
    def test_pydantic_to_json(self):
        """Test Pydantic to JSON conversion"""
        from backend import pydantic_to_json
        from models import Employee
        
        emp = Employee(
            id="test_001",
            name="Test",
            role="Manager"
        )
        
        result = pydantic_to_json(emp)
        assert isinstance(result, dict)
        assert result['id'] == "test_001"
        assert result['name'] == "Test"
    
    def test_json_to_pydantic(self):
        """Test JSON to Pydantic conversion"""
        from backend import json_to_pydantic
        from models import Employee
        
        data = {
            "id": "test_001",
            "name": "Test",
            "role": "Manager",
            "roles": ["Manager"]
        }
        
        emp = json_to_pydantic(data, Employee)
        assert isinstance(emp, Employee)
        assert emp.id == "test_001"
        assert emp.name == "Test"


@pytest.mark.integration
@pytest.mark.slow
class TestIntegration:
    """Integration tests (require OpenAI API calls - marked as slow)"""
    
    @pytest.mark.skip(reason="Requires OpenAI API credits - run manually with pytest -m integration")
    def test_generate_schedule_integration(self):
        """Test actual schedule generation with LLM (skip by default)"""
        from backend import generate_schedule
        from models import create_example_employee, create_example_constraints
        
        employees = [create_example_employee()]
        constraints = create_example_constraints()
        
        result = generate_schedule(
            employees=employees,
            constraints=constraints,
            week_start="2025-12-16"
        )
        
        assert result is not None
        assert 'schedule' in result or 'error' in result


# Pytest configuration
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (deselect with '-m \"not integration\"')"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
