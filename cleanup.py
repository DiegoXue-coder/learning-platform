import sqlite3
conn = sqlite3.connect("learning_platform.db")

# 更新密码
conn.execute("UPDATE users SET password='teacher1yunze' WHERE username='teacher'")

# 添加第二个老师
conn.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('teacher2', 'teacher2yunze', 'teacher')")

# 更新学生密码
conn.execute("UPDATE users SET password='8888' WHERE username='student'")

# 更新家长密码
conn.execute("UPDATE users SET password='jiazhang123' WHERE username='parent'")

conn.commit()
print("完成")

# 验证
users = conn.execute("SELECT id, username, password, role FROM users").fetchall()
for u in users:
    print(u)
conn.close()