# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
import json
from contextlib import contextmanager
from typing import Optional, List, Dict, Any

from constants import DB_FILE


# ---------------- Connection Helper ---------------- #
@contextmanager
def get_conn():
    """
    Yields a SQLite connection with sane defaults:
    - Foreign keys ON
    - WAL journaling
    - Row factory -> sqlite3.Row
    """
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------- Database Init + Lightweight Migrations ---------------- #
def init_db():
    """
    Creates base tables if they do not exist.
    Also applies lightweight migrations for existing DBs:
      - add companies.active column if missing
      - enforce uniqueness on schedule via a unique index
      - helpful indexes for speed
    """
    with get_conn() as conn:
        # Companies
        conn.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            active_shifts TEXT DEFAULT '[]',
            roles TEXT DEFAULT '[]',
            rules TEXT DEFAULT '{}',
            role_settings TEXT DEFAULT '{}',
            work_model TEXT DEFAULT '5ήμερο',
            active INTEGER DEFAULT 1
        )
        """)

        # Employees
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

        # Schedule
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

        # Shift swap requests
        conn.execute("""
        CREATE TABLE IF NOT EXISTS shift_swaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            requester_id INTEGER NOT NULL,
            target_employee_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            shift TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', -- pending|approved|rejected
            manager_note TEXT DEFAULT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY(requester_id) REFERENCES employees(id) ON DELETE CASCADE,
            FOREIGN KEY(target_employee_id) REFERENCES employees(id) ON DELETE CASCADE
        )
        """)

        # ---------- Lightweight migrations ----------
        # Ensure 'active' exists on companies (older DBs)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(companies)").fetchall()]
        if "active" not in cols:
            conn.execute("ALTER TABLE companies ADD COLUMN active INTEGER DEFAULT 1")

        # Enforce uniqueness for schedule (older DBs may lack the constraint)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_schedule_unique
            ON schedule(company_id, employee_id, date, shift)
        """)

        # Helpful indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sched_company_date ON schedule(company_id, date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_swaps_company_status ON shift_swaps(company_id, status)")


# ---------------- Company Functions ---------------- #
def get_all_companies() -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT id, name FROM companies ORDER BY name").fetchall()
        return [{"id": r["id"], "name": r["name"]} for r in rows]


def get_company(company_id: int) -> Optional[Dict[str, Any]]:
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
            "active": r["active"] if "active" in r.keys() else 1,
        }


def create_company(name: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO companies (name, active_shifts, roles, rules, role_settings, work_model, active) "
            "VALUES (?, '[]', '[]', '{}', '{}', '5ήμερο', 1)",
            (name,),
        )


def update_company(company_id: int, data: Dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute("""
            UPDATE companies
            SET active_shifts=?, roles=?, rules=?, role_settings=?, work_model=?, name=?, active=?
            WHERE id=?
        """, (
            json.dumps(data.get("active_shifts", []), ensure_ascii=False),
            json.dumps(data.get("roles", []), ensure_ascii=False),
            json.dumps(data.get("rules", {}), ensure_ascii=False),
            json.dumps(data.get("role_settings", {}), ensure_ascii=False),
            data.get("work_model", "5ήμερο"),
            data.get("name"),
            int(data.get("active", 1)),
            company_id
        ))


# ---------------- Employee Functions ---------------- #
def _normalize_roles_for_store(roles) -> List[str]:
    """Accept string or list; return list for storage."""
    if isinstance(roles, str):
        return [roles] if roles else []
    return roles or []


def get_employees(company_id: int) -> List[Dict[str, Any]]:
    """
    Returns each employee as:
      {
        id, name,
        roles: [..],          # always list (normalized)
        role: str,            # convenience (first or "")
        availability: {...} or [...]
      }
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM employees WHERE company_id=? ORDER BY name", (company_id,)
        ).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            roles = json.loads(r["roles"] or "[]")
            if isinstance(roles, str):  # backward-compat (single role stored as string)
                roles = [roles] if roles else []
            availability = json.loads(r["availability"] or "[]")
            out.append({
                "id": r["id"],
                "name": r["name"],
                "roles": roles,
                "role": roles[0] if roles else "",
                "availability": availability,
            })
        return out


def add_employee(company_id: int, name: str, roles, availability) -> None:
    roles_list = _normalize_roles_for_store(roles)
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO employees (company_id, name, roles, availability)
            VALUES (?,?,?,?)
        """, (company_id,
              name,
              json.dumps(roles_list, ensure_ascii=False),
              json.dumps(availability, ensure_ascii=False)))


def update_employee(employee_id: int, name: str, roles, availability) -> None:
    roles_list = _normalize_roles_for_store(roles)
    with get_conn() as conn:
        conn.execute("""
            UPDATE employees
            SET name=?, roles=?, availability=?
            WHERE id=?
        """, (name,
              json.dumps(roles_list, ensure_ascii=False),
              json.dumps(availability, ensure_ascii=False),
              employee_id))


