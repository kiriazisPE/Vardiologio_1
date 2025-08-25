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
                work_model TEXT DEFAULT '5ήμερο',
                active INTEGER DEFAULT 1
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

        # swap_requests (new/extended)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS swap_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                from_employee_id INTEGER NOT NULL,
                to_employee_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                shift_from TEXT,
                shift_to TEXT,
                shift TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                note TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
                FOREIGN KEY(from_employee_id) REFERENCES employees(id) ON DELETE CASCADE,
                FOREIGN KEY(to_employee_id) REFERENCES employees(id) ON DELETE CASCADE
            )
            """
        )

        # Backfill/alter for existing DBs
        try:
            conn.execute("ALTER TABLE companies ADD COLUMN active INTEGER DEFAULT 1;")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE schedule ADD COLUMN role TEXT;")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE swap_requests ADD COLUMN shift TEXT;")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE swap_requests ADD COLUMN note TEXT;")
        except sqlite3.OperationalError:
            pass

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


def bulk_save_week_schedule(company_id: int, start_date: str, end_date: str, entries: Iterable[Dict]) -> None:
    """Save a week's schedule transactionally over an inclusive date window.

    UI calls with 4 args: (company_id, start_date, end_date, entries).
    We delete existing rows for [start_date, end_date] and then insert the provided entries
    (ignoring any entry outside the window for safety).
    """
    entries = [e for e in entries if start_date <= e.get("date", "") <= end_date]
    if not entries:
        with get_conn() as conn:
            conn.execute("DELETE FROM schedule WHERE company_id=? AND date>=? AND date<=?", (company_id, start_date, end_date))
        return

    with get_conn() as conn:
        conn.execute("DELETE FROM schedule WHERE company_id=? AND date>=? AND date<=?", (company_id, start_date, end_date))
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

def create_swap_request(company_id: int, from_employee_id: int, to_employee_id: int, date: str, shift: str) -> int:
    """UI signature: (company_id, from_id, to_id, date, shift). Store a single shift.
    For backward compatibility we also populate shift_from/shift_to with the same value.
    """
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO swap_requests (company_id, from_employee_id, to_employee_id, date, shift, shift_from, shift_to, status)
            VALUES (?,?,?,?,?, ?, ?, 'pending')
            """,
            (company_id, from_employee_id, to_employee_id, date, shift, shift, shift),
        )
        return int(cur.lastrowid)


from typing import Optional, List, Dict

def list_swap_requests(company_id: int, status: Optional[str] = None) -> List[Dict]:
    """
    Return rows shaped for the UI, including names and normalized field names.
    Fields: id, date, shift, status, note, created_at, requester_id, target_employee_id, requester_name, target_name
    """
    with get_conn() as conn:
        base_sql = """
            SELECT sr.id,
                   sr.date,
                   COALESCE(sr.shift, sr.shift_from, sr.shift_to) AS shift,
                   sr.status,
                   sr.note,
                   sr.created_at,
                   sr.from_employee_id AS requester_id,
                   sr.to_employee_id   AS target_employee_id,
                   ef.name AS requester_name,
                   et.name AS target_name
            FROM swap_requests sr
            JOIN employees ef ON ef.id = sr.from_employee_id
            JOIN employees et ON et.id = sr.to_employee_id
            WHERE sr.company_id = ? {status_clause}
            ORDER BY sr.created_at DESC
        """
        if status:
            sql = base_sql.format(status_clause="AND sr.status = ?")
            rows = conn.execute(sql, (company_id, status)).fetchall()
        else:
            sql = base_sql.format(status_clause="")
            rows = conn.execute(sql, (company_id,)).fetchall()
        return [dict(r) for r in rows]


def update_swap_status(request_id: int, status: str, note: Optional[str] = None) -> None:
    """
    Update status (pending|approved|rejected|applied) and optional note.
    """
    if status not in {"pending", "approved", "rejected", "applied"}:
        raise ValueError("Invalid status")
    with get_conn() as conn:
        conn.execute(
            "UPDATE swap_requests SET status = ?, note = ? WHERE id = ?",
            (status, note, request_id),
        )


def apply_approved_swap(company_id: int, date: str, shift: str,
                        requester_id: int, target_id: int) -> bool:
    """
    UI signature: (company_id, date, shift, requester_id, target_id)

    Behavior: move the (date, shift) assignment from requester to target.
    If the target already has an assignment for the same (date, shift), we drop the duplicate
    before reassigning. Returns True if a change was applied.
    """
    with get_conn() as conn:
        # Find the requester's existing assignment for that date/shift
        row_req = conn.execute(
            "SELECT id FROM schedule WHERE company_id = ? AND employee_id = ? AND date = ? AND shift = ?",
            (company_id, requester_id, date, shift),
        ).fetchone()
        if not row_req:
            return False

        # Ensure the target has no duplicate assignment for that slot
        conn.execute(
            "DELETE FROM schedule WHERE company_id = ? AND employee_id = ? AND date = ? AND shift = ?",
            (company_id, target_id, date, shift),
        )

        # Reassign the schedule row to the target
        conn.execute(
            "UPDATE schedule SET employee_id = ? WHERE id = ?",
            (target_id, row_req["id"]),
        )

        # Mark matching swap requests as applied (covers shift/shift_from/shift_to)
        conn.execute(
            """
            UPDATE swap_requests
            SET status = 'applied'
            WHERE company_id = ?
              AND date = ?
              AND COALESCE(shift, shift_from, shift_to) = ?
              AND from_employee_id = ?
              AND to_employee_id   = ?
              AND status IN ('pending','approved')
            """,
            (company_id, date, shift, requester_id, target_id),
        )
        return True
