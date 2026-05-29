"""
Moodle content fetcher.
Supports two auth modes:
  - api_token: uses Moodle Web Services REST API (structured, preferred)
  - session_cookie: uses browser MoodleSession cookie (universal fallback)
"""
import re
import json
import requests
from datetime import datetime

TIMEOUT = 15
DEFAULT_MOODLE_URL = "https://moodle.telt.unsw.edu.au"


# ─── helpers ────────────────────────────────────────────────────────────────

def _clean_html(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)


def _ts_to_date(ts: int) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _rest(moodle_url: str, token: str, fn: str, **params):
    r = requests.get(
        f"{moodle_url}/webservice/rest/server.php",
        params={"wstoken": token, "wsfunction": fn, "moodlewsrestformat": "json", **params},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and "exception" in data:
        raise RuntimeError(data.get("message", data["exception"]))
    return data


# ─── API TOKEN mode ──────────────────────────────────────────────────────────

def api_verify_token(moodle_url: str, token: str) -> dict:
    """Returns {userid, fullname, sitename} or raises RuntimeError."""
    info = _rest(moodle_url, token, "core_webservice_get_site_info")
    return {
        "userid": info["userid"],
        "fullname": info.get("fullname", ""),
        "sitename": info.get("sitename", ""),
    }


def api_get_courses(moodle_url: str, token: str, userid: int) -> list[dict]:
    """Returns [{id, fullname, shortname}]"""
    courses = _rest(moodle_url, token, "core_enrol_get_users_courses", userid=userid)
    return [{"id": c["id"], "fullname": c["fullname"], "shortname": c.get("shortname", "")}
            for c in courses]


def api_fetch_course_items(moodle_url: str, token: str, course_id: int) -> list[dict]:
    """Fetch assignments + resources for one course. Returns list of item dicts."""
    items = []

    # Assignments (has due dates)
    try:
        data = requests.post(
            f"{moodle_url}/webservice/rest/server.php",
            data={"wstoken": token, "wsfunction": "mod_assign_get_assignments",
                  "moodlewsrestformat": "json", "courseids[0]": course_id},
            timeout=TIMEOUT,
        ).json()
        for course in data.get("courses", []):
            for a in course.get("assignments", []):
                items.append({
                    "type": "assignment",
                    "title": a.get("name", ""),
                    "body": _clean_html(a.get("intro", ""))[:200],
                    "due_date": _ts_to_date(a.get("duedate", 0)),
                })
    except Exception:
        pass

    # Course contents (sections + modules)
    try:
        sections = _rest(moodle_url, token, "core_course_get_contents", courseid=course_id)
        for sec in sections:
            for mod in sec.get("modules", []):
                mtype = mod.get("modname", "")
                if mtype == "assign":
                    continue  # already captured above
                item_type = "announcement" if mtype == "forum" else "resource"
                items.append({
                    "type": item_type,
                    "title": mod.get("name", ""),
                    "body": f"[{sec.get('name', '')}]",
                    "due_date": "",
                })
    except Exception:
        pass

    return items


# ─── SESSION COOKIE mode ─────────────────────────────────────────────────────

def _cookie_session(moodle_url: str, cookie: str) -> requests.Session:
    domain = moodle_url.replace("https://", "").replace("http://", "").split("/")[0]
    s = requests.Session()
    s.cookies.set("MoodleSession", cookie, domain=domain)
    s.headers["User-Agent"] = "Mozilla/5.0 (compatible; learning-platform)"
    return s


def cookie_verify(moodle_url: str, cookie: str) -> tuple[bool, str]:
    """Returns (is_valid, reason). reason is empty string if valid."""
    cookie = cookie.strip()
    if not cookie:
        return False, "Cookie 为空"
    try:
        s = _cookie_session(moodle_url, cookie)
        r = s.get(f"{moodle_url}/my/", timeout=TIMEOUT, allow_redirects=True)
        final_url = r.url
        # Ended up back on login / SSO page = session rejected
        login_keywords = ["login", "sso", "idp", "saml", "auth", "signin", "microsoft"]
        if any(k in final_url.lower() for k in login_keywords):
            return False, f"IP_BOUND:{final_url}"
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        return True, ""
    except Exception as e:
        return False, f"网络错误: {e}"


def cookie_get_courses(moodle_url: str, cookie: str) -> list[dict]:
    """Scrape enrolled course list from Moodle dashboard."""
    from bs4 import BeautifulSoup
    s = _cookie_session(moodle_url, cookie)
    r = s.get(f"{moodle_url}/my/", timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "html.parser")

    seen = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = re.search(r"/course/view\.php\?id=(\d+)", href)
        if m:
            cid = m.group(1)
            name = a.get_text(strip=True)
            if name and len(name) > 2 and cid not in seen:
                seen[cid] = {"id": cid, "fullname": name, "shortname": ""}

    return list(seen.values())


def cookie_fetch_course_items(moodle_url: str, cookie: str, course_id: str,
                               course_name: str) -> list[dict]:
    """Fetch course page and extract items via Claude."""
    from bs4 import BeautifulSoup
    from ai_helper import call_claude

    s = _cookie_session(moodle_url, cookie)
    r = s.get(f"{moodle_url}/course/view.php?id={course_id}", timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)[:7000]

    prompt = (
        f"以下是 Moodle 课程「{course_name}」的页面内容。"
        "请提取所有作业（含截止日期）、公告、课程资料，返回JSON：\n"
        '{"items":[{"type":"assignment|announcement|resource","title":"标题",'
        '"body":"简述限100字","due_date":"YYYY-MM-DD或空字符串"}]}\n'
        f"只返回JSON。\n\n内容：\n{text}"
    )
    result = call_claude(
        "你是 Moodle 课程内容解析助手。",
        [{"role": "user", "content": prompt}],
        max_tokens=2000,
    )
    m = re.search(r"\{.*\}", result, re.DOTALL)
    if m:
        try:
            return json.loads(m.group()).get("items", [])
        except Exception:
            pass
    return []
