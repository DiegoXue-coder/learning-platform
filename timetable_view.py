import streamlit as st
import base64
import json
import re
from database import get_conn
from ai_helper import call_claude

COLORS = ['#4A90D9', '#E87C3E', '#5BB85D', '#9B59B6', '#E74C3C', '#1ABC9C', '#F39C12', '#E91E8C']
DAY_NAMES = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']


def _get_entries(student_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT id, course_name, course_code, day_of_week, start_time, end_time, location, lecturer, color
        FROM timetable_entries WHERE student_id=%s ORDER BY day_of_week, start_time
    """, (student_id,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "course_name": r[1], "course_code": r[2], "day_of_week": r[3],
             "start_time": r[4], "end_time": r[5], "location": r[6], "lecturer": r[7], "color": r[8]}
            for r in rows]


def _get_course_colors(entries):
    keys = list(dict.fromkeys((e['course_code'] or e['course_name']) for e in entries))
    return {k: COLORS[i % len(COLORS)] for i, k in enumerate(keys)}


def _render_timetable_html(entries):
    if not entries:
        return ""

    course_colors = _get_course_colors(entries)

    slots = []
    for h in range(8, 21):
        slots.append(f"{h:02d}:00")
        slots.append(f"{h:02d}:30")

    html = """<style>
.tt-wrap{overflow-x:auto;margin:4px 0}
.tt{width:100%;border-collapse:collapse;font-size:12px;min-width:520px}
.tt th{background:#21262d;color:#8b949e;padding:8px 6px;text-align:center;font-weight:600;border:1px solid #30363d}
.tt td{border:1px solid #1e2128;height:22px;padding:0;vertical-align:top;background:#0d1117}
.tt-time{background:#161b22!important;color:#484f58;font-size:10px;text-align:right;padding:0 6px;white-space:nowrap;width:48px}
.cb{padding:2px 5px;height:100%;box-sizing:border-box;overflow:hidden}
.cb-code{font-weight:700;font-size:11px;color:white;line-height:1.3}
.cb-name{font-size:9px;color:rgba(255,255,255,0.85)}
.cb-loc{font-size:9px;color:rgba(255,255,255,0.7)}
</style>
<div class="tt-wrap"><table class="tt">
<tr><th>时间</th><th>周一</th><th>周二</th><th>周三</th><th>周四</th><th>周五</th></tr>
"""
    for slot in slots:
        time_label = slot if slot.endswith(':00') else ''
        html += f'<tr><td class="tt-time">{time_label}</td>'

        for day in range(5):
            active = [e for e in entries
                      if e['day_of_week'] == day and e['start_time'] <= slot < e['end_time']]

            if active:
                e = active[0]
                key = e['course_code'] or e['course_name']
                color = course_colors.get(key, '#4A90D9')

                if e['start_time'] == slot:
                    code = e.get('course_code', '')
                    name = e.get('course_name', '')
                    loc = e.get('location', '')
                    inner = f'<div class="cb-code">{code or name}</div>'
                    if code and name and name != code:
                        inner += f'<div class="cb-name">{name}</div>'
                    if loc:
                        inner += f'<div class="cb-loc">📍{loc}</div>'
                    html += f'<td><div class="cb" style="background:{color}">{inner}</div></td>'
                else:
                    html += f'<td style="background:{color}55;border-left:2px solid {color}"></td>'
            else:
                html += '<td></td>'

        html += '</tr>\n'

    html += '</table></div>'
    return html


def _parse_timetable_image(b64_data, media_type):
    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64_data}},
            {"type": "text", "text": (
                "请分析这张课程表图片，提取所有课程信息。以JSON数组格式返回：\n"
                '[{"course_name":"课程名","course_code":"课程代码（如COMP1511，无则空字符串）",'
                '"day_of_week":0,"start_time":"09:00","end_time":"11:00","location":"地点","lecturer":"教师（无则空）"}]\n'
                "day_of_week: 0=周一,1=周二,2=周三,3=周四,4=周五,5=周六\n"
                "时间用24小时制HH:MM格式。只返回JSON数组，不要其他文字。"
            )}
        ]
    }]
    result = call_claude("你是专业课程表解析助手。", messages, max_tokens=2048)
    m = re.search(r'\[.*\]', result, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return []


def _save_entries(student_id, entries):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM timetable_entries WHERE student_id=%s", (student_id,))
    color_map = {}
    for e in entries:
        key = e.get('course_code') or e.get('course_name', '')
        if key not in color_map:
            color_map[key] = COLORS[len(color_map) % len(COLORS)]
        c.execute("""
            INSERT INTO timetable_entries
            (student_id, course_name, course_code, day_of_week, start_time, end_time, location, lecturer, color)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (student_id, e.get('course_name', ''), e.get('course_code', ''),
              int(e.get('day_of_week', 0)), e.get('start_time', '09:00'),
              e.get('end_time', '10:00'), e.get('location', ''), e.get('lecturer', ''),
              color_map[key]))
    conn.commit()
    conn.close()


def _show_course_detail(course_key, entries, student_id):
    course_entries = [e for e in entries if (e['course_code'] or e['course_name']) == course_key]
    if not course_entries:
        return

    e0 = course_entries[0]
    colors = _get_course_colors(entries)
    color = colors.get(course_key, '#4A90D9')

    st.markdown(
        f'<div style="border-left:4px solid {color};padding:8px 14px;'
        f'background:{color}18;border-radius:4px;margin:10px 0">'
        f'<strong style="font-size:16px">'
        f'{(e0.get("course_code") or "") + " " if e0.get("course_code") else ""}{e0["course_name"]}'
        f'</strong>'
        f'{"<br><small style=color:#888>" + e0["lecturer"] + "</small>" if e0.get("lecturer") else ""}'
        f'</div>',
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)
    with col1:
        st.write("**上课时间**")
        for e in course_entries:
            st.write(f"- {DAY_NAMES[e['day_of_week']]} {e['start_time']}–{e['end_time']} @ {e.get('location') or '未知'}")

    with col2:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT title, content_type, due_date FROM moodle_content
            WHERE student_id=%s AND (course_code=%s OR course_name=%s)
            ORDER BY created_at DESC LIMIT 6
        """, (student_id, e0.get('course_code', ''), e0['course_name']))
        moodle_items = cur.fetchall()
        conn.close()

        if moodle_items:
            st.write("**Moodle 内容**")
            icons = {"announcement": "📢", "assignment": "📝", "resource": "📁", "quiz": "📊"}
            for item in moodle_items:
                icon = icons.get(item[1], '📌')
                due = f" | 截止: {item[2]}" if item[2] else ''
                st.write(f"{icon} {item[0]}{due}")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.title, t.due_date, COALESCE(p.status, 'pending')
        FROM tasks t
        LEFT JOIN progress p ON t.id = p.task_id AND p.student_id=%s
        WHERE t.subject=%s OR t.subject=%s
        ORDER BY t.due_date NULLS LAST LIMIT 5
    """, (student_id, e0.get('course_code', ''), e0['course_name']))
    tasks = cur.fetchall()
    conn.close()

    if tasks:
        st.write("**相关任务**")
        status_cn = {
            "pending": "⏳ 未开始", "in_progress": "🔵 进行中",
            "submitted": "📬 已提交", "completed": "✅ 已完成",
            "needs_revision": "🔄 需修改"
        }
        for t in tasks:
            st.write(f"- {t[0]} | 截止: {t[1] or '未设'} | {status_cn.get(t[2], t[2])}")

    if st.button("✕ 关闭", key=f"close_cd_{course_key}"):
        del st.session_state['selected_course']
        st.rerun()


def show_timetable(user):
    student_id = user['id']
    entries = _get_entries(student_id)

    tab_view, tab_import, tab_manual = st.tabs(["📅 查看课程表", "📤 导入截图", "✏️ 手动编辑"])

    with tab_view:
        if not entries:
            st.info("还没有课程表。请在「导入截图」标签页上传截图，或在「手动编辑」中添加课程。")
        else:
            st.markdown(_render_timetable_html(entries), unsafe_allow_html=True)
            st.divider()
            st.write("**点击课程卡片查看详情**")

            keys = list(dict.fromkeys((e['course_code'] or e['course_name']) for e in entries))
            colors = _get_course_colors(entries)
            cols = st.columns(min(len(keys), 4))

            for i, key in enumerate(keys):
                e = next(e for e in entries if (e['course_code'] or e['course_name']) == key)
                with cols[i % 4]:
                    display = f"📘 {e.get('course_code', '')} {e['course_name']}" if e.get('course_code') else f"📗 {e['course_name']}"
                    if st.button(display, key=f"ccard_{key}", use_container_width=True):
                        if st.session_state.get('selected_course') == key:
                            del st.session_state['selected_course']
                        else:
                            st.session_state['selected_course'] = key
                        st.rerun()

            if st.session_state.get('selected_course'):
                _show_course_detail(st.session_state['selected_course'], entries, student_id)

    with tab_import:
        st.write("### 上传课程表截图")
        st.caption("支持 JPG、PNG、WEBP 格式。AI 自动识别课程名称、时间、地点。")

        uploaded = st.file_uploader("选择截图", type=["jpg", "jpeg", "png", "webp"], key="tt_img")

        if uploaded:
            st.image(uploaded, caption="预览", width=500)

            if st.button("🔍 AI 识别课程表", type="primary"):
                with st.spinner("AI 正在识别中，请稍候..."):
                    b64 = base64.standard_b64encode(uploaded.read()).decode()
                    ext = uploaded.name.split('.')[-1].lower()
                    media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                                  "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
                    parsed = _parse_timetable_image(b64, media_type)

                if parsed:
                    st.session_state['tt_parsed'] = parsed
                    st.success(f"识别到 {len(parsed)} 个课程条目")
                else:
                    st.error("识别失败，请尝试上传更清晰的图片")

        if st.session_state.get('tt_parsed'):
            parsed = st.session_state['tt_parsed']
            st.write("### 识别结果预览")

            for p in parsed:
                day_idx = int(p.get('day_of_week', 0))
                day_label = DAY_NAMES[day_idx] if day_idx < len(DAY_NAMES) else str(day_idx)
                st.write(
                    f"- **{p.get('course_code', '') or ''} {p.get('course_name', '')}** | "
                    f"{day_label} {p.get('start_time', '')}–{p.get('end_time', '')} "
                    f"@ {p.get('location') or '未知'}"
                )

            st.warning("⚠️ 保存将替换当前全部课程表数据")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ 确认保存", type="primary"):
                    _save_entries(student_id, parsed)
                    del st.session_state['tt_parsed']
                    st.success("课程表已保存！")
                    st.rerun()
            with col2:
                if st.button("取消", key="tt_cancel"):
                    del st.session_state['tt_parsed']
                    st.rerun()

    with tab_manual:
        with st.form("add_tt_entry"):
            st.write("### 添加课程")
            col1, col2 = st.columns(2)
            with col1:
                cname = st.text_input("课程名称 *")
                ccode = st.text_input("课程代码（如 COMP1511）")
                location = st.text_input("上课地点")
                lecturer = st.text_input("讲师")
            with col2:
                day = st.selectbox("星期", options=list(range(5)), format_func=lambda x: DAY_NAMES[x])
                c1, c2 = st.columns(2)
                with c1:
                    start = st.time_input("开始时间")
                with c2:
                    end = st.time_input("结束时间")

            if st.form_submit_button("➕ 添加") and cname:
                existing = _get_entries(student_id)
                color_map = _get_course_colors(existing)
                key = ccode or cname
                color = color_map.get(key, COLORS[len(color_map) % len(COLORS)])
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO timetable_entries
                    (student_id, course_name, course_code, day_of_week, start_time, end_time, location, lecturer, color)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (student_id, cname, ccode, day,
                      start.strftime("%H:%M"), end.strftime("%H:%M"),
                      location, lecturer, color))
                conn.commit()
                conn.close()
                st.success(f"已添加：{cname}")
                st.rerun()

        if entries:
            st.divider()
            st.write("### 当前课程")
            for e in entries:
                col1, col2 = st.columns([5, 1])
                with col1:
                    code_part = f"**{e['course_code']}** " if e.get('course_code') else ''
                    st.write(
                        f"{code_part}{e['course_name']} | "
                        f"{DAY_NAMES[e['day_of_week']]} {e['start_time']}–{e['end_time']} "
                        f"| 📍{e.get('location') or '—'}"
                    )
                with col2:
                    if st.button("删除", key=f"del_tt_{e['id']}"):
                        conn = get_conn()
                        cur = conn.cursor()
                        cur.execute("DELETE FROM timetable_entries WHERE id=%s AND student_id=%s",
                                    (e['id'], student_id))
                        conn.commit()
                        conn.close()
                        st.rerun()
