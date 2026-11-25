/* =====================================================================
   محرر المحتوى في بوابة الإدارة: نصوص وصور وفيديوهات لكل درس وكل إصدار
   يُحفظ عبر API.content ويظهر في الموقع فوراً
   ===================================================================== */
(function(){
const esc=CB.esc;
const PL=window.CONTENT_PLACES||{products:[],courses:[]};
const BODIES=window.LESSON_BODIES||{};
const E={all:null,loading:false,key:null,d:null,dirty:false,msg:"",bad:false,prev:false,q:"",leave:null,del:false,busy:0};
const T={text:"نص",image:"صورة",video:"فيديو"};

function placeOf(k){
 if(k.startsWith("product:")){const p=PL.products.find(x=>"product:"+x.id===k);return p&&{title:p.name,group:"صفحة الإصدار",href:"index.html#p-"+p.id,lesson:false}}
 for(const c of PL.courses){const i=c.lessons.findIndex((t,i)=>"lesson:"+c.id+"-"+i===k);if(i>=0)return {title:c.lessons[i],group:c.title+" · الدرس "+(i+1),href:"index.html#lesson-"+c.id+"-"+i,lesson:true}}
 return null}
const cnt=k=>{const c=E.all&&E.all[k];return c&&c.blocks.length?`<span class="chip">${c.blocks.length}</span>`:""};
const item=(k,t)=>`<button class="ce-item ${E.key===k?"on":""}" data-ce="pick" data-k="${k}"><span>${esc(t)}</span>${cnt(k)}</button>`;
const match=t=>!E.q||t.includes(E.q);

function list(){
 const prods=PL.products.filter(p=>match(p.name));
 return `<div class="panel ce-list"><h3 style="margin-top:0">اختر المكان</h3><input id="ce_q" placeholder="بحث باسم الدرس أو الإصدار" value="${esc(E.q)}" style="width:100%;margin-bottom:8px">
 ${prods.length?`<details open><summary>صفحات الإصدارات</summary>${prods.map(p=>item("product:"+p.id,p.name)).join("")}</details>`:""}
 ${PL.courses.map(c=>{const ls=c.lessons.map((t,i)=>[t,i]).filter(([t])=>match(t)||match(c.title));if(!ls.length)return "";
   const has=ls.some(([t,i])=>E.all&&E.all["lesson:"+c.id+"-"+i]);
   return `<details ${E.q||has&&c.id==="core"||(E.key||"").startsWith("lesson:"+c.id+"-")?"open":""}><summary>${esc(c.title)}</summary>${ls.map(([t,i])=>item("lesson:"+c.id+"-"+i,(i+1)+". "+t)).join("")}</details>`}).join("")}</div>`}

function blk(b,i,n){
 const hd=`<div class="hd"><b>${T[b.type]||b.type} ${i+1}</b><span class="row-acts"><button class="btn sm ghost" data-ce="up" data-i="${i}" ${i?"":"disabled"} title="للأعلى">↑</button><button class="btn sm ghost" data-ce="down" data-i="${i}" ${i<n-1?"":"disabled"} title="للأسفل">↓</button><button class="btn sm ghost" data-ce="rm" data-i="${i}">حذف</button></span></div>`;
 if(b.type==="text")return `<div class="ce-blk">${hd}<textarea data-cf="v" data-i="${i}" placeholder="اكتب الشرح هنا">${esc(b.v||"")}</textarea></div>`;
 const acc=b.type==="image"?"image/png,image/jpeg,image/webp,image/gif":"video/mp4,video/webm";

 return `<div class="ce-blk">${hd}<div class="form5"><label class="full">${b.type==="image"?"رابط الصورة (https://) أو ارفع صورة":"رابط يوتيوب (فيديو أو قائمة تشغيل) أو ارفع ملف فيديو قصير"}<input type="url" dir="ltr" data-cf="url" data-i="${i}" value="${esc(b.url||"")}" placeholder="https://"></label>
 <label>رفع ملف<input type="file" accept="${acc}" data-cu="${i}"></label><label>وصف قصير يظهر تحت ${T[b.type]}<input type="text" data-cf="cap" data-i="${i}" value="${esc(b.cap||"")}" maxlength="200"></label></div><div id="cePv${i}">${pvOf(b)}</div></div>`}
function pvOf(b){const u=b.url||"";if(!/^https:\/\//i.test(u))return "";const y=b.type==="video"&&CB.yt(u);
 return b.type==="image"?`<img class="prev" src="${esc(u)}" alt="">`:y&&y.v?`<img class="prev" src="${esc(CB.ytThumb(y))}" alt="">`:y?`<p class="fine">قائمة تشغيل يوتيوب ✓</p>`:/\.(mp4|webm)(\?|$)/i.test(u)?`<p class="fine">ملف فيديو ✓</p>`:`<p class="msg bad">رابط غير مفهوم</p>`}

function editor(){
 if(!E.key)return `<div class="panel"><h3>محرر المحتوى</h3><p>اختر درساً أو صفحة إصدار من القائمة، ثم أضف نصوصاً وصوراً وفيديوهات. ما تحفظه يظهر للطلاب والعملاء فوراً.</p>
  <ul class="steps5"><li><b>الدروس:</b> اختر «إضافة بعد الشرح الأصلي» لتكمل الشرح، أو «استبدال الشرح الأصلي» لتعيد كتابته. زر «نسخ الشرح الأصلي» يضع الشرح الحالي في مربع نص لتعدّل عليه.</li><li><b>صفحات الإصدارات:</b> يظهر ما تضيفه في تبويب «الفيديوهات والشرح» داخل صفحة الإصدار.</li><li><b>الفيديو:</b> الأفضل رابط يوتيوب (فيديو أو قائمة تشغيل كاملة). رفع ملف فيديو مباشر محدود بـ 50 ميغابايت.</li><li>كل الفيديوهات تظهر أيضاً في <a href="index.html#videos" target="_blank">مكتبة الفيديوهات</a> مقسمة حسب مكانها.</li></ul></div>`;
 const pl=placeOf(E.key)||{title:E.key,group:"",href:"index.html",lesson:false},d=E.d;
 return `<div class="panel"><div class="sechead" style="margin:0 0 8px"><div><div class="eyebrow">${esc(pl.group)}</div><h3 style="margin:2px 0">${esc(pl.title)}</h3></div><a class="btn sm ghost" href="${pl.href}" target="_blank">افتح في الموقع</a></div>
 ${pl.lesson?`<div class="form5"><label>طريقة العرض<select id="ce_mode"><option value="append" ${d.mode!=="replace"?"selected":""}>إضافة بعد الشرح الأصلي</option><option value="replace" ${d.mode==="replace"?"selected":""}>استبدال الشرح الأصلي</option></select></label><div style="align-self:end"><button class="btn sm ghost" data-ce="orig" ${BODIES[E.key]?"":"disabled"}>نسخ الشرح الأصلي للتعديل</button></div></div>`:`<p class="fine">يظهر في تبويب «الفيديوهات والشرح» في صفحة الإصدار.</p>`}
 ${d.blocks.map((b,i)=>blk(b,i,d.blocks.length)).join("")||`<p class="fine" style="margin:14px 0">لا يوجد محتوى بعد. أضف أول عنصر:</p>`}
 <div class="row-acts" style="margin:10px 0"><button class="btn sm ghost" data-ce="add" data-t="text">+ نص</button><button class="btn sm ghost" data-ce="add" data-t="image">+ صورة</button><button class="btn sm ghost" data-ce="add" data-t="video">+ فيديو</button></div>
 <p class="ce-help">تنسيق النص: سطر يبدأ بـ <b dir="ltr">##</b> عنوان · <b dir="ltr">-</b> نقطة · <b dir="ltr">1.</b> خطوة مرقمة · <b dir="ltr">**كلمة**</b> غامق · <b dir="ltr">&gt;</b> ملاحظة مميزة · <b dir="ltr">[نص](https://رابط)</b> رابط. سطر فارغ يبدأ فقرة جديدة.</p>
 <div class="row-acts" style="margin-top:12px"><button class="btn" data-ce="save" ${E.busy?"disabled":""}>حفظ ونشر</button><button class="btn ghost" data-ce="prev">${E.prev?"إخفاء المعاينة":"معاينة"}</button>${E.all&&E.all[E.key]?`<button class="btn ghost" data-ce="del">${E.del?"تأكيد حذف كل محتوى هذا المكان":"حذف المحتوى"}</button>`:""}${E.dirty?`<span class="chip warn">تعديلات غير محفوظة</span>`:""}</div>
 <div id="ceMsg">${E.msg?`<p class="msg ${E.bad?"bad":"ok"}">${esc(E.msg)}</p>`:""}</div>
 ${E.prev?`<div class="ce-prev lesson">${pl.lesson&&d.mode!=="replace"?`<p class="fine">[الشرح الأصلي للدرس يظهر هنا]</p><h3>شرح إضافي وفيديوهات</h3>`:""}${CB.render(d.blocks)}</div>`:""}</div>`}

function inner(){
 if(!E.all){if(!E.loading)load();return `<p class="fine">جارٍ تحميل المحتوى…</p>`}
 return list()+`<div>${editor()}</div>`}
function view(){return `<div class="ce" id="ceRoot">${inner()}</div>`}
function paint(){const r=document.getElementById("ceRoot");if(!r)return;const l=r.querySelector(".ce-list"),st=l?l.scrollTop:0;r.innerHTML=inner();const l2=r.querySelector(".ce-list");if(l2)l2.scrollTop=st}
async function load(){E.loading=true;try{E.all=await API.content.all()}catch(e){E.all={};E.msg=e.message;E.bad=true}E.loading=false;paint()}
const say=(m,bad)=>{E.msg=m;E.bad=!!bad};

function pick(k){
 if(E.dirty&&E.leave!==k){E.leave=k;say("لديك تعديلات غير محفوظة. اضغط على المكان مرة أخرى لتجاهلها، أو احفظ أولاً.",true);paint();return}
 const c=E.all[k];const pl=placeOf(k);
 E.key=k;E.d={title:pl?pl.title:"",mode:c?c.mode:"append",blocks:c?JSON.parse(JSON.stringify(c.blocks)):[]};
 E.dirty=false;E.leave=null;E.del=false;E.prev=false;say("");paint();
 const ed=document.querySelector("#ceRoot .ce-list + div");if(ed&&window.innerWidth<860)ed.scrollIntoView({behavior:"smooth"})}

function clean(blocks){return blocks.map(b=>b.type==="text"?{type:"text",v:String(b.v||"").trim()}:{type:b.type,url:String(b.url||"").trim(),cap:String(b.cap||"").trim()}).filter(b=>b.type==="text"?b.v:b.url)}

async function save(){
 const blocks=clean(E.d.blocks);
 const badUrl=blocks.find(b=>b.url&&!/^https:\/\//i.test(b.url));if(badUrl)return say("كل رابط يجب أن يبدأ بـ https://",true),paint();
 const badVid=blocks.find(b=>b.type==="video"&&!CB.yt(b.url)&&!/\.(mp4|webm)(\?|$)/i.test(b.url));if(badVid)return say("رابط الفيديو غير مفهوم. استخدم رابط يوتيوب أو ملف MP4/WebM.",true),paint();
 E.busy=1;paint();
 try{
  if(!blocks.length&&E.all[E.key]){await API.content.remove(E.key);delete E.all[E.key]}
  else if(blocks.length){await API.content.save(E.key,{title:E.d.title,mode:E.d.mode,blocks});E.all[E.key]={title:E.d.title,mode:E.d.mode,blocks,at:Date.now()}}
  E.d.blocks=JSON.parse(JSON.stringify(blocks));E.dirty=false;say("حُفظ ونُشر في الموقع.")
 }catch(e){say(e.message,true)}
 E.busy=0;paint()}

async function upload(i,file){
 if(!file)return;const b=E.d.blocks[i];if(!b)return;
 say("جارٍ رفع الملف… لا تغلق الصفحة.");E.busy++;paint();
 try{b.url=await API.content.upload(file);if(!b.cap)b.cap=file.name.replace(/\.[^.]+$/,"");E.dirty=true;say("تم الرفع. اضغط «حفظ ونشر» ليظهر في الموقع.")}catch(e){say(e.message,true)}
 E.busy--;paint()}

document.addEventListener("click",e=>{
 const b=e.target.closest("#ceRoot [data-ce]");if(!b)return;e.preventDefault();
 const a=b.dataset.ce,i=+b.dataset.i,d=E.d;
 if(a!=="del")E.del=false;
 switch(a){
  case "pick":return pick(b.dataset.k);
  case "add":d.blocks.push(b.dataset.t==="text"?{type:"text",v:""}:{type:b.dataset.t,url:"",cap:""});E.dirty=true;say("");break;
  case "rm":d.blocks.splice(i,1);E.dirty=true;break;
  case "up":if(i>0){[d.blocks[i-1],d.blocks[i]]=[d.blocks[i],d.blocks[i-1]];E.dirty=true}break;
  case "down":if(i<d.blocks.length-1){[d.blocks[i+1],d.blocks[i]]=[d.blocks[i],d.blocks[i+1]];E.dirty=true}break;
  case "orig":d.blocks.unshift({type:"text",v:CB.htmlToText(BODIES[E.key])});d.mode="replace";E.dirty=true;say("نُسخ الشرح الأصلي في أول مربع، وتحولت طريقة العرض إلى «استبدال». عدّل ثم احفظ.");break;
  case "prev":E.prev=!E.prev;break;
  case "save":return save();
  case "del":if(!E.del){E.del=true;break}E.del=false;d.blocks=[];return save();
 }
 paint()});
document.addEventListener("input",e=>{
 const t=e.target;if(!t.closest||!t.closest("#ceRoot"))return;
 if(t.id==="ce_q"){E.q=t.value.trim();clearTimeout(E.qt);E.qt=setTimeout(()=>{paint();const q=document.getElementById("ce_q");if(q){q.focus();q.setSelectionRange(q.value.length,q.value.length)}},250);return}
 if(t.dataset.cf){const i=+t.dataset.i,b=E.d.blocks[i];if(b){b[t.dataset.cf]=t.value;E.dirty=true;
  if(t.dataset.cf==="url"){clearTimeout(E.pt);E.pt=setTimeout(()=>{const el=document.getElementById("cePv"+i);if(el&&E.d.blocks[i]===b)el.innerHTML=pvOf(b)},350)}}}
});
document.addEventListener("change",e=>{
 const t=e.target;if(!t.closest||!t.closest("#ceRoot"))return;
 if(t.id==="ce_mode"){E.d.mode=t.value;E.dirty=true;paint()}
 else if(t.dataset.cu!==undefined)upload(+t.dataset.cu,t.files&&t.files[0]);

});
window.addEventListener("beforeunload",e=>{if(E.dirty){e.preventDefault();e.returnValue=""}});
window.ContentAdmin={view};
})();
