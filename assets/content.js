/* عرض المحتوى الذي تضيفه الإدارة (نصوص وصور وفيديوهات) — مشترك بين الموقع ولوحة الإدارة */
(function () {
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function yt(u) {
    try {
      const x = new URL(u); if (x.protocol !== "https:") return null;
      const h = x.hostname.replace(/^(www|m)\./, "");
      const okId = s => /^[\w-]{6,64}$/.test(s || "");
      if (h === "youtube.com" || h === "youtube-nocookie.com") {
        const list = x.searchParams.get("list"), v = x.searchParams.get("v");
        if (x.pathname === "/playlist" && okId(list)) return { list };
        if (okId(v)) return { v, list: okId(list) ? list : null };
        const m = x.pathname.match(/^\/(embed|shorts|live)\/([\w-]{6,64})/); if (m && m[2] !== "videoseries") return { v: m[2] };
        if (okId(list)) return { list };
      }
      if (h === "youtu.be") { const id = x.pathname.slice(1).split("/")[0]; if (okId(id)) return { v: id }; }
    } catch (e) {}
    return null;
  }
  const ytEmbed = y => y.v ? "https://www.youtube-nocookie.com/embed/" + y.v + (y.list ? "?list=" + y.list : "") : "https://www.youtube-nocookie.com/embed/videoseries?list=" + y.list;
  const ytThumb = y => y.v ? "https://i.ytimg.com/vi/" + y.v + "/hqdefault.jpg" : "";
  function inline(s) {
    s = esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    return s.replace(/\[([^\]]+)\]\((https:\/\/[^\s)]+)\)/g, (m, t, u) => `<a href="${u}" target="_blank" rel="noopener">${t}</a>`);
  }
  function text(t) {
    let out = "", list = null, para = [];
    const fp = () => { if (para.length) { out += "<p>" + para.map(inline).join("<br>") + "</p>"; para = []; } };
    const fl = () => { if (list) { out += `<${list.t}>` + list.items.map(i => "<li>" + inline(i) + "</li>").join("") + `</${list.t}>`; list = null; } };
    for (const ln of String(t || "").split(/\r?\n/)) {
      const l = ln.trim(); let m;
      if (!l) { fp(); fl(); continue; }
      if ((m = l.match(/^#{1,4}\s+(.*)/))) { fp(); fl(); out += "<h3>" + inline(m[1]) + "</h3>"; continue; }
      if ((m = l.match(/^[-•*]\s+(.*)/))) { fp(); if (!list || list.t !== "ul") { fl(); list = { t: "ul", items: [] }; } list.items.push(m[1]); continue; }
      if ((m = l.match(/^\d+[.)]\s+(.*)/))) { fp(); if (!list || list.t !== "ol") { fl(); list = { t: "ol", items: [] }; } list.items.push(m[1]); continue; }
      if ((m = l.match(/^>\s*(.*)/))) { fp(); fl(); out += '<div class="tip">' + inline(m[1]) + "</div>"; continue; }
      fl(); para.push(l);
    }
    fp(); fl(); return out;
  }
  function block(b) {
    if (!b || typeof b !== "object") return "";
    const cap = b.cap ? `<figcaption>${esc(b.cap)}</figcaption>` : "";
    if (b.type === "text") return `<div class="cb-text">${text(b.v)}</div>`;
    const u = String(b.url || ""); if (!/^https:\/\//i.test(u)) return "";
    if (b.type === "image") return `<figure class="cb-fig"><img src="${esc(u)}" alt="${esc(b.cap || "")}" loading="lazy">${cap}</figure>`;
    if (b.type === "video") {
      const y = yt(u);
      if (y) return `<figure class="cb-fig"><div class="cb-vid"><iframe src="${esc(ytEmbed(y))}" title="${esc(b.cap || "فيديو")}" loading="lazy" allow="accelerometer; encrypted-media; gyroscope; picture-in-picture; fullscreen" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe></div>${cap}</figure>`;
      if (/\.(mp4|webm)(\?|$)/i.test(u)) return `<figure class="cb-fig"><video controls preload="metadata" src="${esc(u)}"></video>${cap}</figure>`;
      return `<p><a href="${esc(u)}" target="_blank" rel="noopener">${esc(b.cap || u)}</a></p>`;
    }
    return "";
  }
  const render = blocks => (Array.isArray(blocks) ? blocks : []).map(block).join("");
  /* تحويل شرح الدرس الأصلي (HTML) إلى نص قابل للتعديل */
  function htmlToText(html) {
    const doc = new DOMParser().parseFromString("<div>" + String(html || "") + "</div>", "text/html");
    const inl = n => Array.from(n.childNodes).map(c => c.nodeType === 3 ? c.textContent.replace(/\s+/g, " ") : c.nodeType !== 1 ? "" : /^(B|STRONG)$/.test(c.tagName) ? "**" + inl(c).trim() + "**" : c.tagName === "BR" ? "\n" : c.tagName === "A" && /^https:/.test(c.getAttribute("href") || "") ? "[" + inl(c).trim() + "](" + c.getAttribute("href") + ")" : inl(c)).join("");
    const out = [];
    const walk = n => {
      for (const c of n.childNodes) {
        if (c.nodeType === 3) { const t = c.textContent.trim(); if (t) out.push(t); continue; }
        if (c.nodeType !== 1) continue;
        const tg = c.tagName;
        if (/^H[1-6]$/.test(tg)) out.push("## " + inl(c).trim());
        else if (tg === "P") out.push(inl(c).trim());
        else if (tg === "UL" || tg === "OL") out.push(Array.from(c.children).filter(li => li.tagName === "LI").map((li, i) => (tg === "OL" ? (i + 1) + ". " : "- ") + inl(li).trim()).join("\n"));
        else if (tg === "TABLE") out.push(Array.from(c.querySelectorAll("tr")).map(tr => "- " + Array.from(tr.children).map(td => inl(td).trim()).filter(Boolean).join(" | ")).join("\n"));
        else if (c.classList.contains("tip") || c.classList.contains("note")) out.push("> " + inl(c).replace(/\s+/g, " ").trim());
        else if (/^(DIV|SECTION|ARTICLE|FIGURE)$/.test(tg)) walk(c);
        else { const t = inl(c).trim(); if (t) out.push(t); }
      }
    };
    walk(doc.body.firstChild);
    return out.filter(Boolean).join("\n\n");
  }
  window.CB = { render, text, yt, ytThumb, htmlToText, esc };
})();
