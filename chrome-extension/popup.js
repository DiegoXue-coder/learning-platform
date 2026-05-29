const MOODLE_URL = "https://moodle.telt.unsw.edu.au";
const PLATFORM_URL = "https://learning-platform-diego.streamlit.app";

function getCookie() {
  const btn = document.getElementById("copyBtn");
  const status = document.getElementById("status");
  const cookieBox = document.getElementById("cookieBox");
  const hint = document.getElementById("hint");

  btn.disabled = true;
  btn.textContent = "读取中...";

  chrome.cookies.get({ url: MOODLE_URL, name: "MoodleSession" }, function (cookie) {
    btn.disabled = false;
    btn.textContent = "📋 一键复制登录凭证";

    if (!cookie || !cookie.value) {
      status.className = "status error";
      status.textContent = "❌ 未找到登录状态，请先打开 Moodle 并登录后再点击";
      cookieBox.style.display = "none";
      hint.innerHTML = '<a href="' + MOODLE_URL + '" target="_blank" style="color:#1e40af">点这里打开 Moodle 登录</a>';
      return;
    }

    // Copy to clipboard
    navigator.clipboard.writeText(cookie.value).then(function () {
      status.className = "status success";
      status.innerHTML = "✅ <strong>已复制到剪贴板！</strong><br>回到平台，直接 Ctrl+V 粘贴即可";
      cookieBox.style.display = "block";
      cookieBox.textContent = cookie.value.substring(0, 40) + "...";
      hint.innerHTML = '<a href="' + PLATFORM_URL + '" target="_blank" style="color:#1e40af">点这里打开学习平台</a>';
    }).catch(function () {
      // Clipboard API failed, show value manually
      status.className = "status success";
      status.textContent = "✅ 已获取，请手动复制下方内容：";
      cookieBox.style.display = "block";
      cookieBox.textContent = cookie.value;
      cookieBox.onclick = function () {
        document.execCommand("copy");
        status.textContent = "✅ 已复制！";
      };
    });
  });
}
