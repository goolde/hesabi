/* =====================================================================
   Engineers API — بوابة مهندسي الصيانة
   امتداد لطبقة API الموحدة (assets/api.js). يُحمَّل بعدها ويضيف window.API.eng.
   الواجهة لا تعرف شيئاً عن Supabase. للانتقال إلى Python/FastAPI يُعاد كتابة هذا الملف
   بنفس الدوال وأشكال البيانات: كائنات camelCase، والتواريخ أرقام (ms).
   الجداول والصلاحيات: maintenance/supabase/001_engineers_portal.sql
   ===================================================================== */
(function () {
  const API = window.API; if (!API) return;
  const sb = window.__sb;
  const ok = ({ data, error }) => {
    if (error) { const m = error.message || ""; const e = new Error(/row-level security|permission denied|not allowed/i.test(m) ? "ليست لديك صلاحية لهذا الإجراء." : /duplicate|unique/i.test(m) ? "هذا السجل موجود مسبقاً." : "تعذّر الحفظ، حاول مرة أخرى."); e.raw = m; e.code = /row-level|permission|not allowed/i.test(m) ? "denied" : "error"; throw e; }
    return data;
  };
  /* app field -> [column, kind]; kind: t=timestamp(ms), d=date(ms), n=nullable text, else as-is */
  const MAP = {
    engineers: { userId: ["user_id", "n"], name: ["name"], phone: ["phone"], region: ["region"], empNo: ["emp_no"], skills: ["skills"], active: ["active"] },
    customers: { name: ["name"], sector: ["sector"], city: ["city"], contact: ["contact"], phone: ["phone"], vat: ["vat"], installDate: ["install_date", "d"], contractStart: ["contract_start", "d"], contractEnd: ["contract_end", "d"], licenses: ["licenses"], notes: ["notes"], updatedAt: ["updated_at", "t"] },
    tickets: { no: ["no"], custId: ["customer_id", "n"], title: ["title"], desc: ["description"], prod: ["prod"], type: ["type"], pri: ["priority"], status: ["status"], channel: ["channel"], mode: ["mode"], engId: ["engineer_id", "n"], createdAt: ["created_at", "t"], assignedAt: ["assigned_at", "t"], dueAt: ["due_at", "t"], visitAt: ["visit_at", "t"], closedAt: ["closed_at", "t"], resolution: ["resolution"], mins: ["minutes"], rating: ["rating"], cl: ["checklist"], notes: ["notes"], updatedAt: ["updated_at", "t"] },
    kb: { title: ["title"], cat: ["cat"], prod: ["prod", "n"], tags: ["tags"], problem: ["problem"], solution: ["solution"], updatedAt: ["updated_at", "t"] },
    releases: { prod: ["prod"], ver: ["version"], kind: ["kind"], date: ["release_date", "d"], link: ["link", "n"], fileId: ["file_path", "n"], notes: ["notes"], updatedAt: ["updated_at", "t"] },
    drivers: { dtype: ["dtype"], brand: ["brand"], model: ["model"], conn: ["conn"], os: ["os"], link: ["link", "n"], fileId: ["file_path", "n"], notes: ["notes"], updatedAt: ["updated_at", "t"] },
    tools: { name: ["name"], purpose: ["purpose"], link: ["link", "n"], fileId: ["file_path", "n"], notes: ["notes"], updatedAt: ["updated_at", "t"] },
    trials: { prod: ["prod"], client: ["client"], phone: ["phone"], purpose: ["purpose"], days: ["days"], status: ["status"], engId: ["requested_by", "n"], username: ["username"], url: ["login_url", "n"], expiresAt: ["expires_at", "d"], activatedAt: ["activated_at", "t"], note: ["note"], createdAt: ["created_at", "t"], updatedAt: ["updated_at", "t"] },
  };
  const toRow = (col, o) => { const m = MAP[col], r = {}; for (const [k, v] of Object.entries(o)) { const f = m[k]; if (!f) continue; const [c, kind] = f;
    r[c] = kind === "t" ? (v ? new Date(v).toISOString() : null) : kind === "d" ? (v ? new Date(v).toISOString().slice(0, 10) : null) : kind === "n" ? (v === "" || v == null ? null : v) : (v === undefined ? null : v); } return r; };
  const fromRow = (col, r) => { const m = MAP[col], o = { id: r.id }; for (const [k, [c, kind]] of Object.entries(m)) { const v = r[c]; o[k] = (kind === "t" || kind === "d") ? (v ? new Date(v).getTime() : null) : v; }
    if (r.file_path) o.fileName = r.file_path.replace(/^\d+-/, ""); return o; };
  const mJoin = r => ({ id: r.user_id, name: r.name, empNo: r.emp_no, phone: r.phone, region: r.region, skills: r.skills || [], status: r.status, reason: r.reason, at: r.requested_at ? new Date(r.requested_at).getTime() : null });

  API.eng = {
    newId: () => (crypto.randomUUID ? crypto.randomUUID() : "10000000-1000-4000-8000-100000000000".replace(/[018]/g, c => (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16))),
    /* state: admin | eng | pending | rejected | none | suspended | signedout */
    async access() {
      const s = await API.auth.session(); if (!s) return { state: "signedout" };
      const me = await API.profile.me();
      const e = ok(await sb.from("engineers").select("*").eq("user_id", s.uid).maybeSingle());
      if (me && me.role === "admin") return { state: "admin", uid: s.uid, me, engineer: e && fromRow("engineers", e) };
      if (e) return { state: e.active && me && me.role === "engineer" ? "eng" : "suspended", uid: s.uid, me, engineer: fromRow("engineers", e) };
      const j = ok(await sb.from("join_requests").select("*").eq("user_id", s.uid).maybeSingle());
      return { state: j ? (j.status === "rejected" ? "rejected" : j.status === "approved" ? "suspended" : "pending") : "none", uid: s.uid, me, join: j && mJoin(j) };
    },
    async list(col) { const order = col === "engineers" ? "name" : col === "tickets" || col === "trials" ? "created_at" : "updated_at";
      return ok(await sb.from(col).select("*").order(order, { ascending: col === "engineers" }).limit(5000)).map(r => fromRow(col, r)); },
    async put(col, id, obj) { const row = toRow(col, obj); row.id = id; return fromRow(col, ok(await sb.from(col).upsert(row).select().single())); },
    async patch(col, id, obj) { return fromRow(col, ok(await sb.from(col).update(toRow(col, obj)).eq("id", id).select().single())); },
    async del(col, id) { ok(await sb.from(col).delete().eq("id", id)); },
    join: {
      async submit(j) { const s = await API.auth.session(); ok(await sb.from("join_requests").upsert({ user_id: s.uid, name: j.name, emp_no: j.empNo, phone: j.phone, region: j.region, skills: j.skills || [], status: "pending", reason: null, requested_at: new Date().toISOString() })); },
      async all() { return ok(await sb.from("join_requests").select("*").order("requested_at", { ascending: false })).map(mJoin); },
      async approve(userId, linkEngineerId) { return ok(await sb.rpc("approve_engineer", { p_user: userId, p_link_engineer: linkEngineerId || null })); },
      async reject(userId, reason) { ok(await sb.rpc("reject_engineer", { p_user: userId, p_reason: reason || null })); },
    },
    files: {
      async upload(file) { const path = Date.now() + "-" + file.name.replace(/[^\w.\-]+/g, "_"); ok(await sb.storage.from("eng-files").upload(path, file)); return path; },
      async url(path) { const { data, error } = await sb.storage.from("eng-files").createSignedUrl(path, 600); if (error) throw error; return data.signedUrl; },
    },
  };
})();
