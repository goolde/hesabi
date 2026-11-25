/* =====================================================================
   API layer — المحاسب الشامل
   كل اتصال بالخادم يمر من هنا فقط. الواجهات لا تعرف شيئاً عن Supabase.
   لاستبدال الخادم لاحقاً (مثلاً Python/FastAPI) يكفي إعادة كتابة هذا الملف
   بنفس أسماء الدوال ونفس أشكال البيانات المرجعة.
   ===================================================================== */
(function () {
  const cfg = window.APP_CONFIG || {};
  const sb = (window.supabase && cfg.SUPABASE_URL)
    ? window.supabase.createClient(cfg.SUPABASE_URL, cfg.SUPABASE_KEY, { auth: { persistSession: true, autoRefreshToken: true, storageKey: cfg.STORAGE_KEY || "shamel-auth" } })
    : null;

  const ok = ({ data, error }) => { if (error) throw normErr(error); return data; };
  function normErr(e) {
    const m = String(e && (e.message || e.error_description || e) || "");
    const map = [
      [/Invalid login credentials/i, "البريد أو كلمة المرور غير صحيحة."],
      [/Email not confirmed/i, "لم يتم تأكيد البريد بعد. افتح رسالة التفعيل في بريدك."],
      [/User already registered/i, "هذا البريد مسجل مسبقاً. سجّل الدخول بدلاً من ذلك."],
      [/Password should be at least/i, "كلمة المرور قصيرة، استخدم 8 أحرف على الأقل."],
      [/row-level security|permission denied|not allowed/i, "ليست لديك صلاحية لهذا الإجراء."],
      [/invalid_code/i, "رمز التفعيل غير صحيح."],
      [/code_used/i, "رمز التفعيل استُخدم من قبل."],
      [/mime type|not supported/i, "نوع الملف غير مسموح. المسموح: صور PNG/JPG/WebP/GIF وفيديو MP4/WebM وPDF."],
      [/exceeded the maximum allowed size|Payload too large/i, "حجم الملف أكبر من المسموح (50 ميغابايت)."],
      [/rate limit/i, "محاولات كثيرة، انتظر قليلاً ثم أعد المحاولة."],
      [/Failed to fetch|NetworkError/i, "تعذر الاتصال بالخادم. تحقق من الإنترنت."],
    ];
    const hit = map.find(([r]) => r.test(m));
    const err = new Error(hit ? hit[1] : "حدث خطأ، حاول مرة أخرى.");
    err.raw = m; return err;
  }
  const ts = v => v ? new Date(v).getTime() : 0;
  const need = () => { if (!sb) throw new Error("الخادم غير مهيأ."); };

  /* ---------- mappers: DB row -> app model ---------- */
  const mJob = r => ({ id: r.id, owner: r.user_id, title: r.title, company: r.company, city: r.city, type: r.job_type, salary: r.salary, desc: r.description, contact: r.contact, featured: r.featured, status: r.status, exp: ts(r.expires_at), at: ts(r.created_at) });
  const mReq = r => ({ id: r.id, owner: r.user_id, type: r.type, product: r.product, company: r.company, name: r.name, phone: r.phone, email: r.email, city: r.city, details: r.details || {}, notes: r.notes, status: r.status, price: r.price, reply: r.reply, published: r.published, at: ts(r.created_at), upd: ts(r.updated_at) });
  const mAd = r => ({ id: r.id, title: r.title, text: r.body, link: r.link, cta: r.cta, placement: r.placement, start: ts(r.start_at), end: ts(r.end_at), active: r.active, paid: !!r.request_id || !!r.price, price: r.price, at: ts(r.created_at) });
  const mOffice = r => ({ id: r.id, owner: r.user_id, name: r.name, city: r.city, license: r.license_no, cr: r.cr_no, phone: r.phone, email: r.email, contact: r.phone || r.email, services: r.services, verified: r.verified, status: r.status, at: ts(r.created_at) });
  const mEvent = r => ({ id: r.id, t: r.title, date: r.starts_at ? r.starts_at.slice(0, 10) : "", city: r.city, place: r.place, org: r.organizer, url: r.url, d: r.description, at: ts(r.created_at) });
  const mNote = r => ({ id: r.id, t: r.title, s: r.body, href: r.link, read: !!r.read_at, at: ts(r.created_at) });
  const mProfile = r => r && ({ id: r.id, name: r.full_name || "", phone: r.phone || "", city: r.city || "", company: r.company || "", role: r.role, email: r.email || "", at: ts(r.created_at), seen: ts(r.last_seen) });

  const API = {
    ready: !!sb,

    /* ---------------- auth ---------------- */
    auth: {
      async session() { if (!sb) return null; const { data } = await sb.auth.getSession(); return data.session ? { uid: data.session.user.id, email: data.session.user.email } : null; },
      onChange(fn) { if (!sb) return () => {}; const { data } = sb.auth.onAuthStateChange((_e, s) => fn(s ? { uid: s.user.id, email: s.user.email } : null)); return () => data.subscription.unsubscribe(); },
      async signUp({ email, password, name, phone, city }) { need(); return ok(await sb.auth.signUp({ email, password, options: { data: { full_name: name, phone, city }, emailRedirectTo: location.origin + location.pathname } })); },
      async signIn({ email, password }) { need(); return ok(await sb.auth.signInWithPassword({ email, password })); },
      async signOut() { if (sb) await sb.auth.signOut(); },
      async resetPassword(email) { need(); return ok(await sb.auth.resetPasswordForEmail(email, { redirectTo: location.origin + location.pathname + "#reset" })); },
      async updatePassword(password) { need(); return ok(await sb.auth.updateUser({ password })); },
    },

    /* ---------------- profile ---------------- */
    profile: {
      async me() { const s = await API.auth.session(); if (!s) return null; const r = ok(await sb.from("profiles").select("*").eq("id", s.uid).maybeSingle()); sb.from("profiles").update({ last_seen: new Date().toISOString() }).eq("id", s.uid).then(() => {}); return mProfile(r); },
      async update(p) { const s = await API.auth.session(); return mProfile(ok(await sb.from("profiles").update({ full_name: p.name, phone: p.phone, city: p.city, company: p.company }).eq("id", s.uid).select().single())); },
    },

    /* ---------------- academy ---------------- */
    academy: {
      async load() { const s = await API.auth.session(); if (!s) return null; const r = ok(await sb.from("academy_state").select("state,updated_at").eq("user_id", s.uid).maybeSingle()); return r ? { state: r.state, at: ts(r.updated_at) } : null; },
      async save(state) { const s = await API.auth.session(); if (!s) return; ok(await sb.from("academy_state").upsert({ user_id: s.uid, state, updated_at: new Date().toISOString() })); },
      async issueCertificate({ track, holder, score }) { ok(await sb.from("certificates").upsert({ track, holder_name: holder, score }, { onConflict: "user_id,track" })); },
      async myCertificates() { return ok(await sb.from("certificates").select("code,track,holder_name,score,issued_at").order("issued_at")); },
      async verify(code) { const r = ok(await sb.rpc("verify_certificate", { p_code: code })); return r && r[0] ? { holder: r[0].holder_name, track: r[0].track, at: ts(r[0].issued_at) } : null; },
    },

    /* ---------------- requests (order portal) ---------------- */
    requests: {
      async create(r) { need(); const s = await API.auth.session(); ok(await sb.from("requests").insert({ user_id: s ? s.uid : null, type: r.type, product: r.product, company: r.company, name: r.name, phone: r.phone, email: r.email, city: r.city, notes: r.notes, details: r.details || {} })); },
      async mine() { const s = await API.auth.session(); if (!s) return []; return ok(await sb.from("requests").select("*").eq("user_id", s.uid).order("created_at", { ascending: false })).map(mReq); },
      async all() { return ok(await sb.from("requests").select("*").order("created_at", { ascending: false }).limit(2000)).map(mReq); },
      async update(id, p) { const row = {}; if ("status" in p) row.status = p.status; if ("price" in p) row.price = p.price === "" ? null : p.price; if ("reply" in p) row.reply = p.reply; if ("published" in p) row.published = p.published; return mReq(ok(await sb.from("requests").update(row).eq("id", id).select().single())); },
      async remove(id) { ok(await sb.from("requests").delete().eq("id", id)); },
    },

    /* ---------------- ads ---------------- */
    ads: {
      async active() { if (!sb) return []; return ok(await sb.from("ads").select("*").eq("active", true).order("created_at", { ascending: false })).map(mAd).filter(a => (!a.start || a.start <= Date.now()) && (!a.end || a.end >= Date.now())); },
      async all() { return ok(await sb.from("ads").select("*").order("created_at", { ascending: false })).map(mAd); },
      async create(a) { ok(await sb.from("ads").insert({ title: a.title, body: a.text, link: a.link || null, cta: a.cta, placement: a.placement, start_at: a.start ? new Date(a.start).toISOString() : null, end_at: a.end ? new Date(a.end).toISOString() : null, price: a.price || null, request_id: a.requestId || null, active: true })); },
      async setActive(id, active) { ok(await sb.from("ads").update({ active }).eq("id", id)); },
      async remove(id) { ok(await sb.from("ads").delete().eq("id", id)); },
    },

    /* ---------------- jobs & alerts ---------------- */
    jobs: {
      async list() { if (!sb) return []; return ok(await sb.from("jobs").select("*").eq("status", "published").gte("expires_at", new Date().toISOString()).order("featured", { ascending: false }).order("created_at", { ascending: false }).limit(500)).map(mJob); },
      async all() { return ok(await sb.from("jobs").select("*").order("created_at", { ascending: false }).limit(2000)).map(mJob); },
      async create(j) { const days = Number(j.days) || 30; ok(await sb.from("jobs").insert({ title: j.title, company: j.company, city: j.city, job_type: j.type, salary: j.salary, description: j.desc, contact: j.contact, expires_at: new Date(Date.now() + days * 864e5).toISOString() })); },
      async update(id, p) { const row = {}; if ("featured" in p) row.featured = p.featured; if ("status" in p) row.status = p.status; ok(await sb.from("jobs").update(row).eq("id", id)); },
      async remove(id) { ok(await sb.from("jobs").delete().eq("id", id)); },
    },
    alerts: {
      async mine() { const s = await API.auth.session(); if (!s) return null; const r = ok(await sb.from("job_alerts").select("*").eq("user_id", s.uid).maybeSingle()); return r ? { kw: (r.keywords || []).join("، "), city: r.city || "" } : null; },
      async set({ kw, city }) { const keywords = String(kw || "").split(/[،,]\s*/).map(x => x.trim()).filter(Boolean); ok(await sb.from("job_alerts").upsert({ keywords, city: city || null })); },
      async remove() { const s = await API.auth.session(); ok(await sb.from("job_alerts").delete().eq("user_id", s.uid)); },
      async count() { const { count } = await sb.from("job_alerts").select("*", { count: "exact", head: true }); return count || 0; },
    },

    /* ---------------- notifications ---------------- */
    notifications: {
      async list() { const s = await API.auth.session(); if (!s) return []; return ok(await sb.from("notifications").select("*").eq("user_id", s.uid).order("created_at", { ascending: false }).limit(100)).map(mNote); },
      async markAllRead() { const s = await API.auth.session(); ok(await sb.from("notifications").update({ read_at: new Date().toISOString() }).eq("user_id", s.uid).is("read_at", null)); },
      subscribe(uid, fn) { if (!sb || !uid) return () => {}; const ch = sb.channel("notes-" + uid).on("postgres_changes", { event: "INSERT", schema: "public", table: "notifications", filter: "user_id=eq." + uid }, p => fn(mNote(p.new))).subscribe(); return () => sb.removeChannel(ch); },
    },

    /* ---------------- offices ---------------- */
    offices: {
      async list() { if (!sb) return []; return ok(await sb.from("offices").select("*").eq("status", "approved").order("verified", { ascending: false }).order("name")).map(mOffice); },
      async mine() { const s = await API.auth.session(); if (!s) return null; const r = ok(await sb.from("offices").select("*").eq("user_id", s.uid).order("created_at", { ascending: false }).limit(1)); return r[0] ? mOffice(r[0]) : null; },
      async register(o) { ok(await sb.from("offices").insert({ name: o.name, city: o.city, license_no: o.license, cr_no: o.cr, services: o.services, phone: o.contact })); },
      async all() { return ok(await sb.from("offices").select("*").order("created_at", { ascending: false })).map(mOffice); },
      async update(id, p) { const row = {}; if ("verified" in p) row.verified = p.verified; if ("status" in p) row.status = p.status; ok(await sb.from("offices").update(row).eq("id", id)); },
      async remove(id) { ok(await sb.from("offices").delete().eq("id", id)); },
    },

    /* ---------------- events ---------------- */
    events: {
      async list() { if (!sb) return []; return ok(await sb.from("events").select("*").order("starts_at", { ascending: true })).map(mEvent); },
      async create(e) { ok(await sb.from("events").insert({ title: e.t, starts_at: e.date ? new Date(e.date + "T09:00:00+03:00").toISOString() : null, city: e.city, place: e.place, organizer: e.org, url: e.url || null, description: e.d })); },
      async remove(id) { ok(await sb.from("events").delete().eq("id", id)); },
    },

    /* ---------------- site settings ---------------- */
    content: {
      async all() {
        if (!sb) return {};
        const rows = ok(await sb.from("site_content").select("key,title,mode,blocks,updated_at"));
        const o = {}; (rows || []).forEach(r => { o[r.key] = { title: r.title || "", mode: r.mode || "append", blocks: Array.isArray(r.blocks) ? r.blocks : [], at: Date.parse(r.updated_at) }; });
        return o;
      },
      async save(key, { title, mode, blocks }) { need(); ok(await sb.from("site_content").upsert({ key, title, mode, blocks })); },
      async remove(key) { need(); ok(await sb.from("site_content").delete().eq("key", key)); },
      async upload(file) {
        need();
        if (file.size > 50 * 1024 * 1024) throw new Error("حجم الملف أكبر من 50 ميغابايت. للفيديوهات الطويلة ارفعها على يوتيوب وضع رابطها.");
        const ext = ((file.name || "").split(".").pop() || "bin").toLowerCase().replace(/[^a-z0-9]/g, "").slice(0, 5) || "bin";
        const id = (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2));
        const path = new Date().toISOString().slice(0, 7) + "/" + id + "." + ext;
        ok(await sb.storage.from("media").upload(path, file, { contentType: file.type, upsert: false }));
        return sb.storage.from("media").getPublicUrl(path).data.publicUrl;
      },
    },

    settings: {
      async get() { if (!sb) return {}; const r = ok(await sb.from("settings").select("value").eq("key", "site").maybeSingle()); return r ? r.value : {}; },
      async set(v) { ok(await sb.from("settings").upsert({ key: "site", value: v, updated_at: new Date().toISOString() })); },
    },

    /* ---------------- newsletter ---------------- */
    subscribers: {
      async add(email) { need(); const { error } = await sb.from("subscribers").insert({ email: email.toLowerCase() }); if (error && !/duplicate/i.test(error.message)) throw normErr(error); },
      async list() { return ok(await sb.from("subscribers").select("*").order("created_at", { ascending: false })).map(r => ({ email: r.email, at: ts(r.created_at) })); },
      async remove(email) { ok(await sb.from("subscribers").delete().eq("email", email)); },
    },

    /* ---------------- Q&A ---------------- */
    qa: {
      async list() { if (!sb) return []; const q = ok(await sb.from("questions").select("id,user_id,body,created_at,answers(id,user_id,body,created_at)").order("created_at", { ascending: false }).limit(200)); return q.map(r => ({ id: r.id, owner: r.user_id, q: r.body, at: ts(r.created_at), answers: (r.answers || []).sort((a, b) => ts(a.created_at) - ts(b.created_at)).map(a => ({ id: a.id, owner: a.user_id, a: a.body, at: ts(a.created_at) })) })); },
      async ask(body) { ok(await sb.from("questions").insert({ body })); },
      async answer(qid, body) { ok(await sb.from("answers").insert({ question_id: qid, body })); },
      async remove(id) { ok(await sb.from("questions").delete().eq("id", id)); },
    },

    /* ---------------- users (admin) ---------------- */
    users: {
      async list() { return ok(await sb.from("profiles").select("*").order("created_at", { ascending: false }).limit(5000)).map(mProfile); },
      async claimAdmin(code) { ok(await sb.rpc("claim_admin", { p_code: code })); },
      async setRole(id, role) { ok(await sb.from("profiles").update({ role }).eq("id", id)); },
      async progress() { return ok(await sb.from("academy_state").select("user_id,state,updated_at")).map(r => ({ uid: r.user_id, state: r.state || {}, at: ts(r.updated_at) })); },
      async certificates() { return ok(await sb.from("certificates").select("*").order("issued_at", { ascending: false })).map(r => ({ code: r.code, uid: r.user_id, track: r.track, holder: r.holder_name, score: r.score, at: ts(r.issued_at) })); },
    },
  };
  window.API = API;
  window.__sb = sb; /* shared client for extensions such as API.eng (engineers portal) */
})();
