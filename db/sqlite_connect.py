import sqlite3
import os

sqlite_file = r'D:\VSCodeProjects\stka\backend\data\sqlite_db.db'


def connect():
    os.makedirs(os.path.dirname(sqlite_file), exist_ok=True)
    conn = sqlite3.connect(sqlite_file)
    cursor = conn.cursor()
    return conn, cursor


def get_db_path():
    return sqlite_file
