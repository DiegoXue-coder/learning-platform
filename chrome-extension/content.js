// Injected into Moodle tab — runs in page context, has full cookie access

const MAX_PDF_BYTES = 3 * 1024 * 1024; // 3 MB
const MAX_TEXT = 2000;
const MONTHS = {
  january:1,february:2,march:3,april:4,may:5,june:6,
  july:7,august:8,september:9,october:10,november:11,december:12
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function parseDate(str) {
  if (!str) return "";
  const m = str.match(/(\d{1,2})\s+(\w+)\s+(\d{4})/);
  if (m) {
    const mo = MONTHS[m[2].toLowerCase()];
    if (mo) return `${m[3]}-${String(mo).padStart(2,"0")}-${String(m[1]).padStart(2,"0")}`;
  }
  const iso = str.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return iso[0];
  return "";
}

function getText(el, limit) {
  if (!el) return "";
  return el.textContent.trim().replace(/\s+/g," ").substring(0, limit || MAX_TEXT);
}

async function safeFetch(url) {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r;
}

function chunkArray(arr, size) {
  const out = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}

// ── Course info ───────────────────────────────────────────────────────────────

function getCourseInfo() {
  const h1 = document.querySelector(".page-header-headings h1, h1.h2, h1");
  const name = h1 ? h1.textContent.trim() : document.title.replace(" | UNSW Moodle","").trim();
  const code = (name.match(/^([A-Z]{3,4}\d{4,5})/)||[])[1] || "";
  const idMatch = location.href.match(/[?&]id=(\d+)/);
  return { name, code, id: idMatch ? idMatch[1] : "", url: location.href };
}

// ── Page sections ─────────────────────────────────────────────────────────────

function getSections() {
  const out = [];
  document.querySelectorAll("li.section.main, li.section.current, li.section").forEach(sec => {
    const title = sec.querySelector(".sectionname, .section-title h3, h3");
    const summary = sec.querySelector(".summary");
    if (title) out.push({
      name: getText(title, 100),
      summary: getText(summary, 400)
    });
  });
  return out;
}

// ── Activity links on current page ───────────────────────────────────────────

const FETCH_TYPES = ["assign","forum","page","resource","label","glossary"];

function getActivityLinks() {
  const seen = new Set();
  const links = [];
  document.querySelectorAll("a[href]").forEach(a => {
    const m = a.href.match(/\/mod\/(\w+)\/view\.php\?id=(\d+)/);
    if (!m) return;
    const [, type, id] = m;
    if (!FETCH_TYPES.includes(type) || seen.has(id)) return;
    seen.add(id);
    links.push({ href: a.href, type, id, name: getText(a, 120) });
  });
  return links;
}

// ── Sub-page extractors ───────────────────────────────────────────────────────

function extractAssignment(doc, activity) {
  // Due date
  let dueDate = "";
  doc.querySelectorAll("tr").forEach(tr => {
    const th = tr.querySelector("th, td:first-child");
    const td = tr.querySelector("td:last-child");
    if (th && td && /due/i.test(th.textContent)) {
      dueDate = parseDate(td.textContent.trim());
    }
  });
  const descEl = doc.querySelector(".box.generalbox.mod_introbox, .generalbox, #intro");
  return {
    type: "assignment",
    name: activity.name,
    description: getText(descEl, 800),
    due_date: dueDate
  };
}

function extractForum(doc, activity) {
  const posts = [];
  // Discussion list view
  doc.querySelectorAll("tr.discussion").forEach(tr => {
    const subj = tr.querySelector("td.topic a, .subject a");
    if (subj) posts.push({ title: subj.textContent.trim(), content: "" });
  });
  // Single discussion view
  doc.querySelectorAll(".forumpost, .post").forEach(post => {
    const subj = post.querySelector(".subject, h3");
    const body = post.querySelector(".posting, .post-content-container");
    if (subj) posts.push({
      title: subj.textContent.trim(),
      content: getText(body, 500)
    });
  });
  return { type: "forum", name: activity.name, posts: posts.slice(0, 20) };
}

function extractPage(doc, activity) {
  const content = doc.querySelector(".box.generalbox.mod_introbox, .region-content .box, #page-content");
  return { type: "page", name: activity.name, content: getText(content, 2000) };
}

async function extractResource(doc, activity) {
  // Try to find PDF link (Moodle may redirect or show inline)
  const pdfLink = Array.from(doc.querySelectorAll("a[href]"))
    .find(a => a.href.includes("pluginfile.php") || /\.pdf(\?|$)/i.test(a.href));

  if (!pdfLink) {
    return { type: "resource", name: activity.name, content: getText(doc.querySelector(".resourcecontent, .generalbox"), 1000) };
  }

  const filename = decodeURIComponent(pdfLink.href.split("/").pop().split("?")[0]);

  try {
    const resp = await safeFetch(pdfLink.href);
    const buf = await resp.arrayBuffer();

    if (buf.byteLength > MAX_PDF_BYTES) {
      return { type: "pdf_large", name: activity.name, filename, size_mb: (buf.byteLength/1024/1024).toFixed(1) };
    }

    // Convert to base64
    const bytes = new Uint8Array(buf);
    let binary = "";
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    const b64 = btoa(binary);

    return { type: "pdf", name: activity.name, filename, pdf_b64: b64, size_mb: (buf.byteLength/1024/1024).toFixed(1) };
  } catch(e) {
    return { type: "pdf_error", name: activity.name, filename, error: e.message };
  }
}

async function fetchActivity(activity) {
  try {
    const resp = await safeFetch(activity.href);
    const html = await resp.text();
    const doc = new DOMParser().parseFromString(html, "text/html");

    switch(activity.type) {
      case "assign":   return extractAssignment(doc, activity);
      case "forum":    return extractForum(doc, activity);
      case "page":     return extractPage(doc, activity);
      case "resource": return await extractResource(doc, activity);
      default:         return { type: activity.type, name: activity.name };
    }
  } catch(e) {
    return { type: activity.type, name: activity.name, error: e.message };
  }
}

// ── Main entry point ──────────────────────────────────────────────────────────

async function run() {
  try {
    const course = getCourseInfo();
    const sections = getSections();
    const activityLinks = getActivityLinks();

    // Send progress update
    chrome.runtime.sendMessage({ type: "PROGRESS", text: `找到 ${activityLinks.length} 个活动，开始并行抓取...` });

    // Fetch in batches of 6 (parallel)
    const activities = [];
    const chunks = chunkArray(activityLinks, 6);
    let done = 0;
    for (const chunk of chunks) {
      const results = await Promise.all(chunk.map(fetchActivity));
      activities.push(...results);
      done += chunk.length;
      chrome.runtime.sendMessage({ type: "PROGRESS", text: `已完成 ${done}/${activityLinks.length}...` });
    }

    const pdfs = activities.filter(a => a.type === "pdf");
    const largePdfs = activities.filter(a => a.type === "pdf_large");

    return {
      course,
      sections,
      activities: activities.filter(a => !["pdf","pdf_large","pdf_error"].includes(a.type)),
      pdfs,
      pdf_skipped: largePdfs
    };
  } catch(e) {
    return { error: e.message };
  }
}

run(); // Chrome scripting API captures the return value of the last expression