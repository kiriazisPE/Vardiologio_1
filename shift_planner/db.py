# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
import json
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Tuple

from constants import DB_FILE

def _safe_json_loads(s: Optional[str], default):
    """
    Defensive JSON loader for legacy/malformed values.
    Returns `default` on any parse error.
    """
    if s is None:
        return default
    try:
        return json.loads(s)
    except Exception:
        return default

def _ensure_list(x) -> List[Any]:
    """Coerce values into a list. Scalars -> [scalar]; None -> []. Others -> []."""
    if isinstance(x, list):
        return x
    if x is None:
        return []
    if isinstance(x, (str, int, float, bool)):
        return [x]
    return []

def _ensure_dict(x) -> Dict[str, Any]:
    """Coerce values into a dict. Non-dicts -> {}."""
    return x if isinstance(x, dict) else {}

def _ensure_availability(x):
    """
    Availability historically stored as list OR dict.
    Keep either; otherwise normalize to empty list.
    """
    if isinstance(x, (list, dict)):
        return x
    return []


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
      - add schedule.role column if missing
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

        # Schedule (now includes role)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            shift TEXT NOT NULL,
            role TEXT DEFAULT NULL,
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
        cols_companies = [r[1] for r in conn.execute("PRAGMA table_info(companies)").fetchall()]
        if "active" not in cols_companies:
            conn.execute("ALTER TABLE companies ADD COLUMN active INTEGER DEFAULT 1")

        # Ensure 'role' exists on schedule (older DBs)
        cols_sched = [r[1] for r in conn.execute("PRAGMA table_info(schedule)").fetchall()]
        if "role" not in cols_sched:
            conn.execute("ALTER TABLE schedule ADD COLUMN role TEXT DEFAULT NULL")

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
        active_shifts = _ensure_list(_safe_json_loads(r["active_shifts"], []))
        roles = _ensure_list(_safe_json_loads(r["roles"], []))
        rules = _ensure_dict(_safe_json_loads(r["rules"], {}))
        role_settings = _ensure_dict(_safe_json_loads(r["role_settings"], {}))
        return {
            "id": r["id"],
            "name": r["name"],
            "active_shifts": active_shifts,
            "roles": roles,
            "rules": rules,
            "role_settings": role_settings,
            "work_model": r["work_model"] or "5ήμερο",
            "active": r["active"] if "active" in r.keys() else 1,
        }


def create_company(name: str) -> None:
    if not name or not str(name).strip():
        raise ValueError("Company name cannot be empty.")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO companies (name, active_shifts, roles, rules, role_settings, work_model, active) "
            "VALUES (?, '[]', '[]', '{}', '{}', '5ήμερο', 1)",
            (str(name).strip(),),
        )


def update_company(company_id: int, data: Dict[str, Any]) -> None:
    # Guard name NOT NULL and avoid clobbering with None
    with get_conn() as conn:
        current = conn.execute("SELECT name FROM companies WHERE id=?", (company_id,)).fetchone()
        if not current:
            raise ValueError("Company not found.")
        name_val = data.get("name", current["name"])
        if name_val is None:
            name_val = current["name"]
        name_val = str(name_val).strip()
        if not name_val:
            raise ValueError("Company name cannot be empty.")

        active_shifts = json.dumps(_ensure_list(data.get("active_shifts", [])), ensure_ascii=False)
        roles = json.dumps(_ensure_list(data.get("roles", [])), ensure_ascii=False)
        rules = json.dumps(_ensure_dict(data.get("rules", {})), ensure_ascii=False)
        role_settings = json.dumps(_ensure_dict(data.get("role_settings", {})), ensure_ascii=False)
        work_model = data.get("work_model", "5ήμερο")
        active = int(data.get("active", 1))

        conn.execute("""
            UPDATE companies
            SET active_shifts=?, roles=?, rules=?, role_settings=?, work_model=?, name=?, active=?
            WHERE id=?
        """, (active_shifts, roles, rules, role_settings, work_model, name_val, active, company_id))


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
            roles = _ensure_list(_safe_json_loads(r["roles"], []))
            availability = _ensure_availability(_safe_json_loads(r["availability"], []))
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
    availability = _ensure_availability(availability)
    if not name or not str(name).strip():
        raise ValueError("Employee name cannot be empty.")
    with get_conn() as conn:
        # Validate company exists
        comp = conn.execute("SELECT 1 FROM companies WHERE id=?", (company_id,)).fetchone()
        if not comp:
            raise ValueError("Company does not exist.")
        conn.execute("""
            INSERT INTO employees (company_id, name, roles, availability)
            VALUES (?,?,?,?)
        """, (company_id,
              str(name).strip(),
              json.dumps(roles_list, ensure_ascii=False),
              json.dumps(availability, ensure_ascii=False)))


def update_employee(employee_id: int, name: str, roles, availability) -> None:
    roles_list = _normalize_roles_for_store(roles)
    availability = _ensure_availability(availability)
    if not name or not str(name).strip():
        raise ValueError("Employee name cannot be empty.")
    with get_conn() as conn:
        conn.execute("""
            UPDATE employees
            SET name=?, roles=?, availability=?
            WHERE id=?
        """, (str(name).strip(),
              json.dumps(roles_list, ensure_ascii=False),
              json.dumps(availability, ensure_ascii=False),
              employee_id))


