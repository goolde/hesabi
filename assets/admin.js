/* =====================================================================
   بوابة الإدارة — دخول مستقل، لا تعمل إلا لحساب دوره admin
   كل البيانات عبر window.API (assets/api.js)
   ===================================================================== */
(function(){
const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const when=ms=>ms?new Date(ms).toLocaleDateString("ar-SA-u-ca-gregory-nu-latn",{year:"numeric",month:"short",day:"numeric"}):"";
const num=n=>Number(n||0).toLocaleString("en-US",{maximumFractionDigits:2});
const TRACKS=window.TRACK_TITLES||{};
const TYPES={quote:"عرض سعر",demo:"نسخة تجريبية",training:"تدريب",support:"دعم فني",renew:"تجديد صيانة أو اشتراك",ad:"إعلان مدفوع",consult:"استشارة",other:"أخرى"};
const STAT={new:["جديد","st-new"],work:["قيد المتابعة","st-work"],await:["بانتظار الدفع","st-pay"],paid:["مدفوع","st-done"],done:["مكتمل","st-done"],cancel:["ملغي","st-cancel"]};
const PLACEMENTS={home:"الصفحة الرئيسية",events:"صفحة الفعاليات",jobs:"صفحة الوظائف",academy:"الأكاديمية"};
const ROLES={student:"طالب / عميل",engineer:"مهندس صيانة",admin:"إدارة"};
const DET={users:"المستخدمون/الطرفيات",pos:"نقاط البيع",mode:"نوع التدريب",place:"مكان الإعلان",weeks:"المدة بالأسابيع",atitle:"عنوان الإعلان",atext:"نص الإعلان",alink:"الرابط",acta:"نص الزر"};

const A={me:null,tab:"dash",data:{},loaded:false,f:{status:"",type:"",q:"",role:""}};

/* ---------- shell ---------- */
function shell(inner){return inner}
function vLogin(msg){
 return `<div class="auth6"><div class="panel"><div class="eyebrow">للإدارة فقط</div><h1 style="font-size:28px">دخول لوحة الإدارة</h1>
 ${msg?`<p class="msg bad">${msg}</p>`:""}
 <form id="admLogin" class="form5 one"><label>البريد الإلكتروني<input id="al_email" type="email" dir="ltr" required autocomplete="username"></label><label>كلمة المرور<input id="al_pass" type="password" dir="ltr" required autocomplete="current-password"></label><div class="full"><button class="btn" type="submit">دخول</button></div></form><div id="alMsg"></div>
 <p class="fine" style="margin-top:14px">هذه البوابة منفصلة عن دخول الطلاب. الطلاب والعملاء يدخلون من <a href="index.html#login">الموقع الرئيسي</a>.</p></div></div>`}
function vDenied(){return `<div class="auth6"><div class="panel"><h1 style="font-size:26px">لا تملك صلاحية الإدارة</h1><p class="lead">الحساب <b dir="ltr">${esc(A.me.email)}</b> مسجل كـ «${esc(ROLES[A.me.role]||A.me.role)}». اطلب من مدير المنصة ترقية حسابك.</p><form id="claimForm" class="it6" style="margin:14px 0"><label>لديك رمز تفعيل الإدارة؟ (يُستخدم مرة واحدة فقط)<input id="cl_code" dir="ltr" required placeholder="AMAN-XXXXXXXX"></label><button class="btn">تفعيل</button><div id="clMsg"></div></form><button class="btn ghost" data-act="signout">تسجيل الخروج</button></div></div>`}

/* ---------- data ---------- */
async function load(){
 const [requests,ads,jobs,offices,events,users,subs,settings,certs,alertsN]=await Promise.all([
  API.requests.all(),API.ads.all(),API.jobs.all(),API.offices.all(),API.events.list(),API.users.list(),API.subscribers.list(),API.settings.get(),API.users.certificates(),API.alerts.count()]);
 A.data={requests,ads,jobs,offices,events,users,subs,settings:settings||{},certs,alertsN};A.loaded=true;if(window.THEME)THEME.apply((settings||{}).theme||null,true);
}
async function reload(){try{await load()}catch(e){toast(e.message,true)}render()}

/* ---------- helpers ---------- */
const countBy=(arr,f)=>arr.reduce((o,x)=>{const k=f(x);if(k)o[k]=(o[k]||0)+1;return o},{});
function bars(obj){const e=Object.entries(obj).sort((a,b)=>b[1]-a[1]).slice(0,12);const m=Math.max(1,...e.map(x=>x[1]));return e.length?`<div class="bars">${e.map(([k,v])=>`<div class="bar5"><span title="${esc(k)}">${esc(k)}</span><span class="tr"><span class="fl" style="width:${v/m*100}%"></span></span><span class="v">${v}</span></div>`).join("")}</div>`:`<p class="fine">لا توجد بيانات بعد.</p>`}
const month=ms=>{const d=new Date(ms);return d.getFullYear()+"/"+String(d.getMonth()+1).padStart(2,"0")};
function csv(rows,name){const q=v=>`"${String(v??"").replace(/"/g,'""')}"`;const txt="﻿"+rows.map(r=>r.map(q).join(",")).join("\r\n");const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([txt],{type:"text/csv"}));a.download=name+".csv";document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove()},500)}
function toast(m,bad){const t=$("#toast");t.innerHTML=`<p class="msg ${bad?"bad":"ok"}">${esc(m)}</p>`;clearTimeout(toast.t);toast.t=setTimeout(()=>t.innerHTML="",3500)}
async function run(fn,okMsg){try{await fn();await reload();if(okMsg)toast(okMsg)}catch(e){toast(e.message,true)}}
const userName=id=>{const u=A.data.users.find(x=>x.id===id);return u?(u.name||u.email):""};

