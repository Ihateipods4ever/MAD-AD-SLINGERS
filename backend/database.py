import sqlite3
import os
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

class Database:
    def __init__(self):
        self.connection = None
        self.cursor = None
        self.is_sqlite = False

    def connect(self):
        """Connect to the database using environment variables"""
        db_url = os.getenv("DATABASE_URL", "sqlite:///agency_db.sqlite")
        if db_url.startswith("sqlite:///"):
            self.is_sqlite = True
            db_path = db_url.replace("sqlite:///", "")
            self.connection = sqlite3.connect(db_path)
            self.cursor = self.connection.cursor()
            self._create_tables()
        elif db_url.startswith("postgresql://"):
            self.is_sqlite = False
            conn_params = db_url.replace("postgresql://", "")
            self.connection = psycopg2.connect(conn_params)
            self.cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            self._create_tables()

    def _create_tables(self):
        """Create necessary tables if they don't exist"""
        if self.is_sqlite:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT,
                    website_url TEXT,
                    industry TEXT,
                    monthly_ad_spend INTEGER,
                    email TEXT,
                    phone TEXT,
                    contact_person TEXT,
                    lead_score INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'new',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    description TEXT,
                    status TEXT DEFAULT 'active',
                    budget INTEGER,
                    start_date TIMESTAMP,
                    end_date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lead_id INTEGER,
                    amount INTEGER,
                    status TEXT DEFAULT 'pending',
                    due_date TIMESTAMP,
                    paid_date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lead_id) REFERENCES leads (id)
                )
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE,
                    password TEXT,
                    name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id SERIAL PRIMARY KEY,
                    company_name VARCHAR(255),
                    website_url VARCHAR(500),
                    industry VARCHAR(100),
                    monthly_ad_spend INTEGER,
                    email VARCHAR(255),
                    phone VARCHAR(50),
                    contact_person VARCHAR(255),
                    lead_score INTEGER DEFAULT 0,
                    status VARCHAR(50) DEFAULT 'new',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS campaigns (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255),
                    description TEXT,
                    status VARCHAR(50) DEFAULT 'active',
                    budget INTEGER,
                    start_date TIMESTAMP,
                    end_date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    id SERIAL PRIMARY KEY,
                    lead_id INTEGER,
                    amount INTEGER,
                    status VARCHAR(50) DEFAULT 'pending',
                    due_date TIMESTAMP,
                    paid_date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lead_id) REFERENCES leads (id)
                )
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE,
                    password TEXT,
                    name VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        self.connection.commit()

    def insert_lead(self, lead_data: Dict[str, Any]) -> int:
        """Insert a new lead into the database"""
        if self.is_sqlite:
            columns = ', '.join(lead_data.keys())
            placeholders = ', '.join(['?'] * len(lead_data))
            values = tuple(lead_data.values())
            self.cursor.execute(f"INSERT INTO leads ({columns}) VALUES ({placeholders})", values)
        else:
            columns = ', '.join(lead_data.keys())
            placeholders = ', '.join(['%s'] * len(lead_data))
            values = tuple(lead_data.values())
            self.cursor.execute(f"INSERT INTO leads ({columns}) VALUES ({placeholders})", values)
        self.connection.commit()
        return self.cursor.lastrowid

    def get_leads(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all leads or filter by status"""
        if status:
            if self.is_sqlite:
                self.cursor.execute("SELECT * FROM leads WHERE status = ? ORDER BY created_at DESC", (status,))
            else:
                self.cursor.execute("SELECT * FROM leads WHERE status = %s ORDER BY created_at DESC", (status,))
        else:
            if self.is_sqlite:
                self.cursor.execute("SELECT * FROM leads ORDER BY created_at DESC")
            else:
                self.cursor.execute("SELECT * FROM leads ORDER BY created_at DESC")
        return self.cursor.fetchall()

    def get_campaigns(self) -> List[Dict[str, Any]]:
        """Get all campaigns"""
        if self.is_sqlite:
            self.cursor.execute("SELECT * FROM campaigns ORDER BY created_at DESC")
        else:
            self.cursor.execute("SELECT * FROM campaigns ORDER BY created_at DESC")
        return self.cursor.fetchall()

    def get_invoices(self) -> List[Dict[str, Any]]:
        """Get all invoices"""
        if self.is_sqlite:
            self.cursor.execute("SELECT * FROM invoices ORDER BY created_at DESC")
        else:
            self.cursor.execute("SELECT * FROM invoices ORDER BY created_at DESC")
        return self.cursor.fetchall()

    def create_user(self, email: str, password: str, name: str) -> Optional[int]:
        """Create a new user"""
        hashed_password = self._hash_password(password)
        if self.is_sqlite:
            self.cursor.execute(
                "INSERT INTO users (email, password, name) VALUES (?, ?, ?)",
                (email, hashed_password, name)
            )
        else:
            self.cursor.execute(
                "INSERT INTO users (email, password, name) VALUES (%s, %s, %s)",
                (email, hashed_password, name)
            )
        self.connection.commit()
        return self.cursor.lastrowid

    def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate a user"""
        if self.is_sqlite:
            self.cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        else:
            self.cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = self.cursor.fetchone()
        if user and self._verify_password(password, user['password']):
            return user
        return None

    def _hash_password(self, password: str) -> str:
        """Hash a password"""
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest()

    def _verify_password(self, password: str, hashed: str) -> bool:
        """Verify a password"""
        import hashlib
        return self._hash_password(password) == hashed

    def close(self):
        """Close the database connection"""
        if self.connection:
            self.connection.close()

    def fetch_all_dicts(self) -> List[Dict[str, Any]]:
        """Fetch all results as dictionaries"""
        if self.is_sqlite:
            return [dict(row) for row in self.cursor.fetchall()]
        return self.cursor.fetchall()

db = Database()