def delete_employee(employee_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM employees WHERE id=?", (employee_id,))


# ---------------- Schedule Functions ---------------- #
def add_schedule_entry(company_id: int, employee_id: int, date: str, shift: str, role: str | None = None) -> None:
    # Validate FK membership early for better UX
    with get_conn() as conn:
        emp = conn.execute("SELECT company_id FROM employees WHERE id=?", (employee_id,)).fetchone()
        if not emp:
            raise ValueError("Employee does not exist.")
        if emp["company_id"] != company_id:
            raise ValueError("Employee does not belong to the given company.")
        # Upsert instead of silent ignore: update role if row exists
        conn.execute("""
            INSERT INTO schedule (company_id, employee_id, date, shift, role)
            VALUES (?,?,?,?,?)
            ON CONFLICT(company_id, employee_id, date, shift) DO UPDATE SET
                role=excluded.role
        """, (company_id, employee_id, date, shift, role))


def get_schedule(company_id: int) -> List[Dict[str, Any]]:
    """Return all schedule entries for a company."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT s.id, s.date, s.shift, s.role,
                   e.name as employee_name, e.roles
            FROM schedule s
            JOIN employees e ON e.id = s.employee_id
            WHERE s.company_id=?
            ORDER BY s.date, e.name
        """, (company_id,)).fetchall()
        result: List[Dict[str, Any]] = []
        for r in rows:
            roles = _ensure_list(_safe_json_loads(r["roles"], []))
            result.append({
                "id": r["id"],
                "date": r["date"],
                "shift": r["shift"],
                "role": r["role"],
                "employee_name": r["employee_name"],
                "roles": roles,
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
            SELECT s.id, s.date, s.shift, s.role,
                   e.id as employee_id, e.name as employee_name, e.roles
            FROM schedule s
            JOIN employees e ON e.id = s.employee_id
            WHERE s.company_id=? AND s.date BETWEEN ? AND ?
            ORDER BY s.date, e.name
        """, (company_id, start_date, end_date)).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            roles = _ensure_list(_safe_json_loads(r["roles"], []))
            out.append({
                "id": r["id"],
                "date": r["date"],
                "shift": r["shift"],
                "role": r["role"],
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
    assignments: list of {employee_id, date (YYYY-MM-DD), shift, role?}
    Clears existing rows in [start_date, end_date] for that company, then inserts all.
    Now deduplicates input and upserts rows (no silent ignore).
    """
    # Normalize and deduplicate input first (last wins on duplicate keys)
    key = lambda a: (a["employee_id"], a["date"], a["shift"])
    dedup: Dict[Tuple[int, str, str], Dict[str, Any]] = {}
    for a in assignments or []:
        if not a.get("employee_id") or not a.get("date") or not a.get("shift"):
            # Skip malformed entries
            continue
        dedup[key(a)] = a  # last write wins

    with get_conn() as conn:
        # Clear the target window
        conn.execute("""
            DELETE FROM schedule
            WHERE company_id=? AND date BETWEEN ? AND ?
        """, (company_id, start_date, end_date))

        # Validate that employees exist & belong to company BEFORE inserting
        emp_company = {
            r["id"]: r["company_id"]
            for r in conn.execute("SELECT id, company_id FROM employees WHERE company_id=?", (company_id,)).fetchall()
        }

        rows = [
            (company_id, a["employee_id"], a["date"], a["shift"], a.get("role"))
            for a in dedup.values()
            if a["employee_id"] in emp_company and emp_company[a["employee_id"]] == company_id
        ]

        if rows:
            conn.executemany("""
                INSERT INTO schedule (company_id, employee_id, date, shift, role)
                VALUES (?,?,?,?,?)
                ON CONFLICT(company_id, employee_id, date, shift) DO UPDATE SET
                    role=excluded.role
            """, rows)


# ---------------- Shift Swap Functions ---------------- #
def create_swap_request(company_id: int, requester_id: int,
                        target_employee_id: int, date: str, shift: str) -> None:
    with get_conn() as conn:
        # Validate employees and membership
        req = conn.execute("SELECT id, company_id FROM employees WHERE id=?", (requester_id,)).fetchone()
        tgt = conn.execute("SELECT id, company_id FROM employees WHERE id=?", (target_employee_id,)).fetchone()
        if not req or not tgt:
            raise ValueError("Requester and target must be valid employees.")
        if req["company_id"] != company_id or tgt["company_id"] != company_id:
            raise ValueError("Both employees must belong to the specified company.")
        if requester_id == target_employee_id:
            raise ValueError("Requester and target cannot be the same employee.")
        # Ensure requester currently holds the shift being swapped
        has_assignment = conn.execute(
            "SELECT 1 FROM schedule WHERE company_id=? AND employee_id=? AND date=? AND shift=?",
            (company_id, requester_id, date, shift)
        ).fetchone()
        if not has_assignment:
            raise ValueError("Requester is not assigned to the given date/shift.")

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
        # Atomic, conflict-free swap in a single statement.
        # This avoids a transient duplicate (company_id, employee_id, date, shift) that would violate idx_schedule_unique.
        conn.execute("""
            UPDATE schedule
            SET employee_id = CASE
                WHEN employee_id = :requester THEN :target
                WHEN employee_id = :target THEN :requester
                ELSE employee_id
            END
            WHERE company_id = :company_id
              AND date = :date
              AND shift = :shift
              AND employee_id IN (:requester, :target)
        """, {
            "company_id": company_id,
            "date": date,
            "shift": shift,
            "requester": requester_id,
            "target": target_employee_id,
        })
