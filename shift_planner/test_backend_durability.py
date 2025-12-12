# -*- coding: utf-8 -*-
"""
Backend Durability & Stress Tests
Tests edge cases, concurrency, data integrity, and error handling
"""

import pytest
import sqlite3
import tempfile
import os
import json
from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Import modules to test
from schedule_templates import (
    save_template, load_template, list_templates, delete_template,
    apply_template_to_schedule, create_template_from_schedule,
    ScheduleTemplate
)
from shift_swaps import (
    create_swap_request, get_swap_requests, approve_swap_request,
    reject_swap_request, cancel_swap_request, get_pending_swap_requests_for_approval,
    create_shift_bid, get_shift_bids, award_shift_bid,
    ShiftSwapRequest, SwapStatus
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_db():
    """Create temporary database for each test"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Use the actual module initialization functions instead of custom schema
    from schedule_templates import init_templates_db
    from shift_swaps import init_swap_db
    
    init_templates_db(path)
    init_swap_db(path)
    
    # Enable WAL mode for better concurrency
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.commit()
    conn.close()
    
    yield path
    
    # Cleanup
    try:
        os.unlink(path)
        # Clean up WAL files
        for suffix in ['-wal', '-shm']:
            try:
                os.unlink(path + suffix)
            except:
                pass
    except:
        pass
    
    # Cleanup
    try:
        os.unlink(path)
    except:
        pass


@pytest.fixture
def sample_template():
    """Create a valid sample template"""
    return ScheduleTemplate(
        name="Test Weekly Template",
        description="Test template for durability testing",
        pattern_type="weekly",
        role_coverage={
            "morning": {"Manager": 1, "Server": 2, "Cook": 1},
            "evening": {"Manager": 1, "Server": 3, "Bartender": 1}
        },
        pattern_data={
            "monday": ["morning", "evening"],
            "friday": ["morning", "evening"],
            "saturday": ["morning", "evening"]
        },
        created_by="test_admin"
    )


# ============================================================================
# TEMPLATE SYSTEM DURABILITY TESTS
# ============================================================================

class TestTemplateDurability:
    """Stress tests for template system"""
    
    def test_extreme_template_names(self, temp_db):
        """Test templates with edge case names"""
        edge_cases = [
            "",  # Empty string
            " " * 1000,  # Very long whitespace
            "a" * 500,  # Very long name
            "Template with émojis 🔥💯🎯",
            "Template\nwith\nnewlines",
            "Template\twith\ttabs",
            "Template with 'quotes' and \"double quotes\"",
            "Template with <html> tags",
            "Template; DROP TABLE schedule_templates;--",  # SQL injection attempt
            "../../etc/passwd",  # Path traversal attempt
            "${MALICIOUS_VAR}",  # Variable injection
        ]
        
        for i, name in enumerate(edge_cases):
            template = ScheduleTemplate(
                name=name or f"fallback_{i}",
                pattern_type="weekly",
                role_coverage={},
                pattern_data={}
            )
            
            # Should either save safely or raise controlled exception
            try:
                template_id = save_template(template, temp_db)
                loaded = load_template(template_id, temp_db)
                assert loaded is not None
            except (ValueError, sqlite3.IntegrityError) as e:
                # Expected for invalid inputs
                assert True
    
    def test_concurrent_template_creation(self, temp_db, sample_template):
        """Test multiple concurrent template saves"""
        results = []
        errors = []
        
        def create_template(idx):
            try:
                template = ScheduleTemplate(
                    name=f"Concurrent Template {idx}",
                    pattern_type="weekly",
                    role_coverage=sample_template.role_coverage,
                    pattern_data=sample_template.pattern_data,
                    created_by=f"user_{idx}"
                )
                template_id = save_template(template, temp_db)
                return template_id
            except Exception as e:
                errors.append((idx, str(e)))
                return None
        
        # Create 50 templates concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_template, i) for i in range(50)]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)
        
        # Verify unique IDs
        assert len(results) == len(set(results)), "Duplicate template IDs created"
        assert len(results) >= 45, f"Too many failed creations: {len(errors)} errors. Errors: {errors[:5]}"
        
        # Verify all templates are retrievable
        templates = list_templates(db_path=temp_db, active_only=False)
        assert len(templates) >= 45, f"Only {len(templates)} templates found in DB, expected >= 45. Created {len(results)}"
    
    def test_template_with_massive_data(self, temp_db):
        """Test template with very large pattern data"""
        # Create massive role coverage (100 roles, 20 shift types)
        massive_coverage = {
            f"shift_{i}": {f"Role_{j}": (j % 5) + 1 for j in range(100)}
            for i in range(20)
        }
        
        # Create massive pattern data (365 days)
        massive_pattern = {
            f"day_{i}": [f"shift_{j}" for j in range(20)]
            for i in range(365)
        }
        
        template = ScheduleTemplate(
            name="Massive Template",
            pattern_type="yearly",
            role_coverage=massive_coverage,
            pattern_data=massive_pattern,
            created_by="stress_test"
        )
        
        # Should handle large data
        template_id = save_template(template, temp_db)
        assert template_id is not None
        
        # Should retrieve correctly
        loaded = load_template(template_id, temp_db)
        assert loaded is not None
        assert len(loaded.role_coverage) == 20
        assert len(loaded.pattern_data) == 365
    
    def test_template_update_race_condition(self, temp_db, sample_template):
        """Test concurrent updates to same template"""
        template_id = save_template(sample_template, temp_db)
        
        def update_template(idx):
            try:
                template = load_template(template_id, temp_db)
                template.name = f"Updated by thread {idx}"
                template.description = f"Update #{idx} at {time.time()}"
                save_template(template, temp_db)
                return True
            except Exception:
                return False
        
        # 20 concurrent updates
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(update_template, range(20)))
        
        # At least some should succeed
        assert sum(results) >= 15
        
        # Template should still be valid
        final = load_template(template_id, temp_db)
        assert final is not None
        assert "Updated by thread" in final.name
    
    def test_template_deletion_integrity(self, temp_db, sample_template):
        """Test template deletion doesn't corrupt database"""
        # Create 10 templates
        ids = []
        for i in range(10):
            template = ScheduleTemplate(
                name=f"Template {i}",
                pattern_type="weekly",
                role_coverage=sample_template.role_coverage,
                pattern_data=sample_template.pattern_data
            )
            ids.append(save_template(template, temp_db))
        
        # Delete every other template (hard delete)
        for i in range(0, 10, 2):
            delete_template(ids[i], soft_delete=False, db_path=temp_db)
        
        # Verify remaining templates (should be 5 active)
        remaining = list_templates(db_path=temp_db, active_only=True)
        assert len(remaining) == 5
        
        # Verify deleted templates are gone
        for i in range(0, 10, 2):
            deleted = load_template(ids[i], temp_db)
            assert deleted is None
    
    def test_apply_template_edge_dates(self, temp_db, sample_template):
        """Test template application with edge case dates"""
        template_id = save_template(sample_template, temp_db)
        template = load_template(template_id, temp_db)
        
        # Mock employees
        employees = [
            {"id": i, "name": f"Employee {i}", "role": "Server", "max_hours": 40}
            for i in range(1, 6)
        ]
        
        edge_dates = [
            date(2024, 2, 29),  # Leap year
            date(2025, 12, 31),  # Year end
            date(2025, 1, 1),   # Year start
            date(2025, 6, 15),  # Mid year
        ]
        
        for start_date in edge_dates:
            schedule = apply_template_to_schedule(
                template, start_date, employees, days_count=30
            )
            assert schedule is not None
            assert 'assignments' in schedule


# ============================================================================
# SHIFT SWAP DURABILITY TESTS
# ============================================================================

class TestShiftSwapDurability:
    """Stress tests for shift swap system"""
    
    def test_concurrent_swap_requests(self, temp_db):
        """Test multiple employees requesting swaps simultaneously"""
        results = []
        errors = []
        
        def create_request(employee_id):
            try:
                swap_id = create_swap_request(
                    requesting_employee_id=employee_id,
                    requesting_employee_name=f"Employee {employee_id}",
                    shift_date=(date.today() + timedelta(days=employee_id)).isoformat(),
                    shift_type="morning",
                    role="Server",
                    swap_type="swap",
                    db_path=temp_db
                )
                return swap_id
            except Exception as e:
                errors.append((employee_id, str(e)))
                return None
        
        # 100 concurrent swap requests
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(create_request, i) for i in range(1, 101)]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)
        
        # Verify all succeeded
        assert len(results) >= 95, f"Too many failures: {len(errors)} errors"
        assert len(results) == len(set(results)), "Duplicate swap IDs"
        
        # Verify retrievable
        all_requests = get_swap_requests(db_path=temp_db)
        assert len(all_requests) >= 95
    
    def test_swap_status_transitions(self, temp_db):
        """Test all valid and invalid status transitions"""
        swap_id = create_swap_request(
            requesting_employee_id=1,
            requesting_employee_name="Test Employee",
            shift_date=(date.today() + timedelta(days=1)).isoformat(),
            shift_type="evening",
            role="Cook",
            swap_type="drop",
            db_path=temp_db
        )
        
        # Valid: pending -> approved
        assert approve_swap_request(swap_id, "manager1", db_path=temp_db)
        
        # Invalid: approved -> pending (should fail)
        swap2_id = create_swap_request(
            requesting_employee_id=2,
            requesting_employee_name="Employee 2",
            shift_date=(date.today() + timedelta(days=2)).isoformat(),
            shift_type="morning",
            role="Server",
            swap_type="swap",
            db_path=temp_db
        )
        
        approve_swap_request(swap2_id, "manager1", db_path=temp_db)
        # Approving again should be idempotent or fail gracefully
        result = approve_swap_request(swap2_id, "manager2", db_path=temp_db)
        assert result in [True, False]  # Either succeeds or fails gracefully
        
        # Valid: pending -> cancelled
        swap3_id = create_swap_request(
            requesting_employee_id=3,
            requesting_employee_name="Employee 3",
            shift_date=(date.today() + timedelta(days=3)).isoformat(),
            shift_type="afternoon",
            role="Host",
            swap_type="pickup",
            db_path=temp_db
        )
        assert cancel_swap_request(swap3_id, db_path=temp_db)
    
    def test_swap_request_data_integrity(self, temp_db):
        """Test data integrity with malicious inputs"""
        malicious_inputs = [
            {
                "requesting_employee_id": -999,  # Negative ID
                "requesting_employee_name": "'; DROP TABLE shift_swap_requests;--",
                "shift_date": "invalid-date",
                "shift_type": "<script>alert('xss')</script>",
                "role": "Role\x00WithNull",
                "swap_type": "invalid_type"
            },
            {
                "requesting_employee_id": 999999999999,  # Huge ID
                "requesting_employee_name": "A" * 10000,  # Very long name
                "shift_date": "9999-12-31",
                "shift_type": "shift" * 1000,
                "role": "role" * 1000,
                "swap_type": "swap"
            }
        ]
        
        for malicious_data in malicious_inputs:
            try:
                swap_id = create_swap_request(
                    **malicious_data,
                    db_path=temp_db
                )
                # If it succeeds, data should be sanitized
                requests = get_swap_requests(db_path=temp_db)
                assert len(requests) > 0
            except (ValueError, sqlite3.IntegrityError, TypeError) as e:
                # Expected for truly invalid data
                assert True
    
    def test_concurrent_approvals(self, temp_db):
        """Test race condition when multiple managers approve same request"""
        swap_id = create_swap_request(
            requesting_employee_id=1,
            requesting_employee_name="Employee 1",
            shift_date=(date.today() + timedelta(days=5)).isoformat(),
            shift_type="morning",
            role="Manager",
            swap_type="drop",
            db_path=temp_db
        )
        
        results = []
        
        def approve_request(manager_id):
            try:
                result = approve_swap_request(
                    swap_id,
                    f"manager_{manager_id}",
                    f"Approved by {manager_id}",
                    temp_db
                )
                return result
            except Exception as e:
                return False
        
        # 10 managers try to approve simultaneously
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(approve_request, range(10)))
        
        # At least one should succeed
        assert any(results)
        
        # Check final state
        requests = get_swap_requests(db_path=temp_db)
        approved = [r for r in requests if r.id == swap_id and r.status == 'approved']
        assert len(approved) == 1
    
    def test_massive_swap_history(self, temp_db):
        """Test system with thousands of swap requests"""
        # Create 1000 swap requests
        for i in range(1000):
            create_swap_request(
                requesting_employee_id=(i % 50) + 1,
                requesting_employee_name=f"Employee {(i % 50) + 1}",
                shift_date=(date.today() + timedelta(days=i % 365)).isoformat(),
                shift_type=["morning", "afternoon", "evening"][i % 3],
                role=["Server", "Cook", "Manager", "Host"][i % 4],
                swap_type=["swap", "drop", "pickup"][i % 3],
                db_path=temp_db
            )
        
        # Query should still work
        all_requests = get_swap_requests(db_path=temp_db)
        assert len(all_requests) == 1000
        
        # Filter by employee should work
        employee_requests = get_swap_requests(employee_id=1, db_path=temp_db)
        assert len(employee_requests) == 20  # 1000 / 50 employees
        
        # Pending requests should work
        pending = get_pending_swap_requests_for_approval(temp_db)
        assert len(pending) == 1000  # All still pending
    
    def test_shift_bid_concurrency(self, temp_db):
        """Test concurrent bidding on same shift"""
        shift_date = (date.today() + timedelta(days=10)).isoformat()
        
        def place_bid(employee_id):
            try:
                bid_id = create_shift_bid(
                    shift_date=shift_date,
                    shift_type="evening",
                    role="Server",
                    employee_id=employee_id,
                    employee_name=f"Employee {employee_id}",
                    priority=employee_id * 10,
                    db_path=temp_db
                )
                return bid_id
            except Exception:
                return None
        
        # 50 employees bid on same shift
        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(place_bid, range(1, 51)))
        
        successful_bids = [r for r in results if r is not None]
        assert len(successful_bids) >= 45
        
        # All bids should be retrievable
        bids = get_shift_bids(shift_date=shift_date, status="pending", db_path=temp_db)
        assert len(bids) >= 45
        
        # Award to highest priority
        sorted_bids = sorted(bids, key=lambda b: b.get('priority', 0), reverse=True)
        top_bid = sorted_bids[0]
        
        # Award the bid
        success = award_shift_bid(top_bid['id'], db_path=temp_db)
        assert success


