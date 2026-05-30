const PLATFORM = "https://learning-platform-diego.streamlit.app";

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("extractBtn").addEventListener("click", startExtract);
});

// Listen for progress messages from content script
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "PROGRESS") setProgress(msg.text);
});

function setStatus(type, html) {
  const el = document.getElementById("status");
  el.className = "status " + type;
  el.innerHTML = html;
}
function setProgress(text) {
  document.getElementById("progress").textContent = text;
}

async function startExtract() {
  const btn = document.getElementById("extractBtn");
  btn.disabled = true;
  btn.textContent = "⏳ 抓取中...";
  setProgress("");
  setStatus("info", "正在读取 Moodle 课程内容...");

  try {
    // Prefer the currently active tab if it's Moodle, otherwise find any Moodle tab
    const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const allTabs = await chrome.tabs.query({});
    const moodleTab =
      (activeTab && activeTab.url && activeTab.url.includes("moodle.telt.unsw.edu.au"))
        ? activeTab
        : allTabs.find(t => t.url && t.url.includes("moodle.telt.unsw.edu.au"));

    if (!moodleTab) {
      setStatus("error",
        "没有找到 Moodle 标签页。<br>" +
        "请先 <a href='https://moodle.telt.unsw.edu.au' target='_blank' style='color:#1e40af'>打开 Moodle</a>" +
        " 并进入某门课的主页，再点提取。"
      );
      btn.disabled = false; btn.textContent = "📥 提取当前课程内容";
      return;
    }

    // Show which tab we're using
    setProgress(`使用标签页：${moodleTab.url.split("?")[0]}`);

    setProgress("注入提取脚本...");

    const results = await chrome.scripting.executeScript({
      target: { tabId: moodleTab.id },
      files: ["content.js"]
    });

    const data = results[0].result;

    if (!data || data.error) {
      setStatus("error", "❌ 提取失败：" + (data ? data.error : "未知错误"));
      btn.disabled = false; btn.textContent = "📥 提取当前课程内容";
      return;
    }

    // Build summary
    const course = data.course;
    const acts = data.activities || [];
    const pdfs = data.pdfs || [];
    const skipped = data.pdf_skipped || [];
    const assignments = acts.filter(a => a.type === "assignment");
    const forums = acts.filter(a => a.type === "forum");

    setProgress("");

    // Wrap in courses array format for platform compatibility
    const payload = {
      source: "extension_v2",
      course_detail: data
    };

    const json = JSON.stringify(payload);
    const encoded = btoa(unescape(encodeURIComponent(json)));

    let summary = `✅ <strong>${course.name}</strong><br>`;
    summary += `📝 作业 ${assignments.length} 个 &nbsp; 📢 论坛 ${forums.length} 个<br>`;
    if (pdfs.length > 0) summary += `📄 PDF ${pdfs.length} 个<br>`;
    if (skipped.length > 0) summary += `⚠️ ${skipped.length} 个大文件已跳过<br>`;
    summary += `<br><small>正在自动导入到平台，无需手动粘贴...</small>`;

    setStatus("success", summary);

    // Use URL param for auto-import (single course data is small enough ~5KB)
    setTimeout(() => chrome.tabs.create({ url: PLATFORM + "?moodle_data=" + encoded }), 1200);

  } catch(e) {
    setStatus("error", "❌ " + e.message);
  }

  btn.disabled = false;
  btn.textContent = "📥 提取当前课程内容";
}