/* ---------- tabs ---------- */
const TABS=[["dash","المؤشرات والتقارير"],["requests","الطلبات"],["ads","الإعلانات"],["jobs","الوظائف"],["offices","المكاتب"],["events","الفعاليات"],["users","المستخدمون"],["academy","الأكاديمية"],["content","المحتوى والفيديوهات"],["subs","النشرة"],["settings","الإعدادات"],["guide","دليل التشغيل"]];
function tabs(){const pend=A.data.offices.filter(o=>o.status==="pending").length,newR=A.data.requests.filter(r=>r.status==="new").length;
 return `<div class="tabs5">${TABS.map(([k,t])=>`<a href="#${k}" class="${A.tab===k?"on":""}">${t}${k==="requests"&&newR?` <span class="chip warn">${newR}</span>`:""}${k==="offices"&&pend?` <span class="chip warn">${pend}</span>`:""}</a>`).join("")}</div>`}

function vDash(){const {requests:R,ads,jobs:J,offices:O,users:U,subs,certs}=A.data,now=Date.now(),D30=30*864e5;
 const rev=R.filter(r=>r.type==="ad"&&["paid","done"].includes(r.status)).reduce((a,r)=>a+Number(r.price||0),0);
 const k=[["إجمالي الطلبات",R.length,1],["طلبات جديدة",R.filter(r=>r.status==="new").length],["قيد المتابعة",R.filter(r=>r.status==="work"||r.status==="await").length],["مكتملة",R.filter(r=>r.status==="done").length],["إيراد الإعلانات (ريال)",num(rev)],["إعلانات نشطة",ads.filter(a=>a.active&&(!a.end||a.end>=now)).length],
  ["المستخدمون",U.length,1],["الطلاب/العملاء",U.filter(u=>u.role==="student").length],["المهندسون",U.filter(u=>u.role==="engineer").length],["تسجيلات آخر 30 يوماً",U.filter(u=>u.at>now-D30).length],["الشهادات الصادرة",certs.length],["وظائف نشطة",J.filter(j=>j.status==="published"&&j.exp>=now).length],["مكاتب بانتظار المراجعة",O.filter(o=>o.status==="pending").length],["مشتركو النشرة",subs.length],["تنبيهات وظائف مفعلة",A.data.alertsN]];
 return `<div class="kpis">${k.map(([t,v,hi])=>`<div class="kpi ${hi?"hi":""}"><b>${v}</b><span>${t}</span></div>`).join("")}</div>
 <div class="grid3">
 <div class="panel"><h3>الطلبات حسب النوع</h3>${bars(countBy(R,r=>TYPES[r.type]||r.type))}</div>
 <div class="panel"><h3>الطلبات حسب المنتج</h3>${bars(countBy(R,r=>r.product))}</div>
 <div class="panel"><h3>الطلبات حسب الحالة</h3>${bars(countBy(R,r=>STAT[r.status]?.[0]))}</div>
 <div class="panel"><h3>الطلبات حسب الشهر</h3>${bars(countBy(R,r=>month(r.at)))}</div>
 <div class="panel"><h3>الطلبات حسب المدينة</h3>${bars(countBy(R,r=>r.city))}</div>
 <div class="panel"><h3>التسجيلات حسب الشهر</h3>${bars(countBy(U,u=>month(u.at)))}</div>
 <div class="panel"><h3>المستخدمون حسب المدينة</h3>${bars(countBy(U,u=>u.city))}</div>
 <div class="panel"><h3>الشهادات حسب المرحلة</h3>${bars(countBy(certs,c=>TRACKS[c.track]||c.track))}</div>
 <div class="panel"><h3>الوظائف حسب المدينة</h3>${bars(countBy(J,j=>j.city))}</div></div>
 <div class="row-acts" style="margin-top:14px"><button class="btn" data-exp="requests">تصدير الطلبات (Excel)</button><button class="btn ghost" data-exp="users">تصدير المستخدمين</button><button class="btn ghost" data-exp="jobs">تصدير الوظائف</button><button class="btn ghost" data-exp="certs">تصدير الشهادات</button><button class="btn ghost" data-exp="subs">تصدير المشتركين</button></div>`}