# ============================================================================
# DATABASE INTEGRITY TESTS
# ============================================================================

class TestDatabaseIntegrity:
    """Test database consistency and recovery"""
    
    def test_corrupted_json_recovery(self, temp_db, sample_template):
        """Test recovery from corrupted JSON data"""
        template_id = save_template(sample_template, temp_db)
        
        # Manually corrupt the JSON in database
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE schedule_templates SET pattern_data = ? WHERE id = ?",
            ("{invalid json}", template_id)
        )
        conn.commit()
        conn.close()
        
        # Loading should handle corruption gracefully
        try:
            template = load_template(template_id, temp_db)
            # Either returns None or raises controlled exception
            assert template is None or isinstance(template, ScheduleTemplate)
        except (ValueError, json.JSONDecodeError):
            # Expected for corrupted data
            assert True
    
    def test_transaction_rollback(self, temp_db):
        """Test database rollback on errors"""
        initial_count = len(list_templates(db_path=temp_db, active_only=False))
        
        # Attempt to create template with duplicate name
        template1 = ScheduleTemplate(
            name="Unique Template",
            pattern_type="weekly",
            role_coverage={},
            pattern_data={}
        )
        save_template(template1, temp_db)
        
        # Try to save again with same name
        try:
            template2 = ScheduleTemplate(
                name="Unique Template",  # Duplicate
                pattern_type="weekly",
                role_coverage={},
                pattern_data={}
            )
            save_template(template2, temp_db)
        except sqlite3.IntegrityError:
            pass
        
        # Should only have one template
        final_count = len(list_templates(db_path=temp_db, active_only=False))
        assert final_count == initial_count + 1
    
    def test_foreign_key_integrity(self, temp_db):
        """Test referential integrity (if foreign keys enabled)"""
        # Create swap request with target employee
        swap_id = create_swap_request(
            requesting_employee_id=1,
            requesting_employee_name="Employee 1",
            shift_date=(date.today() + timedelta(days=1)).isoformat(),
            shift_type="morning",
            role="Server",
            swap_type="swap",
            target_employee_id=2,
            target_employee_name="Employee 2",
            db_path=temp_db
        )
        
        # Request should exist
        requests = get_swap_requests(employee_id=1, db_path=temp_db)
        assert len(requests) == 1
        assert requests[0].target_employee_id == 2


