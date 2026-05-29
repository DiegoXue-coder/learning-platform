const MOODLE = "https://moodle.telt.unsw.edu.au";
const PLATFORM = "https://learning-platform-diego.streamlit.app";

// ── UI helpers ────────────────────────────────────────────────────────────────
function setStatus(type, html) {
  const el = document.getElementById("statusMain");
  el.className = "status " + type;
  el.innerHTML = html;
}
function setProgress(text) {
  document.getElementById("progressText").textContent = text;
}
function setInfo(show) {
  document.getElementById("statusInfo").style.display = show ? "block" : "none";
}

// ── Script injected into the Moodle tab ──────────────────────────────────────
function moodleFetchScript() {
  // This runs INSIDE the Moodle page — same origin, cookies included automatically

  async function fetchText(url) {
    const r = await fetch(url, { credentials: "include" });
    if (!r.ok) throw new Error("HTTP " + r.status + " for " + url);
    return r.text();
  }

  function parseCourses(html) {
    const doc = new DOMParser().parseFromString(html, "text/html");
    const seen = new Set();
    const courses = [];
    doc.querySelectorAll("a[href]").forEach(a => {
      const m = a.href.match(/\/course\/view\.php\?id=(\d+)/);
      if (m && !seen.has(m[1])) {
        const name = a.textContent.trim();
        if (name.length > 2) {
          seen.add(m[1]);
          courses.push({ id: m[1], name });
        }
      }
    });
    return courses;
  }

  function parseCourseItems(html, courseName) {
    const doc = new DOMParser().parseFromString(html, "text/html");
    const items = [];

    // Assignments / activities with due dates
    doc.querySelectorAll("[data-activityname], .activityname, .instancename").forEach(el => {
      const title = el.textContent.trim();
      if (title.length > 2) {
        items.push({ type: "resource", title, body: "", due_date: "" });
      }
    });

    // Due dates in page text
    const text = doc.body ? doc.body.innerText : "";
    const duePat = /(.{5,60}?)\s*[Dd]ue[:\s]+(\d{1,2}\s+\w+\s+\d{4}|\d{4}-\d{2}-\d{2})/g;
    let m;
    while ((m = duePat.exec(text)) !== null) {
      items.push({
        type: "assignment",
        title: m[1].trim().replace(/\n/g, " ").substring(0, 80),
        body: "",
        due_date: m[2]
      });
    }

    // Sections / headings as resources
    doc.querySelectorAll("h3.sectionname, .section-title").forEach(el => {
      const title = el.textContent.trim();
      if (title.length > 2) {
        items.push({ type: "resource", title, body: "[课程章节]", due_date: "" });
      }
    });

    // Deduplicate by title
    const seen = new Set();
    return items.filter(i => {
      if (seen.has(i.title)) return false;
      seen.add(i.title);
      return true;
    }).slice(0, 50); // max 50 items per course
  }

  async function run() {
    try {
      // Check if logged in
      const dashHtml = await fetchText(location.origin + "/my/");
      if (dashHtml.includes("You are not logged in") || dashHtml.includes("login")) {
        // might be redirected — check
        if (location.href.includes("login")) {
          return { error: "NOT_LOGGED_IN" };
        }
      }

      const courses = parseCourses(dashHtml);
      if (courses.length === 0) {
        return { error: "NO_COURSES" };
      }

      const result = { courses: [] };
      for (const course of courses.slice(0, 12)) {
        try {
          const html = await fetchText(location.origin + "/course/view.php?id=" + course.id);
          const items = parseCourseItems(html, course.name);
          result.courses.push({
            id: course.id,
            fullname: course.name,
            shortname: "",
            items
          });
        } catch (e) {
          result.courses.push({ id: course.id, fullname: course.name, shortname: "", items: [] });
        }
      }
      return result;
    } catch (e) {
      return { error: e.message };
    }
  }

  return run(); // returns a Promise — chrome.scripting.executeScript handles this
}

// ── Main ─────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("syncBtn").addEventListener("click", startSync);

  // Check if user is on Moodle tab
  chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
    const url = tabs[0] ? tabs[0].url : "";
    if (url.includes("moodle.telt.unsw.edu.au")) {
      setInfo(false);
    }
  });
});

async function startSync() {
  const btn = document.getElementById("syncBtn");
  btn.disabled = true;
  btn.textContent = "⏳ 正在抓取...";
  setInfo(false);
  setStatus("info", "正在读取 Moodle 课程数据，请稍候...");
  setProgress("");

  try {
    // Find an open Moodle tab; if none, create one
    const tabs = await chrome.tabs.query({});
    let moodleTab = tabs.find(t => t.url && t.url.includes("moodle.telt.unsw.edu.au"));

    if (!moodleTab) {
      setStatus("error",
        "没有找到已打开的 Moodle 标签页。<br>" +
        "请先 <a href='" + MOODLE + "' target='_blank' style='color:#1e40af'>打开 Moodle</a> 并登录，再点同步。"
      );
      btn.disabled = false;
      btn.textContent = "⬇️ 同步 Moodle 课程到平台";
      return;
    }

    setProgress("连接到 Moodle 标签页...");

    // Inject and run the fetch script inside the Moodle tab
    const results = await chrome.scripting.executeScript({
      target: { tabId: moodleTab.id },
      func: moodleFetchScript,
    });

    const data = results[0].result;

    if (!data || data.error) {
      const msg = data && data.error === "NOT_LOGGED_IN"
        ? "Moodle 未登录，请先登录后再同步"
        : data && data.error === "NO_COURSES"
        ? "未找到课程，请确认已登录并有选课"
        : "抓取失败：" + (data ? data.error : "未知错误");
      setStatus("error", "❌ " + msg);
      btn.disabled = false;
      btn.textContent = "⬇️ 同步 Moodle 课程到平台";
      return;
    }

    const courseCount = data.courses.length;
    const itemCount = data.courses.reduce((s, c) => s + c.items.length, 0);
    setProgress(`找到 ${courseCount} 门课程，${itemCount} 个内容项目`);

    // Copy compact JSON to clipboard (avoids URL size limits)
    const json = JSON.stringify(data);
    await navigator.clipboard.writeText(json);

    setStatus("success",
      `✅ 已抓取 <span class="course-count">${courseCount}</span> 门课程<br>` +
      `数据已复制到剪贴板，正在打开学习平台...<br>` +
      `<small>在平台的 Moodle 页面粘贴即可自动导入</small>`
    );

    setTimeout(() => {
      chrome.tabs.create({ url: PLATFORM + "?paste_moodle=1" });
    }, 1200);

  } catch (e) {
    setStatus("error", "❌ 错误：" + e.message);
  }

  btn.disabled = false;
  btn.textContent = "⬇️ 同步 Moodle 课程到平台";
}
