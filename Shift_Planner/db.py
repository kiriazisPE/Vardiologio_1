# -*- coding: utf-8 -*-
"""
SQLite data layer for the scheduling app.

Key cleanups & compatibility notes:
- Deterministic trigger installation: we now check sqlite_master for trigger presence
  before attempting CREATE TRIGGER (SQLite lacks IF NOT EXISTS for triggers).
- create_company(...) now accepts either a simple name (str) *or* a dict with
  fields (name, active_shifts, roles, rules, role_settings, work_model, active),
  so calls from UI that pass a dict won't fail. Returns newly created company id.
- Swap API param names are normalized: functions accept both the DB-facing
  from_employee_id/to_employee_id and the UI-facing requester_id/target_employee_id.
  This keeps UI introspection happy without breaking existing callers.
- Robust date normalization via _normalize_iso_date_or_raise for all date inputs.
"""
import sqlite3
import json
import re
from datetime import date as _date
from contextlib import contextmanager
from typing import Iterable, List, Dict, Optional, Union, Tuple
from constants import DB_FILE

# -----------------------------
# Utilities (date normalization & checks)
# -----------------------------
_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def _normalize_iso_date_or_raise(s: str) -> str:
    """Return YYYY-MM-DD if valid ISO date; raise ValueError otherwise.
    Accepts only YYYY-MM-DD (strict, zero-padded). This keeps lexicographic
    ordering aligned with chronological ordering and plays nicely with range queries.
    """
    if not isinstance(s, str):
        raise ValueError(f"Date must be a string in YYYY-MM-DD format, got: {s!r}")
    m = _ISO_DATE_RE.match(s)
    if not m:
        raise ValueError(f"Invalid date format (expected YYYY-MM-DD): {s!r}")
    y, mo, d = map(int, m.groups())
    try:
        iso = _date(y, mo, d).isoformat()
    except Exception:
        raise ValueError(f"Invalid calendar date: {s!r}")
    return iso

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


def _trigger_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='trigger' AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def _ensure_trigger(conn: sqlite3.Connection, name: str, sql: str) -> None:
    """Create trigger if it doesn't exist.
    NOTE: For existing DBs, an older trigger with the same name but different SQL
    will be left in place (best-effort presence check). If you radically change
    trigger logic, consider bumping the trigger *name* to force a reinstall.
    """
    if not _trigger_exists(conn, name):
        conn.execute(sql)


def _create_date_validation_triggers(conn: sqlite3.Connection) -> None:
    """Install BEFORE INSERT/UPDATE triggers that enforce strict YYYY-MM-DD dates.
    SQLite cannot ALTER TABLE to add CHECK constraints easily post hoc, so triggers
    provide a robust, idempotent path for existing DBs.

    Presence check is *best-effort*: we key off trigger names and avoid re-creating
    if present. We do not diff SQL body. If you need to change logic, rename the
    trigger(s) below.
    """
    for name, table, column in (
        ("trg_schedule_validate_date_ins", "schedule", "date"),
        ("trg_schedule_validate_date_upd", "schedule", "date"),
        ("trg_swap_validate_date_ins", "swap_requests", "date"),
        ("trg_swap_validate_date_upd", "swap_requests", "date"),
    ):
        is_update = name.endswith("_upd")
        timing = "BEFORE UPDATE" if is_update else "BEFORE INSERT"
        sql = f'''
        CREATE TRIGGER {name}
        {timing} ON {table}
        FOR EACH ROW
        BEGIN
            SELECT CASE
                WHEN NEW.{column} IS NULL OR NEW.{column} NOT GLOB '____-__-__' THEN
                    RAISE(ABORT, '{table}.{column} must be YYYY-MM-DD')
                WHEN date(NEW.{column}) IS NULL THEN
                    RAISE(ABORT, '{table}.{column} is not a valid calendar date')
            END;
        END;
        '''
        _ensure_trigger(conn, name, sql)