def delete_employee(employee_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM employees WHERE id=?", (employee_id,))


# ---------------- Schedule Functions ---------------- #
def add_schedule_entry(company_id: int, employee_id: int, date: str, shift: str) -> None:
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO schedule (company_id, employee_id, date, shift)
            VALUES (?,?,?,?)
        """, (company_id, employee_id, date, shift))


def get_schedule(company_id: int) -> List[Dict[str, Any]]:
    """Return all schedule entries for a company."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT s.id, s.date, s.shift,
                   e.name as employee_name, e.roles
            FROM schedule s
            JOIN employees e ON e.id = s.employee_id
            WHERE s.company_id=?
            ORDER BY s.date, e.name
        """, (company_id,)).fetchall()
        result: List[Dict[str, Any]] = []
        for r in rows:
            roles = json.loads(r["roles"] or "[]")
            result.append({
                "id": r["id"],
                "date": r["date"],
                "shift": r["shift"],
                "employee_name": r["employee_name"],
                "roles": roles if isinstance(roles, list) else ([roles] if roles else []),
            })
        return result


def clear_schedule(company_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM schedule WHERE company_id=?", (company_id,))


# ---- Week-range helpers (for visual builder) ---- #
def clear_schedule_range(company_id: int, start_date: str, end_date: str) -> None:
    with get_conn() as conn:
        conn.execute("""
            DELETE FROM schedule
            WHERE company_id=? AND date BETWEEN ? AND ?
        """, (company_id, start_date, end_date))


def get_schedule_range(company_id: int, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT s.id, s.date, s.shift, e.id as employee_id, e.name as employee_name, e.roles
            FROM schedule s
            JOIN employees e ON e.id = s.employee_id
            WHERE s.company_id=? AND s.date BETWEEN ? AND ?
            ORDER BY s.date, e.name
        """, (company_id, start_date, end_date)).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            roles = json.loads(r["roles"] or "[]")
            if isinstance(roles, str):
                roles = [roles] if roles else []
            out.append({
                "id": r["id"],
                "date": r["date"],
                "shift": r["shift"],
                "employee_id": r["employee_id"],
                "employee_name": r["employee_name"],
                "roles": roles,
            })
        return out


def get_employee_id_by_name(company_id: int, name: str) -> Optional[int]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM employees WHERE company_id=? AND name=?",
            (company_id, name)
        ).fetchone()
        return row["id"] if row else None


def bulk_save_week_schedule(company_id: int, assignments: List[Dict[str, Any]],
                            start_date: str, end_date: str) -> None:
    """
    assignments: list of {employee_id, date (YYYY-MM-DD), shift}
    Clears existing rows in [start_date, end_date] for that company, then inserts all.
    """
    if not assignments:
        # Still clear the week to allow "blanking" the schedule.
        clear_schedule_range(company_id, start_date, end_date)
        return

    with get_conn() as conn:
        conn.execute("""
            DELETE FROM schedule
            WHERE company_id=? AND date BETWEEN ? AND ?
        """, (company_id, start_date, end_date))
        conn.executemany("""
            INSERT OR IGNORE INTO schedule (company_id, employee_id, date, shift)
            VALUES (?,?,?,?)
        """, [(company_id, a["employee_id"], a["date"], a["shift"]) for a in assignments])


# ---------------- Shift Swap Functions ---------------- #
def create_swap_request(company_id: int, requester_id: int,
                        target_employee_id: int, date: str, shift: str) -> None:
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO shift_swaps (company_id, requester_id, target_employee_id, date, shift, status)
            VALUES (?,?,?,?,?,'pending')
        """, (company_id, requester_id, target_employee_id, date, shift))


def list_swap_requests(company_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
    q = """
        SELECT ss.*, r.name as requester_name, t.name as target_name
        FROM shift_swaps ss
        JOIN employees r ON r.id = ss.requester_id
        JOIN employees t ON t.id = ss.target_employee_id
        WHERE ss.company_id=?
    """
    args: List[Any] = [company_id]
    if status:
        q += " AND ss.status=?"
        args.append(status)
    with get_conn() as conn:
        return [dict(row) for row in conn.execute(q, args).fetchall()]


def update_swap_status(request_id: int, status: str, manager_note: Optional[str] = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE shift_swaps SET status=?, manager_note=? WHERE id=?",
            (status, manager_note, request_id)
        )


def apply_approved_swap(company_id: int, date: str, shift: str,
                        requester_id: int, target_employee_id: int) -> None:
    """
    Swap assignment of (date, shift) from requester -> target.
    If target had the same (rare), swap back to requester.
    """
    with get_conn() as conn:
        # requester → target
        conn.execute("""
            UPDATE schedule
            SET employee_id=?
            WHERE company_id=? AND employee_id=? AND date=? AND shift=?
        """, (target_employee_id, company_id, requester_id, date, shift))
        # target → requester (if any)
        conn.execute("""
            UPDATE schedule
            SET employee_id=?
            WHERE company_id=? AND employee_id=? AND date=? AND shift=?
        """, (requester_id, company_id, target_employee_id, date, shift))
