# -*- coding: utf-8 -*-
"""
Employee Self-Service Shift Swaps Module
Allows employees to request shift swaps and trades
"""

import sqlite3
import json
from datetime import datetime, date
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class SwapStatus(Enum):
    """Swap request status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


@dataclass
class ShiftSwapRequest:
    """Shift swap request"""
    id: Optional[int] = None
    requesting_employee_id: int = 0
    requesting_employee_name: str = ""
    target_employee_id: Optional[int] = None
    target_employee_name: Optional[str] = None
    shift_date: str = ""  # YYYY-MM-DD
    shift_type: str = ""  # morning, afternoon, evening, etc.
    role: str = ""
    swap_type: str = "swap"  # swap, pickup, drop
    reason: str = ""
    status: str = SwapStatus.PENDING.value
    requested_at: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    response_message: str = ""
    notes: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ShiftSwapRequest':
        """Create from dictionary"""
        return cls(**data)


def init_swap_db(db_path: str = "../shift_maker.sqlite3"):
    """Initialize shift swap tables"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shift_swap_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requesting_employee_id INTEGER NOT NULL,
            requesting_employee_name TEXT NOT NULL,
            target_employee_id INTEGER,
            target_employee_name TEXT,
            shift_date TEXT NOT NULL,
            shift_type TEXT NOT NULL,
            role TEXT NOT NULL,
            swap_type TEXT DEFAULT 'swap',
            reason TEXT,
            status TEXT DEFAULT 'pending',
            requested_at TEXT,
            approved_by TEXT,
            approved_at TEXT,
            response_message TEXT,
            notes TEXT,
            FOREIGN KEY (requesting_employee_id) REFERENCES employees(id)
        )
    """)
    
    # Table for shift swap bids (employees expressing interest in open shifts)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shift_bids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_date TEXT NOT NULL,
            shift_type TEXT NOT NULL,
            role TEXT NOT NULL,
            employee_id INTEGER NOT NULL,
            employee_name TEXT NOT NULL,
            bid_amount REAL DEFAULT 0,
            priority INTEGER DEFAULT 5,
            created_at TEXT,
            status TEXT DEFAULT 'pending',
            awarded_at TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)
    
    conn.commit()
    conn.close()


def create_swap_request(
    requesting_employee_id: int,
    requesting_employee_name: str,
    shift_date: str,
    shift_type: str,
    role: str,
    swap_type: str = "swap",
    target_employee_id: Optional[int] = None,
    target_employee_name: Optional[str] = None,
    reason: str = "",
    db_path: str = "../shift_maker.sqlite3"
) -> int:
    """Create a new shift swap request"""
    # Ensure schema exists first
    init_swap_db(db_path)
    
    conn = sqlite3.connect(db_path, timeout=20.0)
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
    cursor.execute("""
        INSERT INTO shift_swap_requests
        (requesting_employee_id, requesting_employee_name, target_employee_id,
         target_employee_name, shift_date, shift_type, role, swap_type, reason,
         status, requested_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (requesting_employee_id, requesting_employee_name, target_employee_id,
          target_employee_name, shift_date, shift_type, role, swap_type, reason, now))
    
    swap_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return swap_id


def get_swap_requests(
    employee_id: Optional[int] = None,
    status: Optional[str] = None,
    db_path: str = "../shift_maker.sqlite3"
) -> List[ShiftSwapRequest]:
    """Get shift swap requests"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM shift_swap_requests WHERE 1=1"
    params = []
    
    if employee_id:
        query += " AND (requesting_employee_id=? OR target_employee_id=?)"
        params.extend([employee_id, employee_id])
    
    if status:
        query += " AND status=?"
        params.append(status)
    
    query += " ORDER BY requested_at DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [ShiftSwapRequest.from_dict(dict(row)) for row in rows]


def get_pending_swap_requests_for_approval(
    db_path: str = "../shift_maker.sqlite3"
) -> List[ShiftSwapRequest]:
    """Get all pending swap requests for manager approval"""
    return get_swap_requests(status=SwapStatus.PENDING.value, db_path=db_path)


def approve_swap_request(
    swap_id: int,
    approved_by: str,
    response_message: str = "",
    db_path: str = "../shift_maker.sqlite3"
) -> bool:
    """Approve a swap request"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
    cursor.execute("""
        UPDATE shift_swap_requests
        SET status='approved', approved_by=?, approved_at=?, response_message=?
        WHERE id=?
    """, (approved_by, now, response_message, swap_id))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return success


def reject_swap_request(
    swap_id: int,
    approved_by: str,
    response_message: str = "",
    db_path: str = "../shift_maker.sqlite3"
) -> bool:
    """Reject a swap request"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
    cursor.execute("""
        UPDATE shift_swap_requests
        SET status='rejected', approved_by=?, approved_at=?, response_message=?
        WHERE id=?
    """, (approved_by, now, response_message, swap_id))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return success


def cancel_swap_request(
    swap_id: int,
    db_path: str = "../shift_maker.sqlite3"
) -> bool:
    """Cancel a swap request (by requester)"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE shift_swap_requests
        SET status='cancelled'
        WHERE id=? AND status='pending'
    """, (swap_id,))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return success


def create_shift_bid(
    shift_date: str,
    shift_type: str,
    role: str,
    employee_id: int,
    employee_name: str,
    priority: int = 5,
    db_path: str = "../shift_maker.sqlite3"
) -> int:
    """Create a shift bid for an open shift"""
    # Ensure schema exists first
    init_swap_db(db_path)
    
    conn = sqlite3.connect(db_path, timeout=20.0)
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
    cursor.execute("""
        INSERT INTO shift_bids
        (shift_date, shift_type, role, employee_id, employee_name, priority, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
    """, (shift_date, shift_type, role, employee_id, employee_name, priority, now))
    
    bid_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return bid_id


def get_shift_bids(
    shift_date: Optional[str] = None,
    status: str = "pending",
    db_path: str = "../shift_maker.sqlite3"
) -> List[Dict]:
    """Get shift bids"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM shift_bids WHERE status=?"
    params = [status]
    
    if shift_date:
        query += " AND shift_date=?"
        params.append(shift_date)
    
    query += " ORDER BY priority DESC, created_at ASC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def award_shift_bid(
    bid_id: int,
    db_path: str = "../shift_maker.sqlite3"
) -> bool:
    """Award a shift to the bidder"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
    # Get bid info
    cursor.execute("SELECT * FROM shift_bids WHERE id=?", (bid_id,))
    bid = cursor.execute("SELECT * FROM shift_bids WHERE id=?", (bid_id,)).fetchone()
    
    if not bid:
        conn.close()
        return False
    
    # Award this bid
    cursor.execute("""
        UPDATE shift_bids
        SET status='awarded', awarded_at=?
        WHERE id=?
    """, (now, bid_id))
    
    # Reject other bids for same shift
    cursor.execute("""
        UPDATE shift_bids
        SET status='rejected'
        WHERE shift_date=? AND shift_type=? AND role=? AND status='pending' AND id!=?
    """, (bid[1], bid[2], bid[3], bid_id))
    
    conn.commit()
    conn.close()
    
    return True


# Initialize database when module is imported
try:
    init_swap_db()
except Exception as e:
    print(f"Warning: Could not initialize swap database: {e}")
