import psycopg2
import psycopg2.extras
import os
import streamlit as st
from dotenv import load_dotenv
load_dotenv()

def get_conn():
    try:
        db_url = st.secrets["DATABASE_URL"]
    except:
        db_url = os.getenv("DATABASE_URL")
    conn = psycopg2.connect(db_url)
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        due_date TEXT,
        subject TEXT,
        created_by INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        course_id INTEGER,
        video_url TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS task_files (
        id SERIAL PRIMARY KEY,
        task_id INTEGER,
        filename TEXT,
        filepath TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS progress (
        id SERIAL PRIMARY KEY,
        student_id INTEGER,
        task_id INTEGER,
        status TEXT DEFAULT 'pending',
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS resources (
        id SERIAL PRIMARY KEY,
        task_id INTEGER,
        title TEXT,
        url TEXT,
        type TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS courses (
        id SERIAL PRIMARY KEY,
        name TEXT,
        code TEXT,
        student_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS course_materials (
        id SERIAL PRIMARY KEY,
        course_code TEXT,
        course_name TEXT,
        week_number INTEGER,
        title TEXT,
        filepath TEXT,
        student_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        file_hash TEXT,
        content TEXT
    )''')
    # 已有表加 content 字段（兼容旧版本）
    try:
        c.execute("ALTER TABLE course_materials ADD COLUMN IF NOT EXISTS content TEXT")
    except:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS delete_requests (
        id SERIAL PRIMARY KEY,
        task_id INTEGER,
        student_id INTEGER,
        reason TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS submissions (
        id SERIAL PRIMARY KEY,
        task_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        submission_type TEXT NOT NULL,
        filename TEXT,
        filepath TEXT,
        comment TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS parent_student (
        id SERIAL PRIMARY KEY,
        parent_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS chat_history (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        session_key TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS timetable_entries (
        id SERIAL PRIMARY KEY,
        student_id INTEGER NOT NULL,
        course_name TEXT NOT NULL,
        course_code TEXT,
        day_of_week INTEGER NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        location TEXT,
        lecturer TEXT,
        color TEXT DEFAULT '#4A90D9'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS moodle_content (
        id SERIAL PRIMARY KEY,
        student_id INTEGER NOT NULL,
        course_code TEXT,
        course_name TEXT,
        content_type TEXT,
        title TEXT NOT NULL,
        body TEXT,
        due_date TEXT,
        is_processed BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # 创建默认账号
    for uname, pwd, role in [
        ('teacher', 'teacher1yunze', 'teacher'),
        ('teacher2', 'teacher2yunze', 'teacher'),
        ('student', '8888', 'student'),
        ('parent', 'jiazhang123', 'parent'),
    ]:
        c.execute("""
            INSERT INTO users (username, password, role) VALUES (%s, %s, %s)
            ON CONFLICT (username) DO UPDATE SET password=%s
        """, (uname, pwd, role, pwd))

    # 绑定家长和学生
    c.execute("SELECT id FROM users WHERE username='parent'")
    parent_row = c.fetchone()
    c.execute("SELECT id FROM users WHERE username='student'")
    student_row = c.fetchone()
    if parent_row and student_row:
        c.execute("""
            INSERT INTO parent_student (parent_id, student_id)
            SELECT %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM parent_student WHERE parent_id=%s AND student_id=%s
            )
        """, (parent_row[0], student_row[0], parent_row[0], student_row[0]))

    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM app_settings WHERE key=%s", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default


def set_setting(key, value):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO app_settings (key, value) VALUES (%s, %s)
        ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=CURRENT_TIMESTAMP
    """, (key, str(value)))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()