def init_db():
    """Create tables if missing and ensure new columns exist (idempotent).
    Also: add production-grade constraints & indices and install date validation triggers.
    """
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

        # Backfill/alter for existing DBs (idempotent, tolerant of prior runs)
        for ddl in (
            "ALTER TABLE companies ADD COLUMN active INTEGER DEFAULT 1;",
            "ALTER TABLE schedule ADD COLUMN role TEXT;",
            "ALTER TABLE swap_requests ADD COLUMN shift TEXT;",
            "ALTER TABLE swap_requests ADD COLUMN note TEXT;",
        ):
            try:
                conn.execute(ddl)
            except sqlite3.OperationalError:
                pass

        # -----------------------------
        # Constraints & Indices for correctness & performance
        # -----------------------------
        # Uniqueness: an employee cannot be double-booked for the same (date, shift) in a company
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_schedule_company_emp_date_shift
            ON schedule(company_id, employee_id, date, shift)
            """
        )

        # Optional: keep employee names unique per company to avoid ambiguous name→id mapping
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_employees_company_name
            ON employees(company_id, name)
            """
        )

        # Range-query performance for schedule views
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_schedule_company_date
            ON schedule(company_id, date)
            """
        )

        # Swap-requests dashboards
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_swap_company_status
            ON swap_requests(company_id, status)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_swap_company_created
            ON swap_requests(company_id, created_at)
            """
        )

        # Install / refresh validation triggers
        _create_date_validation_triggers(conn)

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


def create_company(data_or_name: Union[str, Dict]) -> int:
    """Create a company.

    Accepts either a plain name (str) or a dict with any of:
      - name (required)
      - active_shifts, roles, rules, role_settings (JSON-serializable)
      - work_model (str), active (int/bool)

    Returns the new company id.
    """
    if isinstance(data_or_name, str):
        payload = {
            "name": data_or_name,
            "active_shifts": [],
            "roles": [],
            "rules": {},
            "role_settings": {},
            "work_model": "5ήμερο",
            "active": 1,
        }
    elif isinstance(data_or_name, dict):
        if not data_or_name.get("name"):
            raise ValueError("create_company requires 'name'")
        payload = {
            "name": data_or_name["name"],
            "active_shifts": data_or_name.get("active_shifts", []),
            "roles": data_or_name.get("roles", []),
            "rules": data_or_name.get("rules", {}),
            "role_settings": data_or_name.get("role_settings", {}),
            "work_model": data_or_name.get("work_model", "5ήμερο"),
            "active": int(data_or_name.get("active", 1)),
        }
    else:
        raise TypeError("create_company expects str or dict")

    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO companies (name, active_shifts, roles, rules, role_settings, work_model, active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["name"],
                json.dumps(payload["active_shifts"], ensure_ascii=False),
                json.dumps(payload["roles"], ensure_ascii=False),
                json.dumps(payload["rules"], ensure_ascii=False),
                json.dumps(payload["role_settings"], ensure_ascii=False),
                payload["work_model"],
                payload["active"],
            ),
        )
        return int(cur.lastrowid)


def update_company(company_id: int, data: Dict) -> None:
    with get_conn() as conn:
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
    """Resolve an employee id by name within a company.
    - If no match: return None
    - If multiple matches: raise ValueError to avoid silent misassignment
    This prevents ambiguous name→id mapping in the Visual Builder flow.
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id FROM employees WHERE company_id=? AND name=? ORDER BY id",
            (company_id, name),
        ).fetchall()
        if not rows:
            return None
        if len(rows) > 1:
            raise ValueError(
                f"Ambiguous employee name '{name}' in company {company_id} (found {len(rows)}). "
                "Please disambiguate by ID or enforce unique names."
            )
        return int(rows[0]["id"]) if rows else None

# -----------------------------
# Schedule (assignment-level role)
# -----------------------------

def add_schedule_entry(company_id: int, employee_id: int, date: str, shift: str, role: Optional[str] = None) -> None:
    """Insert a single assignment; de-duplicate on (company_id, employee_id, date, shift).
    If the row exists, update the role. Date is validated & normalized to YYYY-MM-DD.
    """
    iso_date = _normalize_iso_date_or_raise(date)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO schedule (company_id, employee_id, date, shift, role)
            VALUES (?,?,?,?,?)
            ON CONFLICT(company_id, employee_id, date, shift)
            DO UPDATE SET role=excluded.role
            """,
            (company_id, employee_id, iso_date, shift, role),
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
    """Inclusive date range [start_date, end_date]. Inputs are validated/normalized."""
    s0 = _normalize_iso_date_or_raise(start_date)
    e0 = _normalize_iso_date_or_raise(end_date)
    if s0 > e0:
        raise ValueError(f"start_date {s0} is after end_date {e0}")
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
            (company_id, s0, e0),
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


