import hashlib
import requests
import PyPDF2
import re
import json
from datetime import datetime

import os
import streamlit as st
from dotenv import load_dotenv
load_dotenv()

try:
    API_KEY = st.secrets["ANTHROPIC_API_KEY"]
except:
    API_KEY = os.getenv("ANTHROPIC_API_KEY")

def get_file_hash(filepath):
    md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5.update(chunk)
    return md5.hexdigest()

def read_pdf(filepath):
    try:
        reader = PyPDF2.PdfReader(filepath)
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += re.sub(r'[^\x00-\x7F]+', ' ', t)
        return text
    except:
        return ""

def parse_course_outline(pdf_text, filename=""):
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-opus-4-5",
            "max_tokens": 3000,
            "messages": [
                {
                    "role": "user",
                    "content": f"""请分析以下课程文件,提取所有信息。

严格按照以下 JSON 格式返回,不要返回其他任何文字:

{{
  "course_name": "课程全名",
  "course_code": "课程代码,比如INFS3604",
  "week_number": 周数数字,没有则填null,
  "material_type": "课件/作业说明/课程大纲/其他",
  "has_tasks": true或false,
  "tasks": [
    {{
      "title": "任务名称",
      "type": "作业/考试/项目/其他",
      "due_date": "截止日期,格式YYYY-MM-DD,没有则填null",
      "description": "简短说明"
    }}
  ]
}}

重要规则:
- 课程代码通常是字母+数字组合,比如INFS3700、COMP1234
- 优先从文件名里提取课程代码,文件名是最可靠的来源
- 课程名是这门课自己的名称,不是文件里引用的外部教材名
- 如果文件内容引用了外部教材（比如教科书）,不要把教材名当成课程名
- week_number 从文件名或内容中提取周数
- 即使是课件,如果里面提到了任何作业、考试、提交日期,都要提取到tasks里
- has_tasks 只有在tasks列表不为空且至少一个任务有due_date时才为true

文件名:{filename}

课程文件内容:
{pdf_text[:5000]}"""
                }
            ]
        }
    )

    result = response.json()
    if "content" not in result:
        print("API错误:", result)
        return None

    text = next(
        (block["text"] for block in result["content"] if block.get("type") == "text"),
        ""
    )

    try:
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())

            # 校正年份
            current_year = datetime.now().year
            for task in parsed.get("tasks", []):
                if task.get("due_date"):
                    try:
                        due = datetime.strptime(task["due_date"], "%Y-%m-%d").date()
                        if due.year < current_year:
                            task["due_date"] = task["due_date"].replace(
                                str(due.year), str(due.year + 1), 1
                            )
                    except:
                        pass

            return parsed
    except:
        pass
    return None
