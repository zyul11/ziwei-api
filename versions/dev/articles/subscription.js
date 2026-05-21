     1|// ── Article page subscription modal (shared across all article pages) ──
     2|// Multi-language support: detects language from <html lang>
     3|
     4|(function(){
     5|  // Detect article language
     6|  var htmlLang = document.documentElement.lang || 'zh-TW';
     7|  var SUB_LANG = 'zh-Hant';
     8|  if(htmlLang === 'en' || htmlLang === 'en-US') SUB_LANG = 'en';
     9|  else if(htmlLang === 'zh-CN' || htmlLang === 'zh-Hans') SUB_LANG = 'zh-Hans';
    10|
    11|  var SUB_TEXT = {
    12|    'zh-Hant': {
    13|      hint: '🌟 星伴计划 · 不只是运势，每天一封温暖的信。订阅越久解锁越多',
    14|      emailPH: '请输入电子邮箱',
    15|      namePH: '您的称呼（选填）',
    16|      birthLabel: '📅 出生信息（用于生成专属运势）',
    17|      btn: '✅ 确认订阅',
    18|      yearSuffix: '年', monthSuffix: '月', daySuffix: '日',
    19|      invalidEmail: '❌ 请输入有效邮箱',
    20|      noDate: '❌ 请选择出生日期',
    21|      orderFail: '❌ 创建订单失败，请稍后重试',
    22|      loading: '⏳',
    23|      hourLabels: ['子 (23:00-00:59)','丑 (01:00-02:59)','寅 (03:00-04:59)','卯 (05:00-06:59)','辰 (07:00-08:59)','巳 (09:00-10:59)','午 (11:00-12:59)','未 (13:00-14:59)','申 (15:00-16:59)','酉 (17:00-18:59)','戌 (19:00-20:59)','亥 (21:00-22:59)'],
    24|      genderLabels: ['♂ 男','♀ 女'],
    25|      months: ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'],
    26|      monthly: { benefit:'🌟 运势+热点+故事 · 每天都能解锁更多', name:'月度星伴', price:'$9.9', renew:'首月 $9.9，续订 $9.9/月' },
    27|      yearly: { benefit:'🌠 全年陪伴 · 第30天专属纪念信', name:'年度星伴', price:'$79.9', renew:'首年仅 $79.9，续订 $79.9/年' }
    28|    },
    29|    'zh-Hans': {
    30|      hint: '🌟 星伴计划 · 不只是运势，每天一封温暖的信。订阅越久解锁越多',
    31|      emailPH: '请输入电子邮箱',
    32|      namePH: '您的称呼（选填）',
    33|      birthLabel: '📅 出生信息（用于生成专属运势）',
    34|      btn: '✅ 确认订阅',
    35|      yearSuffix: '年', monthSuffix: '月', daySuffix: '日',
    36|      invalidEmail: '❌ 请输入有效邮箱',
    37|      noDate: '❌ 请选择出生日期',
    38|      orderFail: '❌ 创建订单失败，请稍后重试',
    39|      loading: '⏳',
    40|      hourLabels: ['子 (23:00-00:59)','丑 (01:00-02:59)','寅 (03:00-04:59)','卯 (05:00-06:59)','辰 (07:00-08:59)','巳 (09:00-10:59)','午 (11:00-12:59)','未 (13:00-14:59)','申 (15:00-16:59)','酉 (17:00-18:59)','戌 (19:00-20:59)','亥 (21:00-22:59)'],
    41|      genderLabels: ['♂ 男','♀ 女'],
    42|      months: ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'],
    43|      monthly: { benefit:'🌟 运势+热点+故事 · 每天都能解锁更多', name:'月度星伴', price:'$9.9', renew:'首月 $9.9，续订 $9.9/月' },
    44|      yearly: { benefit:'🌠 全年陪伴 · 第30天专属纪念信', name:'年度星伴', price:'$79.9', renew:'首年仅 $79.9，续订 $79.9/年' }
    45|    },
    46|    'en': {
    47|      hint: '🌟 Star Companion · More than fortune, a warm letter every morning. Unlock more the longer you subscribe',
    48|      emailPH: 'Enter your email',
    49|      namePH: 'Your name (optional)',
    50|      birthLabel: '📅 Birth info (for personalized fortune)',
    51|      btn: '✅ Confirm Subscribe',
    52|      yearSuffix: '', monthSuffix: '', daySuffix: '',
    53|      invalidEmail: '❌ Please enter a valid email',
    54|      noDate: '❌ Please select your birth date',
    55|      orderFail: '❌ Order creation failed, please try again',
    56|      loading: '⏳',
    57|      hourLabels: ['Zi (23:00-00:59)','Chou (01:00-02:59)','Yin (03:00-04:59)','Mao (05:00-06:59)','Chen (07:00-08:59)','Si (09:00-10:59)','Wu (11:00-12:59)','Wei (13:00-14:59)','Shen (15:00-16:59)','You (17:00-18:59)','Xu (19:00-20:59)','Hai (21:00-22:59)'],
    58|      genderLabels: ['♂ Male','♀ Female'],
    59|      months: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
    60|      monthly: { benefit:'🌟 Fortune+trending+stories · Unlock more every day', name:'Monthly Star', price:'$9.9', renew:'$9.9 first month, renew $9.9/mo' },
    61|      yearly: { benefit:'🌠 All-year companion · Day 30 personal letter', name:'Yearly Star', price:'$79.9', renew:'$79.9 first year, renew $79.9/yr' }
    62|    }
    63|  };
    64|  var t = SUB_TEXT[SUB_LANG] || SUB_TEXT['zh-Hant'];
    65|  var hourVals = [23,1,3,5,7,9,11,13,15,17,19,21];
    66|
    67|  if(!document.getElementById('subModal')){
    68|    var div = document.createElement('div');
    69|    div.innerHTML = '<div class="modal-overlay" id="subModal" style="display:none;position:fixed;inset:0;z-index:9998;background:rgba(10,6,4,.85);align-items:center;justify-content:center" onclick="if(event.target===this)closeSubModal()">' +
    70|      '<div style="background:linear-gradient(135deg,#2a1a12,#1a0e08);border:1px solid rgba(232,160,64,.2);border-radius:18px;padding:28px 24px;max-width:400px;width:90%;position:relative;text-align:center;max-height:90vh;overflow-y:auto">' +
    71|      '<button onclick="closeSubModal()" style="position:absolute;top:12px;right:14px;background:none;border:none;color:#6a4a2a;font-size:18px;cursor:pointer;padding:4px">\u2715</button>' +
    72|      '<div style="font-size:24px;margin-bottom:6px">\uD83C\uDF05</div>' +
    73|      '<div id="subModalBenefit" style="font-size:17px;font-weight:700;color:#f0e0c8;line-height:1.4;margin-bottom:4px"></div>' +
    74|      '<div id="subModalName" style="font-size:12px;color:#b09070;margin-bottom:6px"></div>' +
    75|      '<div style="height:1px;background:linear-gradient(90deg,transparent,rgba(232,160,64,.15),transparent);margin:0 0 10px"></div>' +
    76|      '<div id="subModalPrice" style="font-size:20px;font-weight:700;color:#e8b860;margin-bottom:2px"></div>' +
    77|      '<div id="subModalRenew" style="font-size:11px;color:#8a7050;margin-bottom:8px"></div>' +
    78|      '<div id="subModalHint" style="font-size:10px;color:#6a5a7a;margin-bottom:10px;line-height:1.4">'+t.hint+'</div>' +
    79|      '<input class="sub-input" id="subModalEmail" type="email" placeholder="'+t.emailPH+'" style="width:100%;background:#1e1612;border:1px solid #3a2a1e;border-radius:10px;padding:10px 12px;color:#e0d0b0;font-size:13px;outline:none;transition:border-color .25s;box-sizing:border-box;margin-bottom:6px" onfocus="this.style.borderColor=\'#e8b860\'" onblur="this.style.borderColor=\'#3a2a1e\'">' +
    80|      '<input class="sub-input" id="subModalUserName" type="text" placeholder="'+t.namePH+'" style="width:100%;background:#1e1612;border:1px solid #3a2a1e;border-radius:10px;padding:10px 12px;color:#e0d0b0;font-size:13px;outline:none;transition:border-color .25s;box-sizing:border-box;margin-bottom:8px" onfocus="this.style.borderColor=\'#e8b860\'" onblur="this.style.borderColor=\'#3a2a1e\'">' +
    81|      '<div style="font-size:11px;color:#8a7050;margin-bottom:6px;text-align:left">'+t.birthLabel+'</div>' +
    82|      '<div style="display:flex;gap:4px;margin-bottom:6px">' +
    83|      '<select id="subYear" style="flex:1;background:#1e1612;border:1px solid #3a2a1e;border-radius:8px;padding:6px 4px;color:#e0d0b0;font-size:12px;outline:none;cursor:pointer"></select>' +
    84|      '<select id="subMonth" style="flex:1;background:#1e1612;border:1px solid #3a2a1e;border-radius:8px;padding:6px 4px;color:#e0d0b0;font-size:12px;outline:none;cursor:pointer"></select>' +
    85|      '<select id="subDay" style="flex:1;background:#1e1612;border:1px solid #3a2a1e;border-radius:8px;padding:6px 4px;color:#e0d0b0;font-size:12px;outline:none;cursor:pointer"></select>' +
    86|      '</div>' +
    87|      '<div style="display:flex;gap:4px;margin-bottom:8px">' +
    88|      '<select id="subHour" style="flex:1;background:#1e1612;border:1px solid #3a2a1e;border-radius:8px;padding:6px 4px;color:#e0d0b0;font-size:12px;outline:none;cursor:pointer">' +
    89|      hourVals.map(function(v,i){ return '<option value="'+v+'"'+(i===4?' selected':'')+'>'+t.hourLabels[i]+'</option>'; }).join('') +
    90|      '</select>' +
    91|      '<select id="subGender" style="flex:1;background:#1e1612;border:1px solid #3a2a1e;border-radius:8px;padding:6px 4px;color:#e0d0b0;font-size:12px;outline:none;cursor:pointer">' +
    92|      '<option value="male">'+t.genderLabels[0]+'</option>' +
    93|      '<option value="female">'+t.genderLabels[1]+'</option>' +
    94|      '</select>' +
    95|      '</div>' +
    96|      '<button id="subModalBtn" onclick="subscribeSubmit()" style="width:100%;background:linear-gradient(135deg,#e8a040,#d08020);color:#0a0a14;font-weight:700;font-size:14px;border:none;border-radius:10px;padding:11px;cursor:pointer;font-family:inherit;letter-spacing:.5px;transition:opacity .2s" onmouseover="this.style.opacity=\'.85\'" onmouseout="this.style.opacity=\'1\'">'+t.btn+'</button>' +
    97|      '<div id="subModalStatus" style="margin-top:8px;font-size:12px;min-height:18px;color:#b09070"></div>' +
    98|      '</div></div>';
    99|    document.body.appendChild(div.firstElementChild);
   100|  }
   101|})();
   102|
   103|function initSubDates(){
   104|  var sy=document.getElementById('subYear'),sm=document.getElementById('subMonth'),sd=document.getElementById('subDay');
   105|  if(!sy)return;
   106|  var htmlLang = document.documentElement.lang || 'zh-TW';
   107|  var lang = 'zh-Hant';
   108|  if(htmlLang === 'en' || htmlLang === 'en-US') lang = 'en';
   109|  else if(htmlLang === 'zh-CN' || htmlLang === 'zh-Hans') lang = 'zh-Hans';
   110|  var t = (window.__SUB_TEXT || {})[lang];
   111|  if(!t){
   112|    t = { yearSuffix:'年', monthSuffix:'月', daySuffix:'日', months:['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'] };
   113|    if(lang === 'en') t = { yearSuffix:'', monthSuffix:'', daySuffix:'', months:['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'] };
   114|  }
   115|  var now=new Date(), y=now.getFullYear();
   116|  sy.innerHTML='';
   117|  for(var i=y-90;i<=y-10;i++) sy.innerHTML+='<option value="'+i+'">'+i+t.yearSuffix+'</option>';
   118|  sm.innerHTML='';
   119|  for(var i=1;i<=12;i++) sm.innerHTML+='<option value="'+i+'">'+t.months[i-1]+'</option>';
   120|  sd.innerHTML='';
   121|  for(var i=1;i<=31;i++) sd.innerHTML+='<option value="'+i+'">'+i+t.daySuffix+'</option>';
   122|}
   123|
   124|var _subPlan='monthly';
   125|function openSubModal(plan){
   126|  _subPlan=plan;
   127|  var htmlLang = document.documentElement.lang || 'zh-TW';
   128|  var lang = 'zh-Hant';
   129|  if(htmlLang === 'en' || htmlLang === 'en-US') lang = 'en';
   130|  else if(htmlLang === 'zh-CN' || htmlLang === 'zh-Hans') lang = 'zh-Hans';
   131|  var t = (window.__SUB_TEXT || {})[lang];
   132|  if(!t){
   133|    t = {
      monthly:{ benefit:'🌟 运势+热点+故事 · 每天都能解锁更多', name:'月度星伴', price:'$9.9', renew:'首月 $9.9，续订 $9.9/月' },
      yearly:{ benefit:'🌠 全年陪伴 · 第30天专属纪念信', name:'年度星伴', price:'$79.9', renew:'首年仅 $79.9，续订 $79.9/年' }
    };
    if(lang === 'en'){
      t = {
        monthly:{ benefit:'🌟 Fortune+trending+stories · Unlock more every day', name:'Monthly Star', price:'$9.9', renew:'$9.9 first month, renew $9.9/mo' },
        yearly:{ benefit:'🌠 All-year companion · Day 30 personal letter', name:'Yearly Star', price:'$79.9', renew:'$79.9 first year, renew $79.9/yr' }
   134|      };
   135|    }
   136|  }
   137|  var data = plan==='yearly' ? t.yearly : t.monthly;
   138|  document.getElementById('subModalBenefit').textContent = data.benefit;
   139|  document.getElementById('subModalName').textContent = data.name;
   140|  document.getElementById('subModalPrice').textContent = data.price;
   141|  document.getElementById('subModalRenew').textContent = data.renew;
   142|  initSubDates();
   143|  document.getElementById('subModal').style.display='flex';
   144|  document.getElementById('subModalStatus').textContent='';
   145|}
   146|
   147|function closeSubModal(){document.getElementById('subModal').style.display='none'}
   148|
   149|async function subscribeSubmit(){
   150|  var inp=document.getElementById('subModalEmail'),s=document.getElementById('subModalStatus');
   151|  var email=inp?.value.trim();
   152|  var htmlLang = document.documentElement.lang || 'zh-TW';
   153|  var lang = 'zh-Hant';
   154|  if(htmlLang === 'en' || htmlLang === 'en-US') lang = 'en';
   155|  else if(htmlLang === 'zh-CN' || htmlLang === 'zh-Hans') lang = 'zh-Hans';
   156|  var t = (window.__SUB_TEXT || {})[lang];
   157|  if(!t) t = { invalidEmail:'❌ 请输入有效邮箱', noDate:'❌ 请选择出生日期', orderFail:'❌ 创建订单失败，请稍后重试', loading:'⏳' };
   158|  if(lang === 'en' && !t.invalidEmail) t = { invalidEmail:'❌ Please enter a valid email', noDate:'❌ Please select your birth date', orderFail:'❌ Order creation failed, please try again', loading:'⏳' };
   159|  if(!email||!email.includes('@')){s.textContent=t.invalidEmail;return}
   160|  var by=document.getElementById('subYear')?.value,bm=document.getElementById('subMonth')?.value,bd=document.getElementById('subDay')?.value;
   161|  if(!by||!bm||!bd){s.textContent=t.noDate;return}
   162|  s.textContent=t.loading;
   163|  try{
   164|    var API=window.location.origin==='file://'?'http://127.0.0.1:8119':window.location.origin;
   165|    var r=await fetch(API+'/v1/subscribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
   166|      email,plan:_subPlan,birth_year:parseInt(by),birth_month:parseInt(bm),birth_day:parseInt(bd),
   167|      birth_hour:parseFloat(document.getElementById('subHour')?.value||'12'),gender:document.getElementById('subGender')?.value||'male',
   168|      language:lang
   169|    })});
   170|    var d=await r.json();
   171|    if(d.success&&d.data?.url){window.location.href=d.data.url}
   172|    else{s.textContent=t.orderFail}
   173|  }catch(e){s.textContent=t.orderFail}
   174|}
   175|