def _validate_entries_or_raise(conn: sqlite3.Connection, company_id: int, entries: List[Dict]) -> None:
    """Validate schedule entries *before* we delete anything.
    - Checks required keys
    - Ensures employee ids exist for the given company
    - Validates date format & calendar validity (YYYY-MM-DD)
    Raises ValueError on first problem.
    """
    required = ("employee_id", "date", "shift")
    for i, e in enumerate(entries):
        for k in required:
            if k not in e or e[k] in (None, ""):
                raise ValueError(f"Entry #{i} missing required field '{k}': {e!r}")
        try:
            int(e["employee_id"])  # type check only
        except Exception:
            raise ValueError(f"Entry #{i} has non-integer employee_id: {e!r}")
        e["date"] = _normalize_iso_date_or_raise(e["date"])  # may raise

    # Verify all employee ids exist for company
    emp_ids = sorted({int(e["employee_id"]) for e in entries})
    if emp_ids:
        qmarks = ",".join(["?"] * len(emp_ids))
        rows = conn.execute(
            f"SELECT id FROM employees WHERE company_id=? AND id IN ({qmarks})",
            (company_id, *emp_ids),
        ).fetchall()
        found = {r["id"] for r in rows}
        missing = [eid for eid in emp_ids if eid not in found]
        if missing:
            raise ValueError(f"Unknown employee_id(s) for company {company_id}: {missing}")


def bulk_save_week_schedule(company_id: int, start_date: str, end_date: str, entries: Iterable[Dict]) -> None:
    """Save a week's schedule transactionally over an inclusive date window.

    Defensive flow:
    1) Normalize window dates to YYYY-MM-DD and ensure s<=e
    2) Normalize/validate each entry (shape + date + employee existence) BEFORE touching current data
    3) Filter entries within [start_date, end_date] (after normalization)
    4) Delete window
    5) Upsert (dedup by (company_id, employee_id, date, shift))
    """
    s0 = _normalize_iso_date_or_raise(start_date)
    e0 = _normalize_iso_date_or_raise(end_date)
    if s0 > e0:
        raise ValueError(f"start_date {s0} is after end_date {e0}")

    entries = list(entries)

    with get_conn() as conn:
        if entries:
            _validate_entries_or_raise(conn, company_id, entries)

        # Filter by window (dates already normalized)
        entries = [e for e in entries if s0 <= e.get("date", "") <= e0]

        # Clear the window once (inclusive range)
        conn.execute(
            "DELETE FROM schedule WHERE company_id=? AND date>=? AND date<=?",
            (company_id, s0, e0),
        )

        if not entries:
            return

        conn.executemany(
            """
            INSERT INTO schedule (company_id, employee_id, date, shift, role)
            VALUES (?,?,?,?,?)
            ON CONFLICT(company_id, employee_id, date, shift)
            DO UPDATE SET role=excluded.role
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
# Swap Requests API (UI/DB name compatibility)
# -----------------------------

def _normalize_swap_ids(
    *,
    requester_id: Optional[int] = None,
    target_employee_id: Optional[int] = None,
    from_employee_id: Optional[int] = None,
    to_employee_id: Optional[int] = None,
) -> Tuple[int, int]:
    """Return (from_id, to_id) using flexible param names.

    UI uses requester_id / target_employee_id, while DB columns and some callers
    use from_employee_id / to_employee_id. We normalize here.
    """
    _from = from_employee_id if from_employee_id is not None else requester_id
    _to = to_employee_id if to_employee_id is not None else target_employee_id
    if _from is None or _to is None:
        raise ValueError("Both requester/from and target/to employee ids are required")
    return int(_from), int(_to)


def create_swap_request(
    company_id: int,
    date: str,
    shift: str,
    *,
    # Accept both naming schemes
    requester_id: Optional[int] = None,
    target_employee_id: Optional[int] = None,
    from_employee_id: Optional[int] = None,
    to_employee_id: Optional[int] = None,
) -> int:
    """Create a swap request for a single (date, shift).

    Accepts UI-style (requester_id, target_employee_id) or DB-style
    (from_employee_id, to_employee_id). For backward compatibility we also
    populate shift_from/shift_to with the same value as 'shift'.
    """
    iso_date = _normalize_iso_date_or_raise(date)
    _from, _to = _normalize_swap_ids(
        requester_id=requester_id,
        target_employee_id=target_employee_id,
        from_employee_id=from_employee_id,
        to_employee_id=to_employee_id,
    )

    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO swap_requests (company_id, from_employee_id, to_employee_id, date, shift, shift_from, shift_to, status)
            VALUES (?,?,?,?,?, ?, ?, 'pending')
            """,
            (company_id, _from, _to, iso_date, shift, shift, shift),
        )
        return int(cur.lastrowid)


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
    """Update status (pending|approved|rejected|applied) and optional note."""
    if status not in {"pending", "approved", "rejected", "applied"}:
        raise ValueError("Invalid status")
    with get_conn() as conn:
        conn.execute(
            "UPDATE swap_requests SET status = ?, note = ? WHERE id = ?",
            (status, note, request_id),
        )


