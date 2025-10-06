#!/usr/bin/env python3
"""
Realistic Dummy Data Generator for Shift Plus Pro
Creates comprehensive employee database with realistic schedules and business settings
"""

import sqlite3
import json
import random
from datetime import datetime, date, timedelta
from typing import List, Dict
import sys
import os

# Add current directory to path to import our modules
sys.path.append('.')

try:
    from shift_plus_core import get_conn
    from common.business_settings import BusinessSettings, RoleSettings, ShiftSettings
except ImportError as e:
    print(f"Warning: Could not import modules: {e}")
    print("Make sure you're running this from the project directory")

class RealisticDataGenerator:
    """Generate realistic dummy data for the scheduling system"""
    
    def __init__(self, db_path="shift_maker.sqlite3"):
        self.db_path = db_path
        
        # Realistic employee names
        self.first_names = [
            "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia", "Mason", "Isabella", "William",
            "Mia", "James", "Charlotte", "Benjamin", "Amelia", "Lucas", "Harper", "Henry", "Evelyn", "Alexander",
            "Abigail", "Michael", "Emily", "Daniel", "Elizabeth", "Matthew", "Sofia", "Jackson", "Avery", "Sebastian",
            "Ella", "David", "Madison", "Joseph", "Scarlett", "Samuel", "Victoria", "Carter", "Aria", "Owen",
            "Grace", "Luke", "Chloe", "Gabriel", "Camila", "Anthony", "Penelope", "Isaac", "Riley", "Grayson",
            "Layla", "Jack", "Lillian", "Julian", "Nora", "Levi", "Zoey", "Christopher", "Mila", "Joshua",
            "Aubrey", "Andrew", "Hannah", "Lincoln", "Lily", "Mateo", "Addison", "Ryan", "Eleanor", "Jaxon"
        ]
        
        self.last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
            "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
            "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
            "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
            "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts"
        ]
        
        # Business types with realistic role structures
        self.business_templates = {
            "restaurant": {
                "name": "Bella Vista Restaurant",
                "roles": ["Manager", "Chef", "Line Cook", "Server", "Host", "Dishwasher", "Bartender"],
                "coverage": {
                    "Manager": {"day": 1, "night": 1},
                    "Chef": {"day": 2, "night": 1}, 
                    "Line Cook": {"day": 3, "night": 2},
                    "Server": {"day": 4, "night": 3},
                    "Host": {"day": 1, "night": 1},
                    "Dishwasher": {"day": 2, "night": 1},
                    "Bartender": {"day": 1, "night": 2}
                }
            },
            "retail": {
                "name": "TechHub Electronics Store",
                "roles": ["Store Manager", "Assistant Manager", "Sales Associate", "Cashier", "Stock Clerk", "Customer Service"],
                "coverage": {
                    "Store Manager": {"day": 1, "night": 0},
                    "Assistant Manager": {"day": 1, "night": 1},
                    "Sales Associate": {"day": 3, "night": 2},
                    "Cashier": {"day": 2, "night": 1},
                    "Stock Clerk": {"day": 2, "night": 1},
                    "Customer Service": {"day": 1, "night": 1}
                }
            },
            "healthcare": {
                "name": "Sunrise Medical Center",
                "roles": ["Nurse Manager", "Registered Nurse", "LPN", "CNA", "Medical Tech", "Receptionist"],
                "coverage": {
                    "Nurse Manager": {"day": 1, "night": 1},
                    "Registered Nurse": {"day": 4, "night": 3},
                    "LPN": {"day": 2, "night": 2},
                    "CNA": {"day": 6, "night": 4},
                    "Medical Tech": {"day": 2, "night": 1},
                    "Receptionist": {"day": 2, "night": 1}
                }
            },
            "hotel": {
                "name": "Grand Plaza Hotel",
                "roles": ["General Manager", "Front Desk Manager", "Front Desk Agent", "Housekeeper", "Maintenance", "Concierge", "Security"],
                "coverage": {
                    "General Manager": {"day": 1, "night": 0},
                    "Front Desk Manager": {"day": 1, "night": 1},
                    "Front Desk Agent": {"day": 2, "night": 1},
                    "Housekeeper": {"day": 4, "night": 1},
                    "Maintenance": {"day": 2, "night": 1},
                    "Concierge": {"day": 1, "night": 0},
                    "Security": {"day": 1, "night": 2}
                }
            }
        }
        
    def create_realistic_employees(self, business_type="restaurant", num_employees=50):
        """Create realistic employee database"""
        template = self.business_templates[business_type]
        roles = template["roles"]
        
        employees = []
        
        for i in range(num_employees):
            # Generate realistic employee data
            first_name = random.choice(self.first_names)
            last_name = random.choice(self.last_names)
            name = f"{first_name} {last_name}"
            
            # Assign roles with realistic distribution
            role = random.choices(
                roles,
                weights=[3, 2, 4, 6, 4, 3, 2] if business_type == "restaurant" else [1]*len(roles),
                k=1
            )[0]
            
            # Realistic availability patterns
            availability_patterns = [
                ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],  # Weekday worker
                ["Friday", "Saturday", "Sunday"],  # Weekend worker
                ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],  # Full availability
                ["Monday", "Wednesday", "Friday", "Saturday", "Sunday"],  # Mixed schedule
                ["Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],  # Mid-week to weekend
                ["Saturday", "Sunday", "Monday", "Tuesday"],  # Weekend + start of week
            ]
            
            days_available = random.choice(availability_patterns)
            
            # Experience and importance based on role hierarchy
            if role in ["Manager", "General Manager", "Store Manager", "Nurse Manager", "Front Desk Manager"]:
                experience = random.randint(24, 120)  # 2-10 years
                importance = random.randint(8, 10)
                hourly_wage = random.randint(25, 45)
            elif role in ["Assistant Manager", "Chef", "Registered Nurse"]:
                experience = random.randint(12, 60)  # 1-5 years
                importance = random.randint(6, 9)
                hourly_wage = random.randint(20, 35)
            else:  # Entry level roles
                experience = random.randint(0, 24)  # 0-2 years
                importance = random.randint(3, 7)
                hourly_wage = random.randint(15, 25)
            
            # Realistic constraints
            max_hours = random.choice([20, 25, 30, 35, 40])  # Part-time to full-time
            
            # Preferred shift based on role and availability
            if role in ["Manager", "General Manager", "Store Manager"]:
                preferred_shift = "day"
            elif "Server" in role or "Bartender" in role:
                preferred_shift = random.choice(["day", "night"])
            else:
                preferred_shift = random.choice(["day", "night", "either"])
            
            employee = {
                "name": name,
                "role": role,
                "preferred_shift": preferred_shift,
                "days_available": json.dumps(days_available),
                "max_hours_per_week": max_hours,
                "hourly_wage": hourly_wage,
                "experience_months": experience,
                "importance": importance,
                "email": f"{first_name.lower()}.{last_name.lower()}@{template['name'].lower().replace(' ', '')}.com",
                "phone": f"({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}",
                "hire_date": (datetime.now() - timedelta(days=random.randint(30, 1095))).date().isoformat(),
                "notes": self.generate_realistic_notes(role, experience)
            }
            
            employees.append(employee)
            
        return employees, template
    
    def generate_realistic_notes(self, role, experience_months):
        """Generate realistic employee notes"""
        notes_templates = {
            "high_exp": [
                "Excellent leadership skills, mentors new employees",
                "Highly reliable, never missed a shift",
                "Customer service excellence, handles difficult situations well",
                "Cross-trained in multiple departments",
                "Potential for promotion to management"
            ],
            "medium_exp": [
                "Good team player, works well with others",
                "Punctual and professional",
                "Learning quickly, shows initiative",
                "Handles busy periods well",
                "Good communication skills"
            ],
            "low_exp": [
                "New hire, still in training period",
                "Enthusiastic and eager to learn",
                "Needs supervision during busy periods",
                "Good attitude, fits well with team culture",
                "Recently completed certification program"
            ]
        }
        
        if experience_months > 24:
            category = "high_exp"
        elif experience_months > 6:
            category = "medium_exp"
        else:
            category = "low_exp"
            
        return random.choice(notes_templates[category])
    
    def create_business_settings(self, business_type="restaurant"):
        """Create realistic business settings"""
        template = self.business_templates[business_type]
        
        # Create role settings
        role_settings = []
        for role, coverage in template["coverage"].items():
            role_setting = RoleSettings(
                role=role,
                day_required=coverage["day"],
                night_required=coverage["night"],
                priority=1 if "Manager" in role else 2,
                min_experience_months=12 if "Manager" in role else 0,
                max_consecutive_shifts=5,
                min_rest_between_shifts=8.0
            )
            role_settings.append(role_setting)
        
        # Create shift settings
        shift_settings = [
            ShiftSettings(
                shift_type="day",
                start_hour=8,
                duration_hours=8.0,
                break_duration_minutes=30
            ),
            ShiftSettings(
                shift_type="night", 
                start_hour=16,
                duration_hours=8.0,
                break_duration_minutes=30
            )
        ]
        
        # Create business settings
        business_settings = BusinessSettings(
            business_name=template["name"],
            planning_start=date.today(),
            planning_days=14,
            roles_coverage=template["coverage"],
            default_shift_length=8.0,
            roles_settings=role_settings,
            shift_settings=shift_settings,
            business_hours={
                "Monday": {"open": 8, "close": 22},
                "Tuesday": {"open": 8, "close": 22},
                "Wednesday": {"open": 8, "close": 22},
                "Thursday": {"open": 8, "close": 22},
                "Friday": {"open": 8, "close": 23},
                "Saturday": {"open": 9, "close": 23},
                "Sunday": {"open": 9, "close": 21}
            },
            overtime_threshold=40.0,
            compliance_rules={
                "max_consecutive_days": 6,
                "min_rest_hours": 8,
                "max_daily_hours": 12,
                "require_breaks": True
            }
        )
        
        return business_settings
    
    def create_unavailability_records(self, num_employees, num_records=20):
        """Create realistic unavailability records"""
        unavailability_types = [
            ("Vacation", 5, 14),  # 5-14 days
            ("Sick Leave", 1, 3),  # 1-3 days
            ("Personal Day", 1, 1),  # 1 day
            ("Medical Appointment", 1, 1),  # Half day
            ("Family Emergency", 1, 2),  # 1-2 days
            ("Training", 1, 3),  # 1-3 days
            ("Conference", 2, 4),  # 2-4 days
        ]
        
        records = []
        base_date = datetime.now().date()
        
        for _ in range(num_records):
            employee_id = random.randint(1, num_employees)
            reason, min_days, max_days = random.choice(unavailability_types)
            duration = random.randint(min_days, max_days)
            
            # Random date within next 60 days
            start_offset = random.randint(1, 60)
            start_date = base_date + timedelta(days=start_offset)
            end_date = start_date + timedelta(days=duration - 1)
            
            record = {
                "employee_id": employee_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "reason": reason,
                "approved": True,
                "notes": f"Approved {reason.lower()} request"
            }
            
            records.append(record)
            
        return records
    
    def populate_database(self, business_type="restaurant", num_employees=50):
        """Populate database with realistic data"""
        print(f"🚀 Generating realistic data for {business_type} business...")
        print(f"📊 Creating {num_employees} employees with comprehensive data")
        
        # Create connection
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Clear existing data
        print("🧹 Clearing existing data...")
        cursor.execute("DELETE FROM employees")
        cursor.execute("DELETE FROM employee_unavailability") 
        cursor.execute("DELETE FROM schedules")
        cursor.execute("DELETE FROM business_settings")
        
        # Create employees
        print("👥 Creating realistic employees...")
        employees, template = self.create_realistic_employees(business_type, num_employees)
        
        for emp in employees:
            cursor.execute("""
                INSERT INTO employees (name, role, preferred_shift, days_available, max_hours_per_week, min_hours_per_week)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                emp["name"], emp["role"], emp["preferred_shift"], emp["days_available"], 
                emp["max_hours_per_week"], max(8, emp["max_hours_per_week"] - 10)
            ))
        
        # Create basic business settings (simplified)
        print("⚙️ Setting up business configuration...")
        basic_settings = {
            "business_name": template["name"],
            "planning_start": (datetime.now().date() + timedelta(days=1)).isoformat(),
            "planning_days": 14,
            "roles_coverage": template["coverage"],
            "default_shift_length": 8.0
        }
        
        settings_json = json.dumps(basic_settings)
        cursor.execute("INSERT INTO business_settings (json) VALUES (?)", (settings_json,))
        
        # Create unavailability records
        print("📅 Adding realistic unavailability records...")
        unavailability_records = self.create_unavailability_records(num_employees, 25)
        
        for record in unavailability_records:
            cursor.execute("""
                INSERT INTO employee_unavailability (employee_id, start_date, end_date, reason)
                VALUES (?, ?, ?, ?)
            """, (
                record["employee_id"], record["start_date"], record["end_date"],
                record["reason"]
            ))
        
        conn.commit()
        conn.close()
        
        # Print summary
        print("\n✅ REALISTIC DATA GENERATION COMPLETE!")
        print("=" * 50)
        print(f"🏢 Business: {template['name']}")
        print(f"👥 Employees: {num_employees}")
        print(f"🔧 Roles: {len(template['roles'])}")
        print(f"📋 Unavailability records: {len(unavailability_records)}")
        print(f"📊 Business type: {business_type.title()}")
        print("\n🎯 Your app now has realistic data for comprehensive testing!")
        
        return {
            "employees": len(employees),
            "business_name": template["name"],
            "roles": template["roles"],
            "unavailability_records": len(unavailability_records)
        }

def main():
    """Main function to generate realistic data"""
    print("🎯 SHIFT PLUS PRO - REALISTIC DATA GENERATOR")
    print("=" * 50)
    
    generator = RealisticDataGenerator()
    
    # Let user choose business type
    business_types = list(generator.business_templates.keys())
    
    print("Available business types:")
    for i, btype in enumerate(business_types, 1):
        template = generator.business_templates[btype]
        print(f"{i}. {btype.title()} - {template['name']} ({len(template['roles'])} roles)")
    
    try:
        choice = input(f"\nSelect business type (1-{len(business_types)}) [1]: ").strip()
        if not choice:
            choice = "1"
        
        business_type = business_types[int(choice) - 1]
        
        num_employees = input("Number of employees (50): ").strip()
        if not num_employees:
            num_employees = 50
        else:
            num_employees = int(num_employees)
            
    except (ValueError, IndexError):
        print("Invalid selection, using default (restaurant, 50 employees)")
        business_type = "restaurant"
        num_employees = 50
    
    # Generate data
    result = generator.populate_database(business_type, num_employees)
    
    print(f"\n🚀 Ready to test your AI scheduling system with realistic data!")
    print(f"💡 Try generating schedules to see the AI in action!")

if __name__ == "__main__":
    main()