function vRequests(){const f=A.f;let R=A.data.requests.filter(r=>(!f.status||r.status===f.status)&&(!f.type||r.type===f.type)&&(!f.q||(r.name+" "+(r.company||"")+" "+(r.phone||"")+" "+(r.product||"")).includes(f.q)));
 return `<p class="fine">لترقية مهندس صيانة: يسجّل المهندس من <a href="engineers.html">بوابة المهندسين</a> ويقدّم طلب انضمام، ثم تعتمده أنت من هناك (الإدارة ← طلبات الانضمام).</p><div class="filters5"><input id="f_q" placeholder="بحث بالاسم أو المنشأة أو الجوال" value="${esc(f.q)}"><select id="f_status"><option value="">كل الحالات</option>${Object.entries(STAT).map(([k,v])=>`<option value="${k}" ${k===f.status?"selected":""}>${v[0]}</option>`).join("")}</select><select id="f_type"><option value="">كل الأنواع</option>${Object.entries(TYPES).map(([k,v])=>`<option value="${k}" ${k===f.type?"selected":""}>${v}</option>`).join("")}</select><button class="btn sm ghost" data-exp="requests">تصدير</button></div>
 <div class="tablewrap"><table class="adm"><thead><tr><th>التاريخ</th><th>النوع / المنتج</th><th>العميل</th><th>التفاصيل</th><th>الحالة والإجراء</th></tr></thead><tbody>${R.map(r=>`<tr>
 <td>${when(r.at)}</td><td><b>${esc(TYPES[r.type]||r.type)}</b><br>${esc(r.product||"")}</td>
 <td>${esc(r.name)}<br>${esc(r.company||"")}<br><span dir="ltr">${esc(r.phone||"")}</span><br><span dir="ltr">${esc(r.email||"")}</span><br>${esc(r.city||"")}${r.owner?`<br><span class="chip">حساب مسجل</span>`:`<br><span class="chip">زائر</span>`}</td>
 <td>${Object.entries(r.details||{}).map(([k,v])=>`${esc(DET[k]||k)}: ${esc(v)}`).join("<br>")}${r.notes?`<p style="margin:6px 0 0">${esc(r.notes)}</p>`:""}</td>
 <td><span class="st ${STAT[r.status]?.[1]||""}">${STAT[r.status]?.[0]||esc(r.status)}</span>
  <div class="row-acts" style="margin-top:6px"><select data-rstat="${r.id}">${Object.entries(STAT).map(([k,v])=>`<option value="${k}" ${k===r.status?"selected":""}>${v[0]}</option>`).join("")}</select><input data-rprice="${r.id}" placeholder="السعر" value="${esc(r.price??"")}" size="7" inputmode="decimal"><input data-rreply="${r.id}" placeholder="رد للعميل" value="${esc(r.reply||"")}"><button class="btn sm" data-act="rsave" data-id="${r.id}">حفظ</button>
  ${r.type==="ad"&&r.status==="paid"&&!r.published?`<button class="btn sm order" data-act="rpublish" data-id="${r.id}">نشر الإعلان</button>`:""}${r.published?`<span class="chip">منشور</span>`:""}</div></td></tr>`).join("")||`<tr><td colspan="5">لا توجد طلبات.</td></tr>`}</tbody></table></div>`}

function vAds(){const st=A.data.settings;
 return `<div class="two"><div class="panel"><h3>إعلان جديد</h3><form id="adForm" class="form5"><label class="full">العنوان<input id="ad_t" required maxlength="80"></label><label class="full">النص<input id="ad_x" maxlength="200"></label><label>المكان<select id="ad_p">${Object.entries(PLACEMENTS).map(([k,v])=>`<option value="${k}">${v}${st.adPrices&&st.adPrices[k]?` · ${esc(st.adPrices[k])} ريال/أسبوع`:""}</option>`).join("")}</select></label><label>الرابط (https)<input id="ad_l" dir="ltr" placeholder="https://"></label><label>نص الزر<input id="ad_c" value="التفاصيل" maxlength="24"></label><label>السعر المدفوع (اختياري)<input id="ad_pr" inputmode="decimal"></label><label>من تاريخ<input id="ad_s" type="date"></label><label>إلى تاريخ<input id="ad_e" type="date"></label><div class="full"><button class="btn" type="submit">نشر</button></div></form></div>
 <div class="panel"><h3>الإعلانات</h3>${A.data.ads.length?A.data.ads.map(a=>`<div class="it6"><div><b>${esc(a.title)}</b> <span class="chip">${esc(PLACEMENTS[a.placement]||a.placement)}</span> ${a.active?'<span class="st st-done">نشط</span>':'<span class="st st-cancel">موقوف</span>'}<p class="fine">${a.start?when(a.start):"—"} ← ${a.end?when(a.end):"بلا نهاية"}${a.price?` · ${num(a.price)} ريال`:""}</p></div><div class="row-acts"><button class="btn sm ghost" data-act="adtoggle" data-id="${a.id}" data-v="${a.active?0:1}">${a.active?"إيقاف":"تفعيل"}</button><button class="btn sm ghost" data-act="addel" data-id="${a.id}">حذف</button></div></div>`).join(""):`<p class="fine">لا توجد إعلانات.</p>`}</div></div>`}

