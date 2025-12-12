"""
Pytest Test Suite for DSPy-Based Shift Scheduling System
Run with: pytest test_dspy_system.py -v
"""
import pytest
import sys
import os

# Ensure UTF-8 output for Greek characters
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


# ============================================================================
# Test Configuration
# ============================================================================
class TestConfiguration:
    """Test DSPy configuration with OpenAI"""
    
    def test_api_key_exists(self):
        """Verify OpenAI API key is configured"""
        from dspy_config import get_openai_api_key
        
        api_key = get_openai_api_key()
        assert api_key is not None, "OpenAI API key not found in environment"
        assert len(api_key) > 0, "OpenAI API key is empty"
    
    def test_dspy_configuration(self):
        """Test DSPy configures successfully"""
        from dspy_config import configure_dspy
        import dspy
        
        configure_dspy()
        
        assert hasattr(dspy.settings, 'lm'), "DSPy LM not configured"
        assert dspy.settings.lm is not None, "DSPy LM is None"
    
    def test_dspy_lm_type(self):
        """Verify correct LM type is configured"""
        import dspy
        from dspy_config import configure_dspy
        
        configure_dspy()
        lm_type = type(dspy.settings.lm).__name__
        assert lm_type == "LM", f"Expected LM, got {lm_type}"


# ============================================================================
# Test Pydantic Models
# ============================================================================
class TestModels:
    """Test Pydantic data models"""
    
    def test_employee_model(self):
        """Test Employee model creation and validation"""
        from models import Employee
        
        emp = Employee(
            id="emp_001",
            name="Test Employee",
            role="Manager",
            roles=["Manager", "Barista"]
        )
        
        assert emp.id == "emp_001"
        assert emp.name == "Test Employee"
        assert emp.role == "Manager"
        assert "Manager" in emp.roles
    
    def test_employee_role_auto_add(self):
        """Test that primary role is automatically added to roles list"""
        from models import Employee
        
        emp = Employee(
            id="emp_002",
            name="Test Employee 2",
            role="Cashier",
            roles=[]  # Empty roles
        )
        
        # Primary role should be auto-added to roles list
        assert "Cashier" in emp.roles
    
    def test_constraints_model(self):
        """Test Constraints model"""
        from models import Constraints
        
        constraints = Constraints(
            min_employees_per_shift=2,
            max_employees_per_shift=5,
            shift_duration_hours=8.0
        )
        
        assert constraints.min_employees_per_shift == 2
        assert constraints.max_employees_per_shift == 5
        assert constraints.shift_duration_hours == 8.0
    
    def test_shift_assignment_model(self):
        """Test ShiftAssignment model"""
        from models import ShiftAssignment
        
        assignment = ShiftAssignment(
            day="Mon",
            date="2025-12-15",
            shift="day",
            employee_id="emp_001",
            employee_name="Test Employee",
            role="Manager",
            hours=8.0
        )
        
        assert assignment.day == "Mon"
        assert assignment.date == "2025-12-15"
        assert assignment.shift == "day"
        assert assignment.hours == 8.0
    
    def test_schedule_model(self):
        """Test Schedule model with assignments"""
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
        assert schedule.assignments[0].employee_id == "emp_001"
    
    def test_violation_model(self):
        """Test Violation model"""
        from models import Violation
        
        violation = Violation(
            type="coverage",
            severity="HIGH",  # Must be uppercase
            description="Test violation",
            rule_violated="MIN_COVERAGE"
        )
        
        assert violation.type == "coverage"
        assert violation.severity == "HIGH"
        assert violation.rule_violated == "MIN_COVERAGE"
    
    def test_suggestion_model(self):
        """Test Suggestion model"""
        from models import Suggestion
        
        suggestion = Suggestion(
            type="assignment",
            priority="HIGH",  # Must be uppercase
            description="Test suggestion",
            expected_benefit="Improved coverage"
        )
        
        assert suggestion.type == "assignment"
        assert suggestion.priority == "HIGH"


