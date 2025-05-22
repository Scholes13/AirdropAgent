"""
Database module for AirdropAgent
"""
import sqlite3
import os
import datetime
from config import DATABASE_PATH

# Ensure data directory exists
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

def init_db():
    """Initialize the SQLite database"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Create airdrops table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS airdrops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_name TEXT,
        username TEXT,
        tweet_text TEXT,
        tweet_url TEXT,
        website_url TEXT,
        rating REAL,
        analysis TEXT,
        is_scam BOOLEAN,
        timestamp DATETIME
    )
    ''')
    
    # Create website_data table for storing scraped data
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS website_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        about_text TEXT,
        team_info TEXT,
        tokenomics TEXT,
        domain_age TEXT,
        timestamp DATETIME,
        FOREIGN KEY (project_id) REFERENCES airdrops (id)
    )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized")

def save_airdrop_analysis(project_name, username, tweet_text, tweet_url, website_url, 
                          rating, analysis, is_scam, timestamp=None):
    """Save airdrop analysis to database"""
    if timestamp is None:
        timestamp = datetime.datetime.now()
        
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO airdrops (project_name, username, tweet_text, tweet_url, website_url, 
                         rating, analysis, is_scam, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (project_name, username, tweet_text, tweet_url, website_url, 
         rating, analysis, is_scam, timestamp))
    
    # Get the ID of the inserted row
    airdrop_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    return airdrop_id

def save_website_data(project_id, about_text, team_info, tokenomics, domain_age, timestamp=None):
    """Save website data to database"""
    if timestamp is None:
        timestamp = datetime.datetime.now()
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO website_data (project_id, about_text, team_info, tokenomics, domain_age, timestamp)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (project_id, about_text, team_info, tokenomics, domain_age, timestamp))
    
    conn.commit()
    conn.close()

def get_recent_airdrops(limit=50):
    """Get recent airdrops from database"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT * FROM airdrops ORDER BY timestamp DESC LIMIT ?
    ''', (limit,))
    
    airdrops = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return airdrops

def get_airdrop_by_id(airdrop_id):
    """Get airdrop by ID"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT a.*, w.about_text, w.team_info, w.tokenomics, w.domain_age 
    FROM airdrops a 
    LEFT JOIN website_data w ON a.id = w.project_id
    WHERE a.id = ?
    ''', (airdrop_id,))
    
    airdrop = cursor.fetchone()
    conn.close()
    
    return dict(airdrop) if airdrop else None

def get_stats():
    """Get statistics about airdrops"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Get total count
    cursor.execute("SELECT COUNT(*) FROM airdrops")
    total = cursor.fetchone()[0]
    
    # Get scam count
    cursor.execute("SELECT COUNT(*) FROM airdrops WHERE is_scam = 1")
    scam_count = cursor.fetchone()[0]
    
    # Get avg rating
    cursor.execute("SELECT AVG(rating) FROM airdrops")
    avg_rating = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "total_airdrops": total,
        "scam_count": scam_count,
        "legitimate_count": total - scam_count,
        "avg_rating": avg_rating if avg_rating else 0
    }

def get_airdrops_by_filter(is_scam=None, is_legitimate=None, limit=50):
    """Get airdrops filtered by scam or legitimate status
    
    Args:
        is_scam (bool, optional): Filter for scam airdrops
        is_legitimate (bool, optional): Filter for legitimate airdrops
        limit (int, optional): Maximum number of results
        
    Returns:
        list: List of airdrop dictionaries matching the filters
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM airdrops WHERE 1=1"
    params = []
    
    if is_scam is not None:
        query += " AND is_scam = ?"
        params.append(1 if is_scam else 0)
        
    if is_legitimate is not None:
        query += " AND is_legitimate = ?"
        params.append(1 if is_legitimate else 0)
    
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    airdrops = [dict(row) for row in cursor.fetchall()]
    
    # Convert date strings to datetime objects
    for airdrop in airdrops:
        if 'created_at' in airdrop and airdrop['created_at']:
            airdrop['created_at'] = datetime.datetime.fromisoformat(airdrop['created_at'].replace('Z', '+00:00'))
    
    conn.close()
    return airdrops

# Initialize database when module is imported
init_db() 