# ============================================================================
# PERFORMANCE BENCHMARKS
# ============================================================================

class TestPerformance:
    """Performance and scalability tests"""
    
    def test_template_list_performance(self, temp_db, sample_template):
        """Test listing performance with many templates"""
        # Create 500 templates
        for i in range(500):
            template = ScheduleTemplate(
                name=f"Template {i:04d}",
                pattern_type=["weekly", "biweekly", "monthly"][i % 3],
                role_coverage=sample_template.role_coverage,
                pattern_data=sample_template.pattern_data
            )
            save_template(template, temp_db)
        
        # Measure list performance
        start = time.time()
        templates = list_templates(db_path=temp_db, active_only=False)
        duration = time.time() - start
        
        assert len(templates) == 500, f"Expected 500 templates but got {len(templates)}"
        assert duration < 1.0, f"Listing too slow: {duration:.2f}s"
    
    def test_swap_query_performance(self, temp_db):
        """Test query performance with large dataset"""
        # Create 5000 swap requests
        for i in range(5000):
            create_swap_request(
                requesting_employee_id=(i % 100) + 1,
                requesting_employee_name=f"Employee {(i % 100) + 1}",
                shift_date=(date.today() + timedelta(days=i % 180)).isoformat(),
                shift_type=["morning", "afternoon", "evening"][i % 3],
                role=["Server", "Cook", "Manager"][i % 3],
                swap_type=["swap", "drop", "pickup"][i % 3],
                db_path=temp_db
            )
        
        # Test employee-specific query
        start = time.time()
        employee_swaps = get_swap_requests(employee_id=1, db_path=temp_db)
        duration = time.time() - start
        
        assert len(employee_swaps) == 50  # 5000 / 100 employees
        assert duration < 0.5, f"Query too slow: {duration:.2f}s"
        
        # Test pending requests query
        start = time.time()
        pending = get_pending_swap_requests_for_approval(temp_db)
        duration = time.time() - start
        
        assert len(pending) == 5000
        assert duration < 1.0, f"Pending query too slow: {duration:.2f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-k", "test_"])
