import sqlite3

def init_db():
    conn = sqlite3.connect("learning_platform.db")
    c = conn.cursor()

    # 用户表
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )''')

    # 任务表
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        due_date TEXT,
        subject TEXT,
        created_by INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        course_id INTEGER,
        video_url TEXT
    )''')

    # 任务文件表
    c.execute('''CREATE TABLE IF NOT EXISTS task_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        filename TEXT,
        filepath TEXT
    )''')

    # 学生进度表
    c.execute('''CREATE TABLE IF NOT EXISTS progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        task_id INTEGER,
        status TEXT DEFAULT 'pending',
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    # 资源表
    c.execute('''CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        title TEXT,
        url TEXT,
        type TEXT
    )''')

    # 课程表
    c.execute('''CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        code TEXT,
        student_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    # 课程资料表
    c.execute('''CREATE TABLE IF NOT EXISTS course_materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT,
        course_name TEXT,
        week_number INTEGER,
        title TEXT,
        filepath TEXT,
        student_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        file_hash TEXT
    )''')

    # 删除申请表
    c.execute('''CREATE TABLE IF NOT EXISTS delete_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        student_id INTEGER,
        reason TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    # 提交表
    c.execute('''CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        submission_type TEXT NOT NULL,
        filename TEXT,
        filepath TEXT,
        comment TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    # 家长学生关联表
    c.execute('''CREATE TABLE IF NOT EXISTS parent_student (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    # 创建或更新默认账号
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('teacher', 'teacher1yunze', 'teacher')")
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('teacher2', 'teacher2yunze', 'teacher')")
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('student', '8888', 'student')")
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('parent', 'jiazhang123', 'parent')")

    # 强制更新密码（确保云端密码正确）
    c.execute("UPDATE users SET password='teacher1yunze' WHERE username='teacher'")
    c.execute("UPDATE users SET password='teacher2yunze' WHERE username='teacher2'")
    c.execute("UPDATE users SET password='8888' WHERE username='student'")
    c.execute("UPDATE users SET password='jiazhang123' WHERE username='parent'")

    # 绑定家长和学生
    c.execute("INSERT OR IGNORE INTO parent_student (parent_id, student_id) VALUES (3, 2)")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
