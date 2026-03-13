"""
database/db_manager.py
Manages the SQLite database for storing person records and face encodings.
"""
import sqlite3
import os
import pickle
import numpy as np
from datetime import datetime
from typing import Optional, List, Dict, Any


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "facerec.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db():
    """Create tables if they don't exist and seed sample data."""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS persons (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name   TEXT NOT NULL,
            id_number   TEXT UNIQUE NOT NULL,
            age         INTEGER,
            gender      TEXT,
            nationality TEXT,
            address     TEXT,
            status      TEXT DEFAULT 'No Record',
            last_seen   TEXT,
            notes       TEXT,
            photo_blob  BLOB,
            encoding    BLOB,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS search_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            query_type  TEXT,
            query_value TEXT,
            result_count INTEGER,
            searched_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    _seed_sample_data()


def _seed_sample_data():
    """Insert sample records for demo/research purposes."""
    conn = get_connection()
    c = conn.cursor()

    existing = c.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    if existing > 0:
        conn.close()
        return

    samples = [
        ("Michael Turner",  "456-78-9123", 35, "Male",   "United States", "1234 Elm St, York, NY",      "Felony Warrant",  "05/14/2021", "Known associate of fraud ring."),
        ("Jason Miller",    "388-45-7650", 38, "Male",   "United States", "88 Oak Ave, Boston, MA",      "Arrest Record",   "11/02/2022", "Arrested for theft 2019, released 2020."),
        ("David Collins",   "491-23-6578", 37, "Male",   "United States", "500 Pine Rd, Chicago, IL",    "Under Investigation", "03/17/2023", "Subject of ongoing financial fraud case."),
        ("Eric Sanders",    "572-19-8431", 34, "Male",   "United States", "22 Maple Dr, Austin, TX",     "No Record",       "08/29/2023", "Clean record. Flagged for proximity."),
        ("Sarah Nguyen",    "601-55-3311", 29, "Female", "United States", "10 Birch Ln, Seattle, WA",    "Witness",         "01/05/2024", "Witness in case #4421-B."),
        ("Robert Hale",     "712-88-2200", 52, "Male",   "United Kingdom","15 Crown St, London, UK",     "Interpol Notice", "06/18/2023", "Subject of international warrant."),
        ("Amanda Cruz",     "329-14-8876", 31, "Female", "United States", "71 River Blvd, Miami, FL",    "No Record",       "12/20/2023", ""),
        ("James Okafor",    "580-33-9901", 44, "Male",   "Nigeria",       "Abuja, FCT, Nigeria",          "Person of Interest", "09/01/2023", "Linked to wire fraud network."),
    ]

    for s in samples:
        c.execute("""
            INSERT OR IGNORE INTO persons
            (full_name, id_number, age, gender, nationality, address, status, last_seen, notes)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, s)

    conn.commit()
    conn.close()


def get_all_persons() -> List[Dict]:
    conn = get_connection()
    c = conn.cursor()
    rows = c.execute("SELECT * FROM persons ORDER BY full_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_persons(query: str) -> List[Dict]:
    conn = get_connection()
    c = conn.cursor()
    q = f"%{query}%"
    rows = c.execute("""
        SELECT * FROM persons
        WHERE full_name LIKE ? OR id_number LIKE ? OR nationality LIKE ?
           OR address LIKE ? OR status LIKE ? OR notes LIKE ?
        ORDER BY full_name
    """, (q, q, q, q, q, q)).fetchall()
    conn.close()
    _log_search("text", query, len(rows))
    return [dict(r) for r in rows]


def get_person_by_id(person_id: int) -> Optional[Dict]:
    conn = get_connection()
    c = conn.cursor()
    row = c.execute("SELECT * FROM persons WHERE id=?", (person_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_person(data: Dict) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO persons (full_name, id_number, age, gender, nationality,
                             address, status, last_seen, notes, photo_blob, encoding)
        VALUES (:full_name,:id_number,:age,:gender,:nationality,
                :address,:status,:last_seen,:notes,:photo_blob,:encoding)
    """, data)
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id


def update_person(person_id: int, data: Dict):
    conn = get_connection()
    c = conn.cursor()
    data['id'] = person_id
    c.execute("""
        UPDATE persons SET
            full_name=:full_name, id_number=:id_number, age=:age,
            gender=:gender, nationality=:nationality, address=:address,
            status=:status, last_seen=:last_seen, notes=:notes
        WHERE id=:id
    """, data)
    conn.commit()
    conn.close()


def delete_person(person_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM persons WHERE id=?", (person_id,))
    conn.commit()
    conn.close()


def save_encoding(person_id: int, encoding: np.ndarray, photo_blob: bytes):
    conn = get_connection()
    conn.execute("""
        UPDATE persons SET encoding=?, photo_blob=? WHERE id=?
    """, (pickle.dumps(encoding), photo_blob, person_id))
    conn.commit()
    conn.close()


def get_all_encodings() -> List[Dict]:
    """Return all persons that have a face encoding stored."""
    conn = get_connection()
    c = conn.cursor()
    rows = c.execute(
        "SELECT id, full_name, id_number, status, encoding, photo_blob FROM persons WHERE encoding IS NOT NULL"
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d['encoding'] = pickle.loads(d['encoding'])
        results.append(d)
    return results


def get_search_log(limit: int = 50) -> List[Dict]:
    conn = get_connection()
    c = conn.cursor()
    rows = c.execute(
        "SELECT * FROM search_log ORDER BY searched_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _log_search(query_type: str, query_value: str, result_count: int):
    conn = get_connection()
    conn.execute(
        "INSERT INTO search_log (query_type, query_value, result_count) VALUES (?,?,?)",
        (query_type, query_value, result_count)
    )
    conn.commit()
    conn.close()
