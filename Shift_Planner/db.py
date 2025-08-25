# -*- coding: utf-8 -*-
import sqlite3
import json
from contextlib import contextmanager
from typing import Iterable, List, Dict, Optional, Tuple
from constants import DB_FILE

# -----------------------------
# Connection & pragmas
# -----------------------------
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

# -----------------------------
# Schema helpers (idempotent)
# -----------------------------

def _table_info(conn: sqlite3.Connection, table: str) -> List[sqlite3.Row]:
    return conn.execute(f"PRAGMA table_info({table});").fetchall()


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(r[1] == column for r in _table_info(conn, table))


def init_db():
    """Create tables if missing and ensure new columns exist (idempotent)."""
    with get_conn() as conn:
        # companies
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                active_shifts TEXT DEFAULT '[]',
                roles TEXT DEFAULT '[]',
                rules TEXT DEFAULT '{}',
                role_settings TEXT DEFAULT '{}',
                work_model TEXT DEFAULT '5ήμερο'
            )
            """
        )
        # employees
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                roles TEXT DEFAULT '[]',
                availability TEXT DEFAULT '[]',
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
            )
            """
        )
        # schedule (add assignment-level role)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                shift TEXT NOT NULL,
                role TEXT,
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
                FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE
            )
            """
        )

        # Backfill new columns for existing DBs
        if not _has_column(conn, "companies", "active"):
            conn.execute("ALTER TABLE companies ADD COLUMN active INTEGER DEFAULT 1;")
        if not _has_column(conn, "schedule", "role"):
            conn.execute("ALTER TABLE schedule ADD COLUMN role TEXT;")

        # Swap requests table used by the UI
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS swap_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                from_employee_id INTEGER NOT NULL,
                to_employee_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                shift_from TEXT NOT NULL,
                shift_to TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
                FOREIGN KEY(from_employee_id) REFERENCES employees(id) ON DELETE CASCADE,
                FOREIGN KEY(to_employee_id) REFERENCES employees(id) ON DELETE CASCADE
            )
            """
        )

# -----------------------------
# Companies
# -----------------------------

def get_all_companies() -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, COALESCE(active,1) AS active FROM companies ORDER BY name"
        ).fetchall()
        return [{"id": r["id"], "name": r["name"], "active": r["active"]} for r in rows]


def get_company(company_id: int) -> Optional[Dict]:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
        if not r:
            return None
        return {
            "id": r["id"],
            "name": r["name"],
            "active": r["active"] if "active" in r.keys() else 1,
            "active_shifts": json.loads(r["active_shifts"] or "[]"),
            "roles": json.loads(r["roles"] or "[]"),
            "rules": json.loads(r["rules"] or "{}"),
            "role_settings": json.loads(r["role_settings"] or "{}"),
            "work_model": r["work_model"] or "5ήμερο",
        }


def create_company(name: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO companies (name, active_shifts, roles, rules, role_settings, work_model, active)
            VALUES (?, '[]', '[]', '{}', '{}', '5ήμερο', 1)
            """,
            (name,),
        )


def update_company(company_id: int, data: Dict) -> None:
    with get_conn() as conn:
        # Make sure "active" persists
        active_val = int(data.get("active", 1))
        conn.execute(
            """
            UPDATE companies
            SET active_shifts=?, roles=?, rules=?, role_settings=?, work_model=?, name=?, active=?
            WHERE id=?
            """,
            (
                json.dumps(data.get("active_shifts", []), ensure_ascii=False),
                json.dumps(data.get("roles", []), ensure_ascii=False),
                json.dumps(data.get("rules", {}), ensure_ascii=False),
                json.dumps(data.get("role_settings", {}), ensure_ascii=False),
                data.get("work_model", "5ήμερο"),
                data.get("name"),
                active_val,
                company_id,
            ),
        )

# -----------------------------
# Employees
# -----------------------------

def get_employees(company_id: int) -> List[Dict]:
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


def add_employee(company_id: int, name: str, roles: List[str], availability: List[str]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO employees (company_id, name, roles, availability)
            VALUES (?,?,?,?)
            """,
            (
                company_id,
                name,
                json.dumps(roles, ensure_ascii=False),
                json.dumps(availability, ensure_ascii=False),
            ),
        )


def update_employee(employee_id: int, name: str, roles: List[str], availability: List[str]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE employees
            SET name=?, roles=?, availability=?
            WHERE id=?
            """,
            (name, json.dumps(roles, ensure_ascii=False), json.dumps(availability, ensure_ascii=False), employee_id),
        )


def delete_employee(employee_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM employees WHERE id=?", (employee_id,))


def get_employee_id_by_name(company_id: int, name: str) -> Optional[int]:
    with get_conn() as conn:
        r = conn.execute(
            "SELECT id FROM employees WHERE company_id=? AND name=?",
            (company_id, name),
        ).fetchone()
        return int(r["id"]) if r else None

# -----------------------------
# Schedule (assignment-level role)
# -----------------------------

def add_schedule_entry(company_id: int, employee_id: int, date: str, shift: str, role: Optional[str] = None) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO schedule (company_id, employee_id, date, shift, role)
            VALUES (?,?,?,?,?)
            """,
            (company_id, employee_id, date, shift, role),
        )


