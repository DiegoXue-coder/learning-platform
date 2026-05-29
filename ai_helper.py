from database import get_conn
import requests
import os
import re
import json
from datetime import datetime
from parse_course import read_pdf

import streamlit as st
from dotenv import load_dotenv
load_dotenv()

try:
    API_KEY = st.secrets["ANTHROPIC_API_KEY"]
except:
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
    if "content" not in result:
        print("API错误:", result)
        return ""
    return next(
        (block["text"] for block in result["content"] if block.get("type") == "text"),
        ""
    )

@st.cache_data(ttl=300)
def get_student_task_summary(user_id):
    status_map = {"pending": "未开始", "in_progress": "进行中", "completed": "已完成"}

    # 任务列表
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT t.id, t.title, t.subject, t.due_date, t.description,
               COALESCE(p.status, 'pending') as status
        FROM tasks t
        LEFT JOIN progress p ON t.id = p.task_id AND p.student_id = %s
        ORDER BY t.due_date
    """, (user_id,))
    task_data = c.fetchall()

    # 课程资料库（同一个连接）
    c.execute("""
        SELECT course_code, course_name, week_number, title, filepath, content
        FROM course_materials
        WHERE student_id = %s
        ORDER BY course_code, week_number
    """, (user_id,))
    materials = c.fetchall()
    conn.close()

    task_summary = ""
    for t in task_data:
        task_summary += f"- 任务：{t[1]}，学科：{t[2]}，截止：{t[3]}，状态：{status_map.get(t[5], t[5])}，说明：{t[4]}\n"

    if materials:
        readable = []
        unreadable = []
        for m in materials:
            course_code, course_name, week_number, title, filepath, db_content = m
            week_str = f"第{week_number}周" if week_number else "未知周次"
            label = f"【{course_name}（{course_code}）{week_str}】{title}"

            # 优先从数据库 content 字段读取
            if db_content:
                readable.append(f"\n{label}\n内容摘要：{db_content[:2000]}\n")
            elif filepath and os.path.exists(filepath):
                pdf_text = read_pdf(filepath)
                if pdf_text:
                    readable.append(f"\n{label}\n内容摘要：{pdf_text[:2000]}\n")
                else:
                    unreadable.append(label)
            else:
                unreadable.append(label)

        if readable:
            task_summary += "\n\n=== 课程资料库（以下是真实文件内容）===\n"
            task_summary += "".join(readable)

        if unreadable:
            task_summary += "\n\n=== 课程资料库（以下文件内容暂无法读取）===\n"
            task_summary += "\n".join(f"- {u}" for u in unreadable)
            task_summary += "\n重要规则：以上文件内容无法读取，绝对不要编造内容，直接告诉用户文件暂时无法读取。\n"

    return task_summary

def get_teacher_progress_summary():
    conn = get_conn()
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
    status_map = {"pending": "未开始", "in_progress": "进行中", "completed": "已完成"}
    return "\n".join([
        f"- 任务：{r[0]}，学科：{r[1]}，截止：{r[2]}，学生：{r[3]}，进度：{status_map.get(r[4], r[4])}"
        for r in progress_data
    ])

def smart_classify_files(none_files, existing_courses):
    files_summary = ""
    for f in none_files:
        # 优先从数据库读content
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT content FROM course_materials WHERE id=%s", (f[0],))
        row = c.fetchone()
        conn.close()
        pdf_text = row[0] if row and row[0] else read_pdf(f[2])
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
    text = next(
        (block["text"] for block in result.get("content", []) if block.get("type") == "text"),
        ""
    )

    try:
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except:
        pass
    return None