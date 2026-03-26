import sqlite3
from datetime import datetime

conn = sqlite3.connect("learning_platform.db")
c = conn.cursor()

# 查找所有2025年的日期
c.execute("SELECT id, title, due_date FROM tasks WHERE due_date LIKE '2025-%'")
tasks = c.fetchall()

if not tasks:
    print("没有找到2025年的任务日期，无需修正")
else:
    print(f"找到 {len(tasks)} 条需要修正的记录：")
    for task in tasks:
        old_date = task[2]
        new_date = old_date.replace("2025", "2026", 1)
        print(f"  任务ID {task[0]}: 「{task[1]}」 {old_date} → {new_date}")

    confirm = input("\n确认修正以上日期？(输入 yes 继续): ")
    if confirm.strip().lower() == "yes":
        for task in tasks:
            new_date = task[2].replace("2025", "2026", 1)
            c.execute("UPDATE tasks SET due_date=? WHERE id=?", (new_date, task[0]))
        conn.commit()
        print("✅ 修正完成")
    else:
        print("已取消")

conn.close()