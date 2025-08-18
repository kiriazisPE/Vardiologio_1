# -*- coding: utf-8 -*-
import sqlite3
import json
from contextlib import contextmanager
from constants import DB_FILE

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            active_shifts TEXT DEFAULT '[]',
            roles TEXT DEFAULT '[]',
            rules TEXT DEFAULT '{}',
            role_settings TEXT DEFAULT '{}',
            work_model TEXT DEFAULT '5ήμερο'
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            roles TEXT DEFAULT '[]',
            availability TEXT DEFAULT '[]',
            FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            shift TEXT NOT NULL,
            FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE
        )
        """)

def get_all_companies():
    with get_conn() as conn:
        rows = conn.execute("SELECT id, name FROM companies ORDER BY name").fetchall()
        return [{"id": r["id"], "name": r["name"]} for r in rows]

def get_company(company_id: int):
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
        if not r:
            return None
        return {
            "id": r["id"],
            "name": r["name"],
            "active_shifts": json.loads(r["active_shifts"] or "[]"),
            "roles": json.loads(r["roles"] or "[]"),
            "rules": json.loads(r["rules"] or "{}"),
            "role_settings": json.loads(r["role_settings"] or "{}"),
            "work_model": r["work_model"] or "5ήμερο",
        }

def create_company(name: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO companies (name, active_shifts, roles, rules, role_settings, work_model) "
            "VALUES (?, '[]', '[]', '{}', '{}', '5ήμερο')",
            (name,),
        )

def update_company(company_id: int, data: dict):
    with get_conn() as conn:
        conn.execute("""
            UPDATE companies
            SET active_shifts=?, roles=?, rules=?, role_settings=?, work_model=?, name=?
            WHERE id=?
        """, (
            json.dumps(data.get("active_shifts", []), ensure_ascii=False),
            json.dumps(data.get("roles", []), ensure_ascii=False),
            json.dumps(data.get("rules", {}), ensure_ascii=False),
            json.dumps(data.get("role_settings", {}), ensure_ascii=False),
            data.get("work_model", "5ήμερο"),
            data.get("name"),
            company_id
        ))

def get_employees(company_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM employees WHERE company_id=? ORDER BY name", (company_id,)
        ).fetchall()
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "roles": json.loads(r["roles"] or "[]"),
                "availability": json.loads(r["availability"] or "[]"),
            }
            for r in rows
        ]

def add_employee(company_id: int, name: str, roles: list, availability: list):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO employees (company_id, name, roles, availability)
            VALUES (?,?,?,?)
        """, (company_id, name, json.dumps(roles, ensure_ascii=False), json.dumps(availability, ensure_ascii=False)))

def update_employee(employee_id: int, name: str, roles: list, availability: list):
    with get_conn() as conn:
        conn.execute("""
            UPDATE employees
            SET name=?, roles=?, availability=?
            WHERE id=?
        """, (name, json.dumps(roles, ensure_ascii=False), json.dumps(availability, ensure_ascii=False), employee_id))

def delete_employee(employee_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM employees WHERE id=?", (employee_id,))

def add_schedule_entry(company_id: int, employee_id: int, date: str, shift: str):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO schedule (company_id, employee_id, date, shift)
            VALUES (?,?,?,?)
        """, (company_id, employee_id, date, shift))

def get_schedule(company_id: int):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT s.id, s.date, s.shift,
                   e.name as employee_name, e.roles
            FROM schedule s
            JOIN employees e ON e.id = s.employee_id
            WHERE s.company_id=?
            ORDER BY s.date, e.name
        """, (company_id,)).fetchall()
        result = []
        for r in rows:
            roles = json.loads(r["roles"] or "[]")
            result.append({
                "id": r["id"],
                "date": r["date"],
                "shift": r["shift"],
                "employee_name": r["employee_name"],
                "roles": roles
            })
        return result

def clear_schedule(company_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM schedule WHERE company_id=?", (company_id,))