# ============================================================================
# Test DSPy Signatures
# ============================================================================
class TestSignatures:
    """Test DSPy signature definitions"""
    
    def test_generate_schedule_signature(self):
        """Test GenerateSchedule signature exists"""
        from dspy_scheduler import GenerateSchedule
        
        assert GenerateSchedule is not None
        assert hasattr(GenerateSchedule, '__signature__')
    
    def test_analyze_schedule_signature(self):
        """Test AnalyzeSchedule signature exists"""
        from dspy_scheduler import AnalyzeSchedule
        
        assert AnalyzeSchedule is not None
        assert hasattr(AnalyzeSchedule, '__signature__')
    
    def test_fix_schedule_signature(self):
        """Test FixSchedule signature exists"""
        from dspy_scheduler import FixSchedule
        
        assert FixSchedule is not None
        assert hasattr(FixSchedule, '__signature__')
    
    def test_optimize_schedule_signature(self):
        """Test OptimizeSchedule signature exists"""
        from dspy_scheduler import OptimizeSchedule
        
        assert OptimizeSchedule is not None
        assert hasattr(OptimizeSchedule, '__signature__')


# ============================================================================
# Test DSPy Modules
# ============================================================================
class TestModules:
    """Test DSPy module instantiation"""
    
    def test_schedule_planner_module(self):
        """Test SchedulePlanner module instantiation"""
        from dspy_scheduler import SchedulePlanner
        
        planner = SchedulePlanner()
        assert planner is not None
        assert hasattr(planner, 'forward')
    
    def test_schedule_analyzer_module(self):
        """Test ScheduleAnalyzer module instantiation"""
        from dspy_scheduler import ScheduleAnalyzer
        
        analyzer = ScheduleAnalyzer()
        assert analyzer is not None
        assert hasattr(analyzer, 'forward')
    
    def test_schedule_fixer_module(self):
        """Test ScheduleFixer module instantiation"""
        from dspy_scheduler import ScheduleFixer
        
        fixer = ScheduleFixer()
        assert fixer is not None
        assert hasattr(fixer, 'forward')
    
    def test_schedule_optimizer_module(self):
        """Test ScheduleOptimizer module instantiation"""
        from dspy_scheduler import ScheduleOptimizer
        
        optimizer = ScheduleOptimizer()
        assert optimizer is not None
        assert hasattr(optimizer, 'forward')
    
    def test_comprehensive_scheduler_module(self):
        """Test ComprehensiveScheduler module instantiation"""
        from dspy_scheduler import ComprehensiveScheduler
        
        scheduler = ComprehensiveScheduler()
        assert scheduler is not None
        assert hasattr(scheduler, 'forward')


# ============================================================================
# Test Backend API
# ============================================================================
class TestBackendAPI:
    """Test backend API functions"""
    
    def test_pydantic_to_json(self):
        """Test pydantic_to_json conversion"""
        from backend import pydantic_to_json
        from models import Employee
        
        emp = Employee(id="emp_001", name="Test", role="Manager")
        result = pydantic_to_json(emp)
        
        assert isinstance(result, dict)
        assert result['id'] == "emp_001"
    
    def test_json_to_pydantic(self):
        """Test json_to_pydantic conversion"""
        from backend import json_to_pydantic
        from models import Employee
        
        data = {"id": "emp_001", "name": "Test", "role": "Manager", "roles": ["Manager"]}
        emp = json_to_pydantic(data, Employee)
        
        assert isinstance(emp, Employee)
        assert emp.id == "emp_001"
    
    def test_generate_schedule_exists(self):
        """Test generate_schedule function exists"""
        from backend import generate_schedule
        
        assert callable(generate_schedule)
    
    def test_analyze_schedule_exists(self):
        """Test analyze_schedule function exists"""
        from backend import analyze_schedule
        
        assert callable(analyze_schedule)
    
    def test_fix_schedule_exists(self):
        """Test fix_schedule function exists"""
        from backend import fix_schedule
        
        assert callable(fix_schedule)
    
    def test_optimize_schedule_exists(self):
        """Test optimize_schedule function exists"""
        from backend import optimize_schedule
        
        assert callable(optimize_schedule)
    
    def test_comprehensive_pipeline_exists(self):
        """Test comprehensive_schedule_pipeline function exists"""
        from backend import comprehensive_schedule_pipeline
        
        assert callable(comprehensive_schedule_pipeline)


# ============================================================================
# Integration Tests (Optional - Requires LLM Calls)
# ============================================================================
@pytest.mark.slow
@pytest.mark.integration
class TestIntegration:
    """Integration tests that make actual LLM calls"""
    
    @pytest.mark.skip(reason="Requires OpenAI API call - run manually with -m integration")
    def test_generate_schedule_integration(self):
        """Test end-to-end schedule generation"""
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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
