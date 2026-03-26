import requests
import sqlite3
import os
import re
import json
from datetime import datetime
from parse_course import read_pdf

import os
from dotenv import load_dotenv
load_dotenv()
API_KEY = os.getenv("ANTHROPIC_API_KEY")

def call_claude(system_prompt, messages, max_tokens=1024):
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-opus-4-5",
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": messages
        }
    )
    result = response.json()
    return result["content"][0]["text"]

def get_student_task_summary(user_id):
    status_map = {"pending": "未开始", "in_progress": "进行中", "completed": "已完成"}
    conn = sqlite3.connect("learning_platform.db")
    c = conn.cursor()
    c.execute("""
        SELECT t.id, t.title, t.subject, t.due_date, t.description,
               COALESCE(p.status, 'pending') as status
        FROM tasks t
        LEFT JOIN progress p ON t.id = p.task_id AND p.student_id = ?
        ORDER BY t.due_date
    """, (user_id,))
    task_data = c.fetchall()
    conn.close()

    task_summary = ""
    for t in task_data:
        task_summary += f"- 任务：{t[1]}，学科：{t[2]}，截止：{t[3]}，状态：{status_map.get(t[5], t[5])}，说明：{t[4]}\n"
        conn = sqlite3.connect("learning_platform.db")
        c = conn.cursor()
        c.execute("SELECT filepath FROM task_files WHERE task_id=?", (t[0],))
        files = c.fetchall()
        conn.close()
        for f in files:
            if os.path.exists(f[0]):
                pdf_text = read_pdf(f[0])
                if pdf_text:
                    task_summary += f"  附件内容：{pdf_text}\n"
    return task_summary

def get_teacher_progress_summary():
    status_map = {"pending": "未开始", "in_progress": "进行中", "completed": "已完成"}
    conn = sqlite3.connect("learning_platform.db")
    c = conn.cursor()
    c.execute("""
        SELECT t.title, t.subject, t.due_date,
               u.username,
               COALESCE(p.status, 'pending') as status
        FROM tasks t
        CROSS JOIN users u
        LEFT JOIN progress p ON t.id = p.task_id AND p.student_id = u.id
        WHERE u.role = 'student'
        ORDER BY t.due_date
    """)
    progress_data = c.fetchall()
    conn.close()
    return "\n".join([
        f"- 任务：{r[0]}，学科：{r[1]}，截止：{r[2]}，学生：{r[3]}，进度：{status_map.get(r[4], r[4])}"
        for r in progress_data
    ])

def smart_classify_files(none_files, existing_courses):
    files_summary = ""
    for f in none_files:
        pdf_text = read_pdf(f[2])
        files_summary += f"文件ID:{f[0]} 文件名:{f[1]}\n内容摘要:{pdf_text[:500]}\n\n"

    courses_summary = "\n".join([f"- {c[0]}: {c[1]}" for c in existing_courses])
    if not courses_summary:
        courses_summary = "暂无已有课程"

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-opus-4-5",
            "max_tokens": 2000,
            "messages": [{
                "role": "user",
                "content": f"""以下是一些未能自动归类的课程文件，请根据文件内容判断它们最可能属于哪门课程。

已有课程列表：
{courses_summary}

未归类文件：
{files_summary}

请严格按照以下JSON格式返回，不要返回其他文字：

{{
  "classifications": [
    {{
      "file_id": 文件ID数字,
      "suggested_course_code": "建议的课程代码，如果无法匹配任何已有课程则填null",
      "suggested_course_name": "建议的课程名称",
      "confidence": "high/medium/low",
      "reason": "简短说明理由"
    }}
  ]
}}"""
            }]
        }
    )

    result = response.json()
    text = result["content"][0]["text"]

    try:
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except:
        pass
    return None