function vJobs(){const now=Date.now();
 return `<div class="tablewrap"><table class="adm"><thead><tr><th>الوظيفة</th><th>الناشر</th><th>النشر / الانتهاء</th><th>الحالة</th><th>إجراء</th></tr></thead><tbody>${A.data.jobs.map(j=>`<tr><td><b>${esc(j.title)}</b><br>${esc(j.company||"")} · ${esc(j.city||"")} · ${esc(j.type||"")}${j.featured?' <span class="chip gold">مميزة</span>':""}</td><td>${esc(userName(j.owner))}<br><span dir="ltr">${esc(j.contact||"")}</span></td><td>${when(j.at)}<br>${when(j.exp)}${j.exp<now?' <span class="chip">منتهية</span>':""}</td><td>${j.status==="published"?"منشورة":j.status==="hidden"?"مخفية":"بانتظار"}</td>
 <td class="row-acts"><button class="btn sm ghost" data-act="jfeat" data-id="${j.id}" data-v="${j.featured?0:1}">${j.featured?"إلغاء التمييز":"تمييز"}</button><button class="btn sm ghost" data-act="jhide" data-id="${j.id}" data-v="${j.status==="published"?"hidden":"published"}">${j.status==="published"?"إخفاء":"إظهار"}</button><button class="btn sm ghost" data-act="jdel" data-id="${j.id}">حذف</button></td></tr>`).join("")||`<tr><td colspan="5">لا توجد وظائف.</td></tr>`}</tbody></table></div>`}

function vOffices(){const O=A.data.offices;const pend=O.filter(o=>o.status==="pending"),rest=O.filter(o=>o.status!=="pending");
 const row=o=>`<div class="it6"><div><b>${esc(o.name)}</b> ${o.verified?'<span class="chip trust">✓ ثقة</span>':""} <span class="chip">${esc(o.city||"")}</span><p class="fine">ترخيص SOCPA <span dir="ltr">${esc(o.license||"—")}</span> · السجل <span dir="ltr">${esc(o.cr||"—")}</span> · ${esc(o.services||"")} · <span dir="ltr">${esc(o.contact||"")}</span> · ${when(o.at)}</p></div><div class="row-acts">
 ${o.status==="pending"?`<button class="btn sm" data-act="oapprove" data-id="${o.id}" data-v="1">اعتماد مع الثقة</button><button class="btn sm ghost" data-act="oapprove" data-id="${o.id}" data-v="0">اعتماد دون ثقة</button><button class="btn sm ghost" data-act="oreject" data-id="${o.id}">رفض</button>`:`<button class="btn sm ghost" data-act="otrust" data-id="${o.id}" data-v="${o.verified?0:1}">${o.verified?"سحب الثقة":"منح الثقة"}</button><button class="btn sm ghost" data-act="odel" data-id="${o.id}">حذف</button>`}</div></div>`;
 return `<div class="panel"><h3>طلبات التسجيل (${pend.length})</h3><p class="fine">تحقق من الترخيص في موقع الهيئة السعودية للمراجعين والمحاسبين ومن السجل التجاري قبل منح شارة «ثقة».</p>${pend.map(row).join("")||'<p class="fine">لا توجد طلبات جديدة.</p>'}</div>
 <div class="panel" style="margin-top:14px"><h3>المكاتب (${rest.length})</h3>${rest.map(row).join("")||'<p class="fine">لا توجد مكاتب.</p>'}</div>`}

function vEvents(){return `<div class="two"><div class="panel"><h3>فعالية جديدة</h3><form id="evForm" class="form5"><label class="full">العنوان<input id="ev_t" required maxlength="140"></label><label>التاريخ<input id="ev_d" type="date"></label><label>المدينة<input id="ev_c" maxlength="60"></label><label>المكان<input id="ev_p" maxlength="120"></label><label>الجهة المنظمة<input id="ev_o" maxlength="120"></label><label class="full">رابط التسجيل (https)<input id="ev_u" dir="ltr" placeholder="https://"></label><label class="full">طريقة التسجيل / وصف<textarea id="ev_x" rows="2" maxlength="600"></textarea></label><div class="full"><button class="btn" type="submit">إضافة</button></div></form></div>
 <div class="panel"><h3>الفعاليات المضافة</h3>${A.data.events.map(e=>`<div class="it6"><div><b>${esc(e.t)}</b><p class="fine">${esc(e.date)} · ${esc(e.city||"")} ${esc(e.place||"")} · ${esc(e.org||"")}</p></div><button class="btn sm ghost" data-act="evdel" data-id="${e.id}">حذف</button></div>`).join("")||'<p class="fine">لا توجد فعاليات مضافة. الفعاليات الرسمية الثابتة تظهر في الموقع تلقائياً.</p>'}</div></div>`}

function vUsers(){const f=A.f;const U=A.data.users.filter(u=>(!f.role||u.role===f.role)&&(!f.q||(u.name+" "+u.email+" "+u.phone+" "+u.city).includes(f.q)));
 return `<div class="filters5"><input id="f_q" placeholder="بحث بالاسم أو البريد أو الجوال" value="${esc(f.q)}"><select id="f_role"><option value="">كل الأدوار</option>${Object.entries(ROLES).map(([k,v])=>`<option value="${k}" ${k===f.role?"selected":""}>${v}</option>`).join("")}</select><button class="btn sm ghost" data-exp="users">تصدير</button></div>
 <div class="tablewrap"><table class="adm"><thead><tr><th>المستخدم</th><th>التواصل</th><th>التسجيل / آخر دخول</th><th>الدور</th></tr></thead><tbody>${U.map(u=>`<tr><td><b>${esc(u.name||"—")}</b><br>${esc(u.company||"")}</td><td><span dir="ltr">${esc(u.email)}</span><br><span dir="ltr">${esc(u.phone)}</span><br>${esc(u.city)}</td><td>${when(u.at)}<br>${u.seen?when(u.seen):"—"}</td>
 <td><select data-role="${u.id}" ${u.id===A.me.id?"disabled":""}>${Object.entries(ROLES).map(([k,v])=>`<option value="${k}" ${k===u.role?"selected":""}>${v}</option>`).join("")}</select></td></tr>`).join("")||`<tr><td colspan="4">لا يوجد مستخدمون.</td></tr>`}</tbody></table></div>
 <p class="fine">دور «مهندس صيانة» يفتح بوابة المهندسين. التحقق من المهندس (رقم وظيفي واعتماد) يتم من بوابة المهندسين.</p>`}

function vAcademy(){const C=A.data.certs;
 return `<div class="panel"><h3>الشهادات الصادرة (${C.length})</h3><div class="tablewrap"><table class="adm"><thead><tr><th>الرقم</th><th>الاسم</th><th>المرحلة</th><th>الدرجة</th><th>التاريخ</th></tr></thead><tbody>${C.map(c=>`<tr><td dir="ltr">${esc(c.code)}</td><td>${esc(c.holder||userName(c.uid))}</td><td>${esc(TRACKS[c.track]||c.track)}</td><td>${c.score??"—"}</td><td>${when(c.at)}</td></tr>`).join("")||'<tr><td colspan="5">لا توجد شهادات بعد.</td></tr>'}</tbody></table></div></div>`}

function vSubs(){return `<div class="panel"><h3>مشتركو النشرة (${A.data.subs.length})</h3><div class="row-acts" style="margin-bottom:10px"><button class="btn sm ghost" data-exp="subs">تصدير</button></div>${A.data.subs.map(s=>`<div class="it6"><span dir="ltr">${esc(s.email)}</span><span class="fine">${when(s.at)}</span><button class="btn sm ghost" data-act="subdel" data-id="${esc(s.email)}">حذف</button></div>`).join("")||'<p class="fine">لا يوجد مشتركون.</p>'}</div>`}

function vSettings(){const s=A.data.settings;const p=s.adPrices||{};
 return `<div class="panel"><h3>إعدادات المنصة</h3><form id="setForm" class="form5">${Object.entries(PLACEMENTS).map(([k,v])=>`<label>سعر الإعلان أسبوعياً: ${v} (ريال)<input id="sp_${k}" inputmode="decimal" value="${esc(p[k]||"")}"></label>`).join("")}
 <label class="full">طريقة الدفع (تظهر للعميل عند «بانتظار الدفع»)<textarea id="s_bank" rows="2" maxlength="400">${esc(s.bank||"")}</textarea></label><label>رقم واتساب التواصل<input id="s_wa" dir="ltr" value="${esc(s.whatsapp||"")}"></label><div class="full"><button class="btn" type="submit">حفظ الإعدادات</button></div></form>
 <p class="fine">لا توجد أسعار افتراضية؛ الأسعار التي تكتبها هنا هي ما يراه المعلن.</p></div>${vTheme()}`}
function vTheme(){const T=window.THEME;if(!T)return "";const cur=A.data.settings.theme||T.PRESETS[0];
 const sw=p=>`<button type="button" class="btn sm ghost" data-act="thpreset" data-id="${p.id}" title="${esc(p.name)}"><span style="display:inline-flex;gap:3px;vertical-align:middle;margin-inline-end:6px">${[p.navy,p.accent,p.gold].map(c=>`<i style="width:14px;height:14px;border-radius:4px;background:${c};display:inline-block"></i>`).join("")}</span>${esc(p.name)}</button>`;
 return `<div class="panel" style="margin-top:16px"><h3>ألوان الموقع</h3><p class="fine">اختر مجموعة جاهزة أو حدّد الألوان بنفسك. تتغير هذه الصفحة فوراً للمعاينة، ولا تظهر للزوار إلا بعد «حفظ الألوان».</p>
 <div class="row-acts" style="flex-wrap:wrap;margin:10px 0">${T.PRESETS.map(sw).join("")}</div>
 <form id="themeForm" class="form5"><label>اللون الأساسي (الأزرار والروابط)<input type="color" id="th_a" value="${esc(cur.accent)}"></label><label>اللون الثانوي (الشارات والتمييز)<input type="color" id="th_g" value="${esc(cur.gold)}"></label><label>لون الشريط العلوي<input type="color" id="th_n" value="${esc(cur.navy)}"></label>
 <div class="full row-acts"><button class="btn" type="submit">حفظ الألوان</button><button class="btn ghost" type="button" data-act="threset">الرجوع للألوان الافتراضية</button></div></form></div>`}
const thVal=()=>({accent:v("th_a"),gold:v("th_g"),navy:v("th_n")});

function vGuide(){return `<div class="two"><div class="panel"><h3>الإعلان المدفوع</h3><ol class="steps5"><li>المعلن يرسل طلب «إعلان مدفوع» من صفحة «اطلب خدمة».</li><li>يصلك إشعار، وتجد الطلب في «الطلبات». اكتب السعر والرد واجعل الحالة «بانتظار الدفع»، فيرى العميل السعر وطريقة الدفع في «طلباتي» ويصله إشعار.</li><li>بعد وصول التحويل اجعل الحالة «مدفوع» ثم اضغط «نشر الإعلان». ينشر في المكان والمدة المطلوبة ويختفي تلقائياً عند نهايتها.</li></ol></div>
 <div class="panel"><h3>الوظائف والتنبيهات</h3><ol class="steps5"><li>أي مستخدم مسجل ينشر وظيفة من صفحة الوظائف، وتنتهي تلقائياً بعد المدة المختارة.</li><li>من فعّل «تنبيه الوظائف» يصله إشعار فوري داخل المنصة عند نشر وظيفة تطابق كلماته أو مدينته.</li><li>من هنا تميّز الوظيفة أو تخفيها أو تحذفها.</li></ol></div>
 <div class="panel"><h3>الحسابات والأدوار</h3><ul class="steps5"><li>الطلاب والعملاء يسجلون من الموقع الرئيسي، ويتم حفظ تقدمهم وشهاداتهم في حساباتهم.</li><li>الإدارة تدخل من هذه البوابة فقط، ولا تفتح إلا لحساب دوره «إدارة».</li><li>المهندسون: دور «مهندس صيانة» بعد التحقق، ولهم بوابتهم.</li><li>الشهادات لها رقم يمكن التحقق منه علناً من صفحة «التحقق من شهادة».</li></ul></div>
 <div class="panel"><h3>ما زال يحتاج إعداداً خارجياً</h3><ul class="steps5"><li>الدفع الإلكتروني المباشر: بوابة سعودية (ميسر، HyperPay، Tap) بعقد تجاري.</li><li>إرسال الإشعارات بالبريد أو واتساب: مزود بريد (SMTP) وواتساب للأعمال.</li><li>نطاق باسم الشركة (مثل academy.aman…) يُربط بالاستضافة.</li></ul></div></div>`}

/* ---------- render ---------- */
function render(){
 const app=$("#app");
 if(!A.me){app.innerHTML=vLogin();return}
 if(A.me.role!=="admin"){app.innerHTML=vDenied();return}
 if(!A.loaded){app.innerHTML=`<p class="fine" style="margin-top:30px">جارٍ تحميل البيانات…</p>`;return}
 const V={dash:vDash,requests:vRequests,ads:vAds,jobs:vJobs,offices:vOffices,events:vEvents,users:vUsers,academy:vAcademy,content:()=>window.ContentAdmin?ContentAdmin.view():"",subs:vSubs,settings:vSettings,guide:vGuide}[A.tab]||vDash;
 const a=document.activeElement,fid=a&&a.id&&app.contains(a)?a.id:null,pos=fid&&a.selectionStart;
 app.innerHTML=`<div class="sechead" style="margin-top:22px"><div><div class="eyebrow">بوابة الإدارة</div><h1 style="font-size:28px">لوحة إدارة المنصة</h1></div><div class="row-acts"><span class="fine" dir="ltr">${esc(A.me.email)}</span><button class="btn sm ghost" data-act="reload">تحديث</button><button class="btn sm ghost" data-act="signout">خروج</button></div></div>${tabs()}<div id="toast"></div>${V()}`;
 if(fid){const el=document.getElementById(fid);if(el){el.focus();try{el.setSelectionRange(pos,pos)}catch(e){}}}
}
function route(){A.tab=(location.hash||"#dash").slice(1)||"dash";render();window.scrollTo(0,0)}
window.addEventListener("hashchange",route);

/* ---------- events ---------- */
const v=id=>(document.getElementById(id)?.value||"").trim();
document.addEventListener("submit",async e=>{const f=e.target;e.preventDefault();
 if(f.id==="admLogin"){const m=$("#alMsg");try{await API.auth.signIn({email:v("al_email"),password:$("#al_pass").value});await boot()}catch(err){m.innerHTML=`<p class="msg bad">${esc(err.message)}</p>`}}
 else if(f.id==="claimForm"){const m=$("#clMsg");try{await API.users.claimAdmin(v("cl_code"));await boot()}catch(err){m.innerHTML=`<p class="msg bad">${esc(err.message)}</p>`}}
 else if(f.id==="adForm"){const l=v("ad_l");if(l&&!/^https:\/\//i.test(l))return toast("الرابط يجب أن يبدأ بـ https://",true);run(()=>API.ads.create({title:v("ad_t"),text:v("ad_x"),placement:v("ad_p"),link:l,cta:v("ad_c"),price:v("ad_pr"),start:v("ad_s"),end:v("ad_e")?v("ad_e")+"T23:59:59":""}),"نُشر الإعلان.")}
 else if(f.id==="evForm"){const u=v("ev_u");if(u&&!/^https:\/\//i.test(u))return toast("الرابط يجب أن يبدأ بـ https://",true);run(()=>API.events.create({t:v("ev_t"),date:v("ev_d"),city:v("ev_c"),place:v("ev_p"),org:v("ev_o"),url:u,d:v("ev_x")}),"أضيفت الفعالية.")}
 else if(f.id==="themeForm"){const t=thVal();if(!THEME.valid(t))return toast("لون غير صالح.",true);run(async()=>{await API.settings.set({...A.data.settings,theme:t});THEME.apply(t,true)},"حُفظت الألوان وظهرت للزوار.")}
 else if(f.id==="setForm"){const adPrices={};Object.keys(PLACEMENTS).forEach(k=>{const x=v("sp_"+k);if(x)adPrices[k]=x});run(()=>API.settings.set({...A.data.settings,adPrices,bank:v("s_bank"),whatsapp:v("s_wa")}),"حُفظت الإعدادات.")}
});
document.addEventListener("click",async e=>{
 const x=e.target.closest("[data-exp]");if(x){const k=x.dataset.exp,D=A.data;
  if(k==="requests")csv([["التاريخ","النوع","المنتج","الاسم","المنشأة","الجوال","البريد","المدينة","التفاصيل","الملاحظات","الحالة","السعر","الرد"],...D.requests.map(r=>[new Date(r.at).toISOString().slice(0,10),TYPES[r.type]||r.type,r.product,r.name,r.company,r.phone,r.email,r.city,Object.entries(r.details||{}).map(([a,b])=>(DET[a]||a)+": "+b).join(" | "),r.notes,STAT[r.status]?.[0]||r.status,r.price,r.reply])],"الطلبات");
  if(k==="users")csv([["الاسم","البريد","الجوال","المدينة","المنشأة","الدور","التسجيل"],...D.users.map(u=>[u.name,u.email,u.phone,u.city,u.company,ROLES[u.role]||u.role,new Date(u.at).toISOString().slice(0,10)])],"المستخدمون");
  if(k==="jobs")csv([["الوظيفة","الجهة","المدينة","النوع","الراتب","التواصل","النشر","الانتهاء","مميزة"],...D.jobs.map(j=>[j.title,j.company,j.city,j.type,j.salary,j.contact,new Date(j.at).toISOString().slice(0,10),new Date(j.exp).toISOString().slice(0,10),j.featured?"نعم":""])],"الوظائف");
  if(k==="certs")csv([["الرقم","الاسم","المرحلة","الدرجة","التاريخ"],...D.certs.map(c=>[c.code,c.holder,TRACKS[c.track]||c.track,c.score,new Date(c.at).toISOString().slice(0,10)])],"الشهادات");
  if(k==="subs")csv([["البريد","التاريخ"],...D.subs.map(s=>[s.email,new Date(s.at).toISOString().slice(0,10)])],"المشتركون");
  return}
 const b=e.target.closest("[data-act]");if(!b)return;const d=b.dataset,id=d.id;
 switch(d.act){
  case "signout":await API.auth.signOut();A.me=null;A.loaded=false;render();break;
  case "reload":await reload();toast("تم التحديث.");break;
  case "rsave":{const st=document.querySelector(`[data-rstat="${id}"]`).value,pr=document.querySelector(`[data-rprice="${id}"]`).value.trim(),rp=document.querySelector(`[data-rreply="${id}"]`).value.trim();
   if(pr&&!isFinite(Number(pr)))return toast("السعر رقم فقط.",true);run(()=>API.requests.update(id,{status:st,price:pr,reply:rp}),"حُفظ، ووصل إشعار للعميل إن كان له حساب.");break}
  case "rpublish":{const r=A.data.requests.find(x=>x.id===id);if(!r)return;const dt=r.details||{};const weeks=Math.max(1,Number(dt.weeks)||1);
   run(async()=>{await API.ads.create({title:dt.atitle||r.company||r.name,text:dt.atext||"",link:/^https:\/\//i.test(dt.alink||"")?dt.alink:"",cta:dt.acta||"التفاصيل",placement:dt.place||"home",price:r.price,requestId:r.id,start:Date.now(),end:Date.now()+weeks*7*864e5});await API.requests.update(id,{published:true,status:"done",reply:r.reply||"نُشر إعلانك."})},"نُشر الإعلان وأُبلغ العميل.");break}
  case "adtoggle":run(()=>API.ads.setActive(id,d.v==="1"));break;
  case "addel":run(()=>API.ads.remove(id),"حُذف الإعلان.");break;
  case "jfeat":run(()=>API.jobs.update(id,{featured:d.v==="1"}));break;
  case "jhide":run(()=>API.jobs.update(id,{status:d.v}));break;
  case "jdel":run(()=>API.jobs.remove(id),"حُذفت الوظيفة.");break;
  case "oapprove":run(()=>API.offices.update(id,{status:"approved",verified:d.v==="1"}),"اعتُمد المكتب.");break;
  case "oreject":run(()=>API.offices.update(id,{status:"rejected"}),"رُفض الطلب.");break;
  case "otrust":run(()=>API.offices.update(id,{verified:d.v==="1"}));break;
  case "odel":run(()=>API.offices.remove(id),"حُذف المكتب.");break;
  case "thpreset":{const p=THEME.PRESETS.find(x=>x.id===d.id);if(!p)break;["a","g","n"].forEach((k,i)=>{const el=document.getElementById("th_"+k);if(el)el.value=[p.accent,p.gold,p.navy][i]});THEME.apply(thVal());break}
  case "threset":{const p=THEME.PRESETS[0];run(async()=>{const s={...A.data.settings};delete s.theme;await API.settings.set(s);THEME.apply(null,true)},"رجعت الألوان الافتراضية.");break}
  case "evdel":run(()=>API.events.remove(id),"حُذفت الفعالية.");break;
  case "subdel":run(()=>API.subscribers.remove(id),"حُذف المشترك.");break;
 }
});
document.addEventListener("change",e=>{const el=e.target;
 if(el.id==="f_status"){A.f.status=el.value;render()}else if(el.id==="f_type"){A.f.type=el.value;render()}else if(el.id==="f_role"){A.f.role=el.value;render()}
 else if(el.dataset.role){const id=el.dataset.role,role=el.value;if(role==="engineer"){render();toast("اعتماد المهندسين يتم من بوابة المهندسين ← الإدارة ← طلبات الانضمام، بعد أن يقدّم المهندس طلبه هناك.",true);return}run(()=>API.users.setRole(id,role),"تم تغيير الدور.")}
});
document.addEventListener("input",e=>{if(/^th_[agn]$/.test(e.target.id||""))THEME.apply(thVal())});
let qt=null;document.addEventListener("input",e=>{if(e.target.id==="f_q"){clearTimeout(qt);qt=setTimeout(()=>{A.f.q=e.target.value.trim();render()},250)}});

/* ---------- boot ---------- */
async function boot(){
 if(!API.ready){$("#app").innerHTML=vLogin("الخادم غير مهيأ.");return}
 const s=await API.auth.session();
 if(!s){A.me=null;render();return}
 const p=await API.profile.me().catch(()=>null);
 A.me=p?{id:p.id,email:s.email,role:p.role,name:p.name}:{id:s.uid,email:s.email,role:"student"};
 render();
 if(A.me.role==="admin"){await reload();A.tab=(location.hash||"#dash").slice(1)||"dash";render()}
}
API.auth.onChange(s=>{if(!s&&A.me){A.me=null;A.loaded=false;render()}});
boot();
})();