def get_schedule(company_id: int) -> List[Dict]:
    """Return schedule rows with the *assignment-level* role.
    The UI expects a single role string per row, not the employee's roles list.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.date, s.shift, s.role,
                   e.id AS employee_id, e.name AS employee_name
            FROM schedule s
            JOIN employees e ON e.id = s.employee_id
            WHERE s.company_id=?
            ORDER BY s.date, e.name
            """,
            (company_id,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "date": r["date"],
                "shift": r["shift"],
                "role": r["role"],
                "employee_id": r["employee_id"],
                "employee_name": r["employee_name"],
            }
            for r in rows
        ]


def get_schedule_range(company_id: int, start_date: str, end_date: str) -> List[Dict]:
    """Inclusive date range [start_date, end_date]."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.date, s.shift, s.role,
                   e.id AS employee_id, e.name AS employee_name
            FROM schedule s
            JOIN employees e ON e.id = s.employee_id
            WHERE s.company_id=? AND s.date>=? AND s.date<=?
            ORDER BY s.date, e.name
            """,
            (company_id, start_date, end_date),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "date": r["date"],
                "shift": r["shift"],
                "role": r["role"],
                "employee_id": r["employee_id"],
                "employee_name": r["employee_name"],
            }
            for r in rows
        ]


def bulk_save_week_schedule(company_id: int, entries: Iterable[Dict]) -> None:
    """Save a week's schedule transactionally.

    entries: iterable of dicts with keys {date, employee_id, shift, role}.
    Strategy: delete any existing rows for (company_id, date) in the set of dates provided,
    then insert the provided rows.
    """
    entries = list(entries)
    if not entries:
        return

    dates = sorted({e["date"] for e in entries})
    with get_conn() as conn:
        for d in dates:
            conn.execute("DELETE FROM schedule WHERE company_id=? AND date=?", (company_id, d))
        conn.executemany(
            """
            INSERT INTO schedule (company_id, employee_id, date, shift, role)
            VALUES (?,?,?,?,?)
            """,
            [
                (
                    company_id,
                    int(e["employee_id"]),
                    e["date"],
                    e["shift"],
                    e.get("role"),
                )
                for e in entries
            ],
        )


def clear_schedule(company_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM schedule WHERE company_id=?", (company_id,))

# -----------------------------
# Swap Requests API
# -----------------------------

def create_swap_request(
    company_id: int,
    from_employee_id: int,
    to_employee_id: int,
    date: str,
    shift_from: str,
    shift_to: str,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO swap_requests (company_id, from_employee_id, to_employee_id, date, shift_from, shift_to, status)
            VALUES (?,?,?,?,?,?, 'pending')
            """,
            (company_id, from_employee_id, to_employee_id, date, shift_from, shift_to),
        )
        return int(cur.lastrowid)


def list_swap_requests(company_id: int, status: Optional[str] = None) -> List[Dict]:
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM swap_requests WHERE company_id=? AND status=? ORDER BY created_at DESC",
                (company_id, status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM swap_requests WHERE company_id=? ORDER BY created_at DESC",
                (company_id,),
            ).fetchall()
        return [dict(r) for r in rows]


def update_swap_status(request_id: int, status: str) -> None:
    if status not in {"pending", "approved", "rejected", "applied"}:
        raise ValueError("Invalid status")
    with get_conn() as conn:
        conn.execute("UPDATE swap_requests SET status=? WHERE id=?", (status, request_id))


def apply_approved_swap(request_id: int) -> bool:
    """Apply an approved swap by exchanging shifts in the schedule.

    Returns True if rows were updated, False otherwise.
    """
    with get_conn() as conn:
        req = conn.execute(
            "SELECT * FROM swap_requests WHERE id=?", (request_id,)
        ).fetchone()
        if not req:
            return False
        if req["status"] != "approved":
            return False

        company_id = req["company_id"]
        date = req["date"]
        from_id = req["from_employee_id"]
        to_id = req["to_employee_id"]
        shift_from = req["shift_from"]
        shift_to = req["shift_to"]

        # Find the current schedule rows
        row_from = conn.execute(
            """
            SELECT * FROM schedule WHERE company_id=? AND employee_id=? AND date=? AND shift=?
            """,
            (company_id, from_id, date, shift_from),
        ).fetchone()
        row_to = conn.execute(
            """
            SELECT * FROM schedule WHERE company_id=? AND employee_id=? AND date=? AND shift=?
            """,
            (company_id, to_id, date, shift_to),
        ).fetchone()

        if not row_from or not row_to:
            return False

        # Swap: update the shifts (and keep roles with the assignment)
        conn.execute(
            "UPDATE schedule SET employee_id=? WHERE id=?",
            (to_id, row_from["id"]),
        )
        conn.execute(
            "UPDATE schedule SET employee_id=? WHERE id=?",
            (from_id, row_to["id"]),
        )
        conn.execute(
            "UPDATE swap_requests SET status='applied' WHERE id=?",
            (request_id,),
        )
        return True
