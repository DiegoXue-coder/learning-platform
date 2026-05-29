import streamlit as st
import json
import re
from database import get_conn
from ai_helper import call_claude


def _extract_text(html_content):
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            tag.decompose()
        return soup.get_text(separator='\n', strip=True)
    except ImportError:
        text = re.sub(r'<[^>]+>', ' ', html_content)
        return re.sub(r'\s+', '\n', text).strip()


def _parse_with_claude(text, course_hint=""):
    hint = f"\n课程提示：{course_hint}" if course_hint else ""
    prompt = (
        f"以下是从 Moodle 课程页面提取的文字内容，请分析并提取结构化信息。{hint}\n\n"
        "返回JSON格式（只返回JSON，不要其他文字）：\n"
        '{"course_name":"完整课程名","course_code":"课程代码如COMP1511（无则空字符串）","items":['
        '{"type":"announcement|assignment|resource|quiz","title":"标题",'
        '"body":"内容摘要不超过150字","due_date":"截止日期YYYY-MM-DD（无则空字符串）"}]}\n\n'
        f"页面内容（前6000字）：\n{text[:6000]}"
    )
    result = call_claude(
        "你是专业的 Moodle 课程内容解析助手，擅长提取作业、公告和资料信息。",
        [{"role": "user", "content": prompt}],
        max_tokens=3000
    )
    m = re.search(r'\{.*\}', result, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return None


def _save_items(student_id, course_name, course_code, items):
    conn = get_conn()
    c = conn.cursor()
    saved = 0
    for item in items:
        c.execute(
            "SELECT id FROM moodle_content WHERE student_id=%s AND title=%s AND course_code=%s",
            (student_id, item.get('title', ''), course_code or '')
        )
        if c.fetchone():
            continue
        c.execute("""
            INSERT INTO moodle_content (student_id, course_code, course_name, content_type, title, body, due_date)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            student_id, course_code or '', course_name,
            item.get('type', 'resource'),
            item.get('title', '未命名'),
            item.get('body', ''),
            item.get('due_date') or None
        ))
        saved += 1
    conn.commit()
    conn.close()
    return saved


def _create_tasks(student_id, course_name, course_code, items):
    conn = get_conn()
    c = conn.cursor()
    created = 0
    for item in items:
        if item.get('type') == 'assignment' and item.get('due_date'):
            c.execute("SELECT id FROM tasks WHERE title=%s AND created_by=%s",
                      (item['title'], student_id))
            if c.fetchone():
                continue
            body = item.get('body', '')
            desc = f"{body}\n\n[来源: Moodle — {course_name}]" if body else f"[来源: Moodle — {course_name}]"
            c.execute("""
                INSERT INTO tasks (title, description, due_date, subject, created_by)
                VALUES (%s,%s,%s,%s,%s) RETURNING id
            """, (item['title'], desc, item['due_date'], course_code or course_name, student_id))
            task_id = c.fetchone()[0]
            # Add initial progress record
            c.execute("SELECT id FROM progress WHERE student_id=%s AND task_id=%s",
                      (student_id, task_id))
            if not c.fetchone():
                c.execute("INSERT INTO progress (student_id, task_id, status) VALUES (%s,%s,'pending')",
                          (student_id, task_id))
            created += 1
    conn.commit()
    conn.close()
    return created


def show_moodle_import(user):
    student_id = user['id']

    st.write("### 🔗 Moodle 课程内容导入")

    tab_auto, tab_manual = st.tabs(["🤖 自动抓取（推荐）", "📄 手动上传 HTML"])

    with tab_auto:
        _show_auto_fetch(user)

    with tab_manual:
        _show_manual_upload(user)


def _show_auto_fetch(user):
    student_id = user['id']
    from moodle_scraper import (
        DEFAULT_MOODLE_URL,
        cookie_verify, cookie_get_courses, cookie_fetch_course_items,
    )
    from database import get_setting, set_setting

    moodle_url = get_setting(f"moodle_url_{student_id}", DEFAULT_MOODLE_URL)
    stored_cookie = get_setting(f"moodle_cookie_{student_id}", "")

    # ── 状态检测：已存 Cookie 则自动验证 ──────────────────────────
    if stored_cookie and "mc_verified" not in st.session_state:
        with st.spinner("正在自动验证 Moodle 连接..."):
            try:
                if cookie_verify(moodle_url, stored_cookie):
                    courses = cookie_get_courses(moodle_url, stored_cookie)
                    st.session_state["mc_courses"] = courses
                    st.session_state["mc_auth"] = {"mode": "cookie", "cookie": stored_cookie, "url": moodle_url}
                    st.session_state["mc_verified"] = True
                else:
                    # Cookie expired
                    set_setting(f"moodle_cookie_{student_id}", "")
                    st.session_state["mc_need_reauth"] = True
            except Exception:
                st.session_state["mc_need_reauth"] = True

    # ── 已连接状态 ────────────────────────────────────────────────
    if st.session_state.get("mc_verified") and st.session_state.get("mc_courses") is not None:
        courses = st.session_state["mc_courses"]
        st.success(f"✅ Moodle 已连接 — 找到 **{len(courses)}** 门课程")
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("断开重连", key="mc_disconnect"):
                set_setting(f"moodle_cookie_{student_id}", "")
                for k in ["mc_verified", "mc_courses", "mc_auth", "mc_need_reauth", "mc_fetched"]:
                    st.session_state.pop(k, None)
                st.rerun()

    # ── 未连接 / Cookie 过期 → 显示引导流程 ─────────────────────
    elif not stored_cookie or st.session_state.get("mc_need_reauth"):
        if st.session_state.get("mc_need_reauth"):
            st.warning("⚠️ Moodle 登录已过期，请重新连接")

        st.markdown("""
<div style="background:#f0f7ff;border:1px solid #b3d4f5;border-radius:10px;padding:16px 20px;margin-bottom:12px">
<strong>🔗 连接你的 UNSW Moodle — 只需操作一次</strong><br>
按以下步骤获取登录凭证，之后平台会自动保持连接。
</div>
""", unsafe_allow_html=True)

        # Step 1: open Moodle
        st.markdown("**第 1 步：在新标签页打开 Moodle 并登录**")
        st.markdown(
            '<a href="https://moodle.telt.unsw.edu.au" target="_blank">'
            '<button style="background:#1e40af;color:white;border:none;padding:8px 20px;'
            'border-radius:6px;cursor:pointer;font-size:14px">🌐 打开 UNSW Moodle</button></a>',
            unsafe_allow_html=True
        )
        st.write("")

        # Step 2: instructions with visual
        st.markdown("**第 2 步：获取 Cookie 值（选一种方法）**")

        # Bookmarklet approach
        bookmarklet = (
            "javascript:(function(){"
            "var d=document.cookie.match(/MoodleSession=([^;]+)/);"
            "if(d){var el=document.createElement('div');"
            "el.style='position:fixed;top:20px;left:50%;transform:translateX(-50%);"
            "background:white;border:2px solid #1e40af;border-radius:10px;"
            "padding:20px;z-index:99999;box-shadow:0 4px 20px rgba(0,0,0,0.3);min-width:400px';"
            "el.innerHTML='<b style=color:#1e40af>MoodleSession Cookie</b><br><br>"
            "<textarea style=\"width:100%;height:60px;font-size:11px\" onclick=this.select()>'+d[1]+'</textarea>"
            "<br><small>点击文本框全选，然后 Ctrl+C 复制</small>"
            "<br><br><button onclick=this.parentNode.remove() "
            "style=\"background:#1e40af;color:white;border:none;padding:6px 16px;border-radius:6px;cursor:pointer\">"
            "关闭</button>';"
            "document.body.appendChild(el);"
            "} else {"
            "alert('Cookie 被浏览器保护，无法直接读取。\\n请用备用方法（见下方说明）。');"
            "}"
            "})();"
        )

        st.markdown(f"""
<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;margin:8px 0">
<b>⭐ 方法一：书签工具（最简单）</b><br>
<small>把下面的按钮<b>拖到浏览器书签栏</b>，然后在 Moodle 页面点击它，自动弹出 Cookie 值。</small><br><br>
<a href="{bookmarklet}"
   style="background:#1e40af;color:white;padding:8px 16px;border-radius:6px;
          text-decoration:none;font-size:13px;display:inline-block">
📌 Moodle Cookie 助手
</a>
&nbsp;<small style="color:#64748b">← 把这个拖到书签栏</small>
</div>

<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;margin:8px 0">
<b>🔧 方法二：手动（书签不能用时）</b><br>
在 Moodle 页面按 <b>F12</b>，然后：<br>
• <b>Chrome/Edge</b>：顶部找 <b>Application</b> 标签（可能藏在 <code>>></code> 里）→ 左侧 Cookies → 找 MoodleSession<br>
• <b>Firefox</b>：顶部找 <b>Storage</b> 标签 → Cookies → 找 MoodleSession<br>
• <b>Safari</b>：先去 Safari 偏好设置 → 高级 → 勾选「在菜单栏显示开发菜单」→ 开发 → 显示 Web 检查器 → 存储
</div>
""", unsafe_allow_html=True)

        # Step 3: paste
        st.markdown("**第 3 步：粘贴并连接**")
        cookie_input = st.text_input(
            "粘贴 MoodleSession 值",
            type="password",
            key="mc_cookie_input",
            placeholder="eyJ... 或 一串随机字符"
        )

        if st.button("✅ 连接 Moodle", type="primary", key="mc_connect_btn", disabled=not cookie_input):
            with st.spinner("正在验证并获取课程列表..."):
                try:
                    if not cookie_verify(moodle_url, cookie_input):
                        st.error("Cookie 无效或已过期，请确认已在 Moodle 登录，并重新复制")
                    else:
                        courses = cookie_get_courses(moodle_url, cookie_input)
                        set_setting(f"moodle_url_{student_id}", moodle_url)
                        set_setting(f"moodle_cookie_{student_id}", cookie_input)
                        st.session_state["mc_courses"] = courses
                        st.session_state["mc_auth"] = {"mode": "cookie", "cookie": cookie_input, "url": moodle_url}
                        st.session_state["mc_verified"] = True
                        st.session_state.pop("mc_need_reauth", None)
                        st.success(f"✅ 连接成功！找到 {len(courses)} 门课程")
                        st.rerun()
                except Exception as e:
                    st.error(f"连接失败：{e}")
        return  # Don't show course list until connected

    # Course selection & fetch
    if st.session_state.get("mc_courses"):
        courses = st.session_state["mc_courses"]
        auth = st.session_state["mc_auth"]

        st.divider()
        st.write("#### 选择要导入的课程")

        options = {f"{c['fullname']} ({c.get('shortname','')})": c for c in courses}
        selected_labels = st.multiselect("选择课程（可多选）", list(options.keys()), key="mc_selected")

        if selected_labels and st.button("⬇️ 开始抓取选中课程", type="primary", key="mc_fetch"):
            all_results = {}
            for label in selected_labels:
                course = options[label]
                with st.spinner(f"正在抓取：{course['fullname']}..."):
                    try:
                        items = cookie_fetch_course_items(
                            auth["url"], auth["cookie"], str(course["id"]), course["fullname"])
                        all_results[label] = {"course": course, "items": items}
                    except Exception as e:
                        st.error(f"{course['fullname']} 抓取失败：{e}")

            if all_results:
                st.session_state["mc_fetched"] = all_results

    # Preview & confirm
    if st.session_state.get("mc_fetched"):
        fetched = st.session_state["mc_fetched"]
        st.divider()
        st.write("#### 抓取结果预览")

        for label, data in fetched.items():
            course = data["course"]
            items = data["items"]
            assignments = [i for i in items if i.get("type") == "assignment"]
            others = [i for i in items if i.get("type") != "assignment"]

            with st.expander(f"📘 {label} — {len(items)} 条内容", expanded=True):
                if assignments:
                    st.write(f"**📝 作业 {len(assignments)} 项**（有截止日期的自动创建任务）")
                    for a in assignments:
                        due = f" ｜ ⏰ {a['due_date']}" if a.get("due_date") else ""
                        st.write(f"- {a['title']}{due}")
                if others:
                    st.write(f"**📁 其他内容 {len(others)} 项**")
                    for o in others[:5]:
                        icon = "📢" if o.get("type") == "announcement" else "📄"
                        st.write(f"- {icon} {o['title']}")
                    if len(others) > 5:
                        st.caption(f"...还有 {len(others)-5} 项")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ 全部导入", type="primary", key="mc_confirm_auto"):
                total_saved, total_tasks = 0, 0
                for label, data in fetched.items():
                    course = data["course"]
                    cname = course["fullname"]
                    ccode = course.get("shortname", "")
                    saved = _save_items(student_id, cname, ccode, data["items"])
                    created = _create_tasks(student_id, cname, ccode, data["items"])
                    total_saved += saved
                    total_tasks += created
                del st.session_state["mc_fetched"]
                st.success(f"✅ 导入完成：{total_saved} 条内容，{total_tasks} 个任务已创建")
                st.rerun()
        with col2:
            if st.button("取消", key="mc_cancel_auto"):
                del st.session_state["mc_fetched"]
                st.rerun()


def _show_manual_upload(user):
    student_id = user['id']

    with st.expander("📖 使用说明", expanded=False):
        st.markdown("""
1. 在浏览器中打开你的 **Moodle 课程页面**
2. 按 **Ctrl+S**（Mac: **Cmd+S**），选择保存类型为「**仅 HTML（.htm/.html）**」
3. 上传保存的 `.html` 文件
4. AI 自动提取：课程公告、作业（含截止日期）、资料列表
5. 确认后：内容存入资料库，**有截止日期的作业自动创建任务**
""")

    course_hint = st.text_input(
        "课程代码提示（可选，帮助 AI 识别，如 COMP1511）",
        key="mc_hint",
        placeholder="COMP1511"
    )
    uploaded = st.file_uploader(
        "上传 Moodle 课程页面 HTML 文件",
        type=["html", "htm"],
        key="mc_file"
    )

    if uploaded:
        st.caption(f"已选择：{uploaded.name} ({uploaded.size // 1024} KB)")
        if st.button("🤖 AI 解析内容", type="primary"):
            with st.spinner("AI 正在解析 Moodle 内容，请稍候..."):
                content = uploaded.read().decode('utf-8', errors='ignore')
                text = _extract_text(content)
                if len(text.strip()) < 50:
                    st.error("无法从文件中提取内容，请确认保存的是 HTML 文件")
                    st.stop()
                parsed = _parse_with_claude(text, course_hint)

            if parsed:
                st.session_state['mc_parsed'] = parsed
            else:
                st.error("解析失败，请重试或检查文件是否完整")

    if st.session_state.get('mc_parsed'):
        parsed = st.session_state['mc_parsed']
        items = parsed.get('items', [])
        cname = parsed.get('course_name', '未知课程')
        ccode = parsed.get('course_code', '')

        st.write(f"### 解析结果：{(ccode + ' ') if ccode else ''}{cname}")

        assignments = [i for i in items if i.get('type') == 'assignment']
        announcements = [i for i in items if i.get('type') == 'announcement']
        resources = [i for i in items if i.get('type') not in ('assignment', 'announcement')]

        if assignments:
            st.write(f"**📝 作业（{len(assignments)} 项）** — 有截止日期的将自动创建任务")
            for a in assignments:
                due = f" ｜ ⏰ 截止: **{a['due_date']}**" if a.get('due_date') else " ｜ 无截止日期"
                st.write(f"- {a['title']}{due}")
                if a.get('body'):
                    st.caption(f"  {a['body'][:120]}")

        if announcements:
            st.write(f"**📢 公告（{len(announcements)} 项）**")
            for a in announcements:
                st.write(f"- {a['title']}")

        if resources:
            st.write(f"**📁 其他资料（{len(resources)} 项）**")
            for r in resources:
                st.write(f"- {r['title']}")

        if not items:
            st.warning("未提取到任何内容，建议检查 HTML 文件格式或尝试重新保存页面")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ 确认导入", type="primary"):
                saved = _save_items(student_id, cname, ccode, items)
                created = _create_tasks(student_id, cname, ccode, items)
                del st.session_state['mc_parsed']
                st.success(f"✅ 导入完成：{saved} 条内容已保存，{created} 个作业任务已自动创建")
                st.rerun()
        with col2:
            if st.button("取消", key="mc_cancel"):
                del st.session_state['mc_parsed']
                st.rerun()

    # Show existing Moodle content history
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT course_name, course_code, content_type, title, due_date, created_at
        FROM moodle_content WHERE student_id=%s ORDER BY created_at DESC
    """, (student_id,))
    history = c.fetchall()
    conn.close()

    if history:
        st.divider()
        st.write("### 已导入的 Moodle 内容")

        by_course = {}
        for row in history:
            key = row[1] or row[0]
            if key not in by_course:
                by_course[key] = {"name": row[0], "code": row[1], "items": []}
            by_course[key]["items"].append(row)

        icons = {"announcement": "📢", "assignment": "📝", "resource": "📁", "quiz": "📊"}
        for key, course in by_course.items():
            label = f"📘 {course['code'] + ' ' if course['code'] else ''}{course['name']} — {len(course['items'])} 条"
            with st.expander(label):
                for item in course["items"]:
                    icon = icons.get(item[2], '📌')
                    due = f" | {item[4]}" if item[4] else ""
                    st.write(f"{icon} {item[3]}{due}")
