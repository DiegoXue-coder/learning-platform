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
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
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

    # 预留资源表（以后推送文章视频用）
    c.execute('''CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        title TEXT,
        url TEXT,
        type TEXT
    )''')

    # 创建默认账号
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('teacher', 'teacher123', 'teacher')")
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('student', 'student123', 'student')")

    conn.commit()
    conn.close()
    print("数据库初始化完成")

if __name__ == "__main__":
    init_db()