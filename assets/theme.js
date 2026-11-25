/* ألوان الموقع التي تختارها الإدارة (الإعدادات ← ألوان الموقع) */
(function () {
  const HEX = /^#[0-9a-fA-F]{6}$/;
  const PRESETS = [
    { id: "default", name: "الأزرق الافتراضي", accent: "#0F5C93", gold: "#B7862A", navy: "#0B2540" },
    { id: "shamel", name: "عنابي الشامل", accent: "#7A2350", gold: "#B7862A", navy: "#3E1230" },
    { id: "green", name: "أخضر", accent: "#0E6B57", gold: "#A97A22", navy: "#0D3329" },
    { id: "violet", name: "بنفسجي", accent: "#4E2A6B", gold: "#C08A2E", navy: "#24123A" },
    { id: "teal", name: "أزرق مخضر", accent: "#0E7C86", gold: "#B7862A", navy: "#0A3540" },
    { id: "copper", name: "نحاسي", accent: "#B4532A", gold: "#1F6F5C", navy: "#3B1A0C" },
  ];
  function css(t) {
    if (!t || !HEX.test(t.accent || "") || !HEX.test(t.gold || "") || !HEX.test(t.navy || "")) return "";
    const A = t.accent, G = t.gold, N = t.navy;
    const dark = `--accent:color-mix(in srgb,${A} 55%,#fff);--accent-ink:#06121c;--accent-soft:color-mix(in srgb,${A} 28%,#0f1820);--gold:color-mix(in srgb,${G} 70%,#fff);--gold-soft:color-mix(in srgb,${G} 22%,#141414);--navy:color-mix(in srgb,${N} 55%,#000);--navy2:color-mix(in srgb,${N} 75%,#000)`;
    return `html:root{--accent:${A};--accent-ink:#fff;--accent-soft:color-mix(in srgb,${A} 12%,#fff);--gold:${G};--gold-soft:color-mix(in srgb,${G} 15%,#fff);--navy:${N};--navy2:color-mix(in srgb,${N} 72%,${A})}
@media (prefers-color-scheme:dark){html:root:not([data-theme="light"]){${dark}}}
html:root[data-theme="dark"]{${dark}}`;
  }
  function apply(t, persist) {
    let el = document.getElementById("theme6");
    if (!el) { el = document.createElement("style"); el.id = "theme6"; document.head.appendChild(el); }
    el.textContent = css(t);
    if (persist) try { localStorage.setItem("shamel-theme", t ? JSON.stringify(t) : ""); } catch (e) {}
  }
  try { const s = localStorage.getItem("shamel-theme"); if (s) apply(JSON.parse(s)); } catch (e) {}
  window.THEME = { apply, PRESETS, valid: t => !!css(t) };
})();
