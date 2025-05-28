import sqlite3
import logging
import threading
import queue
from config import DATABASE_FILE

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connection pool for better performance
class ConnectionPool:
    """SQLite connection pool for better performance with multiple users"""
    def __init__(self, db_file, max_connections=10):
        self.db_file = db_file
        self.max_connections = max_connections
        self.connections = queue.Queue(maxsize=max_connections)
        self.connection_count = 0
        self.lock = threading.RLock()
    
    def get_connection(self):
        """Get a connection from the pool or create a new one if needed"""
        try:
            # Try to get an existing connection from the pool
            return self.connections.get(block=False)
        except queue.Empty:
            # If the pool is empty, create a new connection if under the limit
            with self.lock:
                if self.connection_count < self.max_connections:
                    conn = sqlite3.connect(self.db_file, check_same_thread=False)
                    conn.row_factory = sqlite3.Row  # Enable row factory for better row access
                    self.connection_count += 1
                    return conn
                else:
                    # If at max connections, wait for one to become available
                    return self.connections.get()
    
    def return_connection(self, conn):
        """Return a connection to the pool"""
        try:
            # Reset the connection to a clean state
            conn.rollback()
            # Put the connection back in the pool
            self.connections.put(conn, block=False)
        except queue.Full:
            # If the pool is full, close the connection
            conn.close()
            with self.lock:
                self.connection_count -= 1
    
    def close_all(self):
        """Close all connections in the pool"""
        while not self.connections.empty():
            try:
                conn = self.connections.get(block=False)
                conn.close()
            except queue.Empty:
                break
        with self.lock:
            self.connection_count = 0

# Create a global connection pool
connection_pool = ConnectionPool(DATABASE_FILE)

def init_db():
    """Initialize the database if it doesn't exist."""
    conn = None
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        
        # Create users table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            language TEXT DEFAULT "uz",
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create test_results table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            test_name TEXT,
            date TEXT,
            correct INTEGER,
            total INTEGER,
            percent REAL,
            points INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        ''')
        
        # Create an index for faster user_id lookups in test_results
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_test_results_user_id ON test_results(user_id)')
        
        conn.commit()
        logger.info("Database initialized successfully")
    except sqlite3.Error as e:
        logger.error(f"Error initializing database: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            connection_pool.return_connection(conn)

def add_user(user_id, username=None, first_name=None, last_name=None):
    """Add a new user to the database or update existing user."""
    conn = None
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            # Update existing user
            cursor.execute('''
            UPDATE users 
            SET username = ?, first_name = ?, last_name = ?
            WHERE user_id = ?
            ''', (username, first_name, last_name, user_id))
        else:
            # Insert new user
            cursor.execute('''
            INSERT INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name))
        
        conn.commit()
        logger.info(f"User {user_id} added/updated in database")
        return True
    except Exception as e:
        logger.error(f"Error adding user to database: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            connection_pool.return_connection(conn)

def get_user(user_id):
    """Get user information from the database."""
    conn = None
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if user:
            return {
                'user_id': user['user_id'],
                'username': user['username'],
                'first_name': user['first_name'],
                'last_name': user['last_name'],
                'language': user['language'],
                'join_date': user['join_date']
            }
        return None
    except Exception as e:
        logger.error(f"Error getting user from database: {e}")
        return None
    finally:
        if conn:
            connection_pool.return_connection(conn)

def get_user_language(user_id):
    """Get user's preferred language."""
    conn = None
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT language FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        # Return 'uz' if no language is found or if language is None
        return result['language'] if result and result['language'] else 'uz'
    except Exception as e:
        logger.error(f"Error getting user language: {e}")
        return 'uz'  # Default to Uzbek on error
    finally:
        if conn:
            connection_pool.return_connection(conn)

def get_all_users():
    """Get all users from the database."""
    conn = None
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM users')
        users = [row['user_id'] for row in cursor.fetchall()]
        
        return users
    except sqlite3.Error as e:
        logger.error(f"Error getting users from database: {e}")
        return []  # Return empty list on error
    except Exception as e:
        logger.error(f"Unexpected error in get_all_users: {e}")
        return []  # Return empty list on error
    finally:
        if conn:
            connection_pool.return_connection(conn)

def remove_user(user_id):
    """Remove a user from the database."""
    conn = None
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        
        # First delete related test results
        cursor.execute('DELETE FROM test_results WHERE user_id = ?', (user_id,))
        
        # Then delete the user
        cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        
        conn.commit()
        logger.info(f"User {user_id} removed from database")
        return True
    except Exception as e:
        logger.error(f"Error removing user from database: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            connection_pool.return_connection(conn)

async def update_user_language(user_id, language):
    """Update user's preferred language in the database."""
    conn = None
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        
        # First check if language column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'language' not in columns:
            # Add language column if it doesn't exist
            cursor.execute('ALTER TABLE users ADD COLUMN language TEXT DEFAULT "uz"')
            conn.commit()
            
        # Update language
        cursor.execute('''
        UPDATE users
        SET language = ?
        WHERE user_id = ?
        ''', (language, user_id))
        
        conn.commit()
        logger.info(f"Updated language for user {user_id} to {language}")
        return True
    except Exception as e:
        logger.error(f"Error updating user language: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            connection_pool.return_connection(conn)





def get_referrer(user_id):
    """Get the referrer of a user, if any."""
    conn = None
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT referrer_id FROM referrals WHERE referred_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result:
            return result['referrer_id']
        return None
    except Exception as e:
        logger.error(f"Error getting referrer: {e}")
        return None
    finally:
        if conn:
            connection_pool.return_connection(conn)

async def save_test_result(user_id, test_name, date, correct, total, percent, points):
    """Save a test result to the database."""
    conn = None
    try:
        # Validate user_id to ensure it's a valid integer
        try:
            user_id_int = int(user_id)
        except (ValueError, TypeError):
            logger.error(f"Invalid user_id: {user_id}, cannot convert to integer")
            return False
            
        # Validate other parameters
        if not test_name or not date:
            logger.error(f"Missing required parameters for save_test_result")
            return False
            
        # Validate numeric values
        try:
            correct = int(correct)
            total = int(total)
            percent = float(percent)
            points = int(points)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid numeric parameters for save_test_result: {e}")
            return False
            
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        
        # Insert the result
        cursor.execute('''
        INSERT INTO test_results (user_id, test_name, date, correct, total, percent, points)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id_int, test_name, date, correct, total, percent, points))
        
        conn.commit()
        logger.info(f"Test result saved for user {user_id_int}")
        return True
    except Exception as e:
        logger.error(f"Error saving test result: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            connection_pool.return_connection(conn)

async def get_user_test_results(user_id):
    """Get all test results for a user."""
    conn = None
    try:
        # Validate user_id to ensure it's a valid integer
        try:
            user_id_int = int(user_id)
        except (ValueError, TypeError):
            logger.error(f"Invalid user_id: {user_id}, cannot convert to integer")
            return []
            
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        
        # Ensure we only get results for this specific user
        cursor.execute('''
        SELECT test_name, date, correct, total, percent, points
        FROM test_results
        WHERE user_id = ?
        ORDER BY date DESC
        LIMIT 50  -- Limit to most recent 50 results for performance
        ''', (user_id_int,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'test_name': row['test_name'],
                'date': row['date'],
                'correct': row['correct'],
                'total': row['total'],
                'percent': row['percent'],
                'points': row['points'],
                'user_id': user_id_int  # Include user_id to confirm ownership
            })
        
        logger.info(f"Retrieved {len(results)} test results for user {user_id_int}")
        return results
    except Exception as e:
        logger.error(f"Error getting test results: {e}")
        return []
    finally:
        if conn:
            connection_pool.return_connection(conn)

async def get_all_test_results():
    """Get all test results from the database."""
    conn = None
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT user_id, test_name, date, correct, total, percent, points 
        FROM test_results 
        ORDER BY date DESC
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        return [{
            'user_id': result[0],
            'test_name': result[1],
            'date': result[2],
            'correct': result[3],
            'total': result[4],
            'percent': result[5],
            'points': result[6]
        } for result in results]
    except Exception as e:
        logger.error(f"Error getting all test results: {e}")
        return []

# Function to close all database connections when shutting down
def close_connections():
    """Close all database connections in the pool"""
    try:
        connection_pool.close_all()
        logger.info("All database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")