def apply_approved_swap(
    company_id: int,
    date: str,
    shift: str,
    *,
    # UI-style
    requester_id: Optional[int] = None,
    target_employee_id: Optional[int] = None,
    # DB-style / legacy
    from_employee_id: Optional[int] = None,
    to_employee_id: Optional[int] = None,
) -> bool:
    """
    Move the (date, shift) assignment from requester to target.

    Accepts either (requester_id, target_employee_id) or (from_employee_id, to_employee_id).
    If the target already has an assignment for the same (date, shift), we drop the duplicate
    before reassigning. Returns True if a change was applied.

    Role policy: if the original assignment had a role that the target does not possess,
    we clear the role to NULL to avoid invalid role bindings silently propagating.
    """
    iso_date = _normalize_iso_date_or_raise(date)
    _from, _to = _normalize_swap_ids(
        requester_id=requester_id,
        target_employee_id=target_employee_id,
        from_employee_id=from_employee_id,
        to_employee_id=to_employee_id,
    )

    with get_conn() as conn:
        # Find the requester's existing assignment for that date/shift
        row_req = conn.execute(
            "SELECT id, role FROM schedule WHERE company_id = ? AND employee_id = ? AND date = ? AND shift = ?",
            (company_id, _from, iso_date, shift),
        ).fetchone()
        if not row_req:
            return False

        # Ensure the target has no duplicate assignment for that slot
        conn.execute(
            "DELETE FROM schedule WHERE company_id = ? AND employee_id = ? AND date = ? AND shift = ?",
            (company_id, _to, iso_date, shift),
        )

        # If role exists but target doesn't have it, clear role
        role_to_apply = row_req["role"]
        if role_to_apply:
            target_roles_row = conn.execute(
                "SELECT roles FROM employees WHERE id=?",
                (_to,),
            ).fetchone()
            target_roles = []
            if target_roles_row and target_roles_row["roles"]:
                try:
                    target_roles = json.loads(target_roles_row["roles"]) or []
                except Exception:
                    target_roles = []
            if role_to_apply not in target_roles:
                role_to_apply = None  # clear role if target is not suitable

        # Reassign the schedule row to the target
        conn.execute(
            "UPDATE schedule SET employee_id = ?, role = ? WHERE id = ?",
            (_to, role_to_apply, row_req["id"]),
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
            (company_id, iso_date, shift, _from, _to),
        )
        return True
