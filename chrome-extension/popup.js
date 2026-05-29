const MOODLE_URL = "https://moodle.telt.unsw.edu.au";
const PLATFORM_URL = "https://learning-platform-diego.streamlit.app";

function copyText(text) {
  // Most reliable method for Chrome extensions
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.cssText = "position:fixed;top:0;left:0;opacity:0;pointer-events:none";
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  const ok = document.execCommand("copy");
  document.body.removeChild(ta);
  return ok;
}

function show(type, html) {
  const el = document.getElementById("status");
  el.className = "status " + type;
  el.innerHTML = html;
  el.style.display = "block";
}

function getCookie() {
  const btn = document.getElementById("copyBtn");
  btn.disabled = true;
  btn.textContent = "读取中...";

  chrome.cookies.get({ url: MOODLE_URL, name: "MoodleSession" }, function (cookie) {
    btn.disabled = false;
    btn.textContent = "📋 一键复制登录凭证";

    // Debug: show what we got
    if (chrome.runtime.lastError) {
      show("error", "❌ 权限错误：" + chrome.runtime.lastError.message);
      return;
    }

    if (!cookie || !cookie.value) {
      show("error",
        "❌ 未找到 Moodle 登录状态<br><br>" +
        "请先 <a href='" + MOODLE_URL + "' target='_blank' style='color:#1e40af'>打开 Moodle 并登录</a>，" +
        "然后再点此按钮"
      );
      return;
    }

    const val = cookie.value;

    // Try copy
    const copied = copyText(val);

    // Show the value regardless (user can manually copy if needed)
    const preview = val.length > 50 ? val.substring(0, 50) + "..." : val;

    if (copied) {
      show("success",
        "✅ <strong>已复制到剪贴板！</strong><br>" +
        "回到平台直接 Ctrl+V 粘贴<br><br>" +
        "<a href='" + PLATFORM_URL + "' target='_blank' style='color:#1e40af'>→ 打开学习平台</a>"
      );
    } else {
      // Copy failed, show value to manually copy
      show("success",
        "✅ 已获取凭证（自动复制失败，请手动复制下方内容）："
      );
    }

    // Always show the full value in a copyable box
    const box = document.getElementById("cookieBox");
    box.style.display = "block";
    box.value = val;
    box.onclick = function() { this.select(); };

    // Try once more with clipboard API
    if (!copied && navigator.clipboard) {
      navigator.clipboard.writeText(val).then(() => {
        show("success",
          "✅ <strong>已复制到剪贴板！</strong><br>" +
          "回到平台直接 Ctrl+V 粘贴<br><br>" +
          "<a href='" + PLATFORM_URL + "' target='_blank' style='color:#1e40af'>→ 打开学习平台</a>"
        );
      }).catch(() => {});
    }
  });
}
