
import sqlite3
from datetime import datetime


class DatabaseManager:
    '''
    A class for managing the SQLite database, including creating tables and inserting/querying data
    '''

    def __init__(self, db_name="mainstream.db"):
        self.db_name = db_name
        self._create_tables()

    def _create_tables(self):
        '''
        Create the necessary tables in the database if they don't already exist
        '''
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_id TEXT,
                    query TEXT NOT NULL,
                    response TEXT NOT NULL,
                    api_name TEXT NOT NULL,
                    score INTEGER,
                    comparative_rank INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Backward-compatible migration for existing DBs created before query_id existed.
            cursor.execute("PRAGMA table_info(responses)")
            column_names = [row[1] for row in cursor.fetchall()]
            if 'query_id' not in column_names:
                cursor.execute(
                    "ALTER TABLE responses ADD COLUMN query_id TEXT")
            if 'score' not in column_names:
                cursor.execute(
                    "ALTER TABLE responses ADD COLUMN score INTEGER")
            if 'comparative_rank' not in column_names:
                cursor.execute(
                    "ALTER TABLE responses ADD COLUMN comparative_rank INTEGER")

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_responses_query_id
                ON responses(query_id)
            ''')
            conn.commit()

    def fetch_queries(self):
        '''
        Return query runs ordered by most recent response first
        '''
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    COALESCE(query_id, 'legacy:' || query) AS run_id,
                    query,
                    MAX(timestamp) AS latest_timestamp,
                    MAX(score) AS top_score
                FROM responses
                GROUP BY run_id, query
                ORDER BY latest_timestamp DESC
            ''')
            return cursor.fetchall()

    def fetch_responses_for_query(self, query_id, query):
        '''
        Return all stored responses for a query run in insertion order
        '''
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            if query_id.startswith('legacy:'):
                cursor.execute('''
                    SELECT id, api_name, response, timestamp, score, comparative_rank
                    FROM responses
                    WHERE query = ? AND query_id IS NULL
                    ORDER BY id ASC
                ''', (query,))
            else:
                cursor.execute('''
                    SELECT id, api_name, response, timestamp, score, comparative_rank
                    FROM responses
                    WHERE query_id = ?
                    ORDER BY id ASC
                ''', (query_id,))
            rows = cursor.fetchall()
            return [
                {
                    'id': row[0],
                    'api_name': row[1],
                    'response': row[2],
                    'timestamp': row[3],
                    'score': row[4],
                    'comparative_rank': row[5],
                }
                for row in rows
            ]

    def insert_response(
        self,
        query_id,
        query,
        response,
        api_name,
        score=None,
        comparative_rank=None,
    ):
        '''
        Insert a new response into the database
        '''
        with sqlite3.connect(self.db_name) as conn:
            timestamp = datetime.now().isoformat()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO responses (
                    query_id,
                    query,
                    response,
                    api_name,
                    score,
                    comparative_rank,
                    timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (query_id, query, response, api_name, score, comparative_rank, timestamp))
            conn.commit()
            return cursor.lastrowid

    def update_comparative_rank(self, query_id, api_name, comparative_rank):
        '''
        Update comparative rank for a response row identified by query run and API
        '''
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE responses
                SET comparative_rank = ?
                WHERE query_id = ? AND api_name = ?
            ''', (comparative_rank, query_id, api_name))
            conn.commit()

    def update_comparative_rank_by_id(self, row_id, comparative_rank):
        '''
        Update comparative rank for a response row identified by its row id
        '''
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE responses
                SET comparative_rank = ?
                WHERE id = ?
            ''', (comparative_rank, row_id))
            conn.commit()
