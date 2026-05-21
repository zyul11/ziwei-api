#!/usr/bin/env node
/**
 * 紫微斗数 排盘核心库
 * 导出 paiPan 函数和所有常量，供 engine CLI 和 daily-fortune 复用
 */
const { Solar } = require('lunar-javascript');

// ─── 基础数据 ────────────────────────────────────────────────
const TIAN_GAN = ['甲','乙','丙','丁','戊','己','庚','辛','壬','癸'];
const TIAN_GAN_IDX = { '甲':0,'乙':1,'丙':2,'丁':3,'戊':4,'己':5,'庚':6,'辛':7,'壬':8,'癸':9 };
const DI_ZHI = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥'];
const DI_ZHI_IDX = { '子':0,'丑':1,'寅':2,'卯':3,'辰':4,'巳':5,'午':6,'未':7,'申':8,'酉':9,'戌':10,'亥':11 };

const PALACE_NAMES = [
  '命宫','兄弟宫','夫妻宫','子女宫','财帛宫','疾厄宫',
  '迁移宫','交友宫','官禄宫','田宅宫','福德宫','父母宫'
];

const STAR_NAMES = ['紫微','天机','太阳','武曲','天同','廉贞','天府','太阴','贪狼','巨门','天相','天梁','七杀','破军'];
const HUA_NAMES = ['化禄','化权','化科','化忌'];

// 五行局: 2=水,3=木,4=金,5=土,6=火 (甲子序0~59)
const NAYIN_MAP = [
  4,4, 6,6, 3,3, 5,5, 2,2,  6,6, 2,2, 5,5, 4,4, 3,3,
  2,2, 5,5, 6,6, 3,3, 4,4,  4,4, 6,6, 3,3, 5,5, 2,2,
  6,6, 2,2, 5,5, 4,4, 3,3,  2,2, 5,5, 6,6, 3,3, 4,4
];
const NAYIN_NAME = {2:'水二局',3:'木三局',4:'金四局',5:'土五局',6:'火六局'};

// 紫微星位置表
function buildZiWeiTable() {
  const t = {2:[],3:[],4:[],5:[],6:[]};
  for (let ju = 2; ju <= 6; ju++) {
    const step = ju + 1;
    for (let d = 1; d <= 30; d++) {
      t[ju].push(((2 - Math.floor((d - 1) / step)) % 12 + 12) % 12);
    }
  }
  return t;
}
const ZIWEI_POS = buildZiWeiTable();

// 14主星表
function genStarTable() {
  const t = {};
  for (let zw = 0; zw < 12; zw++) {
    const tf = (zw + 4) % 12;
    t[zw] = [
      zw,              (zw-1+12)%12, (zw-3+12)%12, (zw-4+12)%12, (zw-5+12)%12, (zw-7+12)%12,
      tf,              (tf-1+12)%12, (tf+1)%12,     (tf+2)%12,     (tf+3)%12,
      (tf+4)%12,       (tf+5)%12,    (tf+6)%12,
    ];
  }
  return t;
}
const STAR_TABLE = genStarTable();

// 四化 [年干索引0~9] → [化禄,化权,化科,化忌] (星索引)
const SI_HUA = [
  [5,13, 3, 2], [1,11, 0, 7], [4, 1,16, 5], [7, 4, 1, 9], [8, 7,18, 1],
  [3, 8,11,17], [2, 3, 7, 4], [9, 2,17,16], [11,0,15, 3], [13,9, 7, 8],
];

// 天魁天钺 [年干索引] → [天魁地支, 天钺地支]
const TIAN_KUI = [[2,7],[0,8],[11,9],[11,9],[2,7],[0,8],[2,7],[6,2],[5,3],[5,3]];
// 禄存 [年干索引] → 地支索引
const LU_CUN = [2,3,5,6,5,6,8,9,11,0];

// 辅星名称
const MINOR_NAMES = ['左辅','右弼','文昌','文曲','天魁','天钺','禄存','擎羊','陀罗'];

// 命主表
const MING_ZHU = ['贪狼','巨门','禄存','文曲','廉贞','武曲','破军','武曲','廉贞','文曲','禄存','巨门'];
// 身主表
const SHEN_ZHU = ['火星','天相','天梁','天同','文昌','天机','火星','天相','天梁','天同','文曲','天机'];

// 大限路线
const DAXIAN_SHUN = [0,11,10,9,8,7,6,5,4,3,2,1];
const DAXIAN_NI = [0,1,2,3,4,5,6,7,8,9,10,11];

// 地支关系 (简化版)
const BRANCH_LIUHE = [[0,1],[1,0],[2,11],[11,2],[3,10],[10,3],[4,9],[9,4],[5,8],[8,5],[6,7],[7,6]]; // 六合
const BRANCH_LIUCHONG = [[0,6],[6,0],[1,7],[7,1],[2,8],[8,2],[3,9],[9,3],[4,10],[10,4],[5,11],[11,5]]; // 六冲
const BRANCH_XING = [[2,5],[5,2],[5,8],[8,5],[8,2],[2,8]]; // 三刑简版: 寅巳申
const BRANCH_HAI = [[0,6],[6,0],[1,5],[5,1],[2,4],[4,2],[3,9],[9,3],[7,11],[11,7],[8,10],[10,8]]; // 六害

// 三合局
const SAN_HE_GROUPS = [[0,4,8], [1,5,9], [2,6,10], [3,7,11]]; // 申子辰, 酉丑巳, 寅午戌, 卯未亥

// ─── 工具函数 ────────────────────────────────────────────────
function getJiaziIdx(yearGan, yearZhi) {
  const g = TIAN_GAN_IDX[yearGan];
  const z = DI_ZHI_IDX[yearZhi];
  if (g === undefined || z === undefined) return 0;
  if (g % 2 === 0 && z % 2 === 0) return (g / 2) * 10 + (z / 2);
  if (g % 2 === 1 && z % 2 === 1) return Math.floor(g / 2) * 10 + Math.floor(z / 2) + 30;
  return 0;
}

function getBranchRelation(b1, b2) {
  // 返回关系类型: '六合','六冲','三刑','六害','三合','无'
  for (const [a,b] of BRANCH_LIUHE) { if (a===b1 && b===b2) return '六合'; }
  for (const [a,b] of BRANCH_LIUCHONG) { if (a===b1 && b===b2) return '六冲'; }
  for (const [a,b] of BRANCH_XING) { if (a===b1 && b===b2) return '三刑'; }
  for (const [a,b] of BRANCH_HAI) { if (a===b1 && b===b2) return '六害'; }
  for (const grp of SAN_HE_GROUPS) {
    if (grp.includes(b1) && grp.includes(b2) && b1 !== b2) return '三合';
  }
  return '无';
}

function getBranchRelationScore(relation) {
  const scores = { '六合': 1, '三合': 1, '无': 0, '三刑': 0, '六害': -1, '六冲': -2 };
  return scores[relation] || 0;
}

// ─── 排盘 ────────────────────────────────────────────────────
function paiPan(year, month, day, hour, gender) {
  const hourIdx = Math.floor((hour + 1) / 2) % 12;
  const solar = Solar.fromYmdHms(year, month, day, hour, 0, 0);
  const lunar = solar.getLunar();
  const ec = lunar.getEightChar();

  const lunarMonth = lunar.getMonth();
  const lunarDay = lunar.getDay();
  const lunarYear = lunar.getYear();

  const yearGan = ec.getYearGan();
  const yearZhi = ec.getYearZhi();
  const monthGan = ec.getMonthGan();
  const monthZhi = ec.getMonthZhi();
  const dayGan = ec.getDayGan();
  const dayZhi = ec.getDayZhi();
  const timeGan = ec.getTimeGan();
  const timeZhi = ec.getTimeZhi();

  const jiaziIdx = getJiaziIdx(yearGan, yearZhi);
  const wuXingJu = NAYIN_MAP[jiaziIdx] || 2;
  const wuXingJuName = NAYIN_NAME[wuXingJu];

  const mingGong = ((2 + (lunarMonth - 1) - hourIdx) % 12 + 12) % 12;
  const shenGong = ((2 + (lunarMonth - 1) + hourIdx) % 12 + 12) % 12;

  const ziWeiPos = ZIWEI_POS[wuXingJu][Math.min(Math.max(lunarDay - 1, 0), 29)];
  const stars = STAR_TABLE[ziWeiPos];

  const siHua = SI_HUA[TIAN_GAN_IDX[yearGan]];

  // 辅星
  const minor = {};
  minor['左辅'] = ((4 + (lunarMonth - 1)) % 12 + 12) % 12;
  minor['右弼'] = ((10 - (lunarMonth - 1)) % 12 + 12) % 12;
  minor['文昌'] = ((10 - hourIdx) % 12 + 12) % 12;
  minor['文曲'] = ((4 + hourIdx) % 12 + 12) % 12;
  const ky = TIAN_KUI[TIAN_GAN_IDX[yearGan]];
  minor['天魁'] = ky[0];
  minor['天钺'] = ky[1];
  const lc = LU_CUN[TIAN_GAN_IDX[yearGan]];
  minor['禄存'] = lc;
  minor['擎羊'] = (lc + 1) % 12;
  minor['陀罗'] = (lc - 1 + 12) % 12;

  // 12宫
  const palaces = {};
  for (let i = 0; i < 12; i++) {
    const diZhi = (mingGong - i + 12) % 12;
    const name = PALACE_NAMES[i];
    const starList = [];
    for (let s = 0; s < stars.length; s++) {
      if (stars[s] === diZhi) starList.push(STAR_NAMES[s]);
    }
    const minorList = [];
    for (const [mn, pos] of Object.entries(minor)) {
      if (pos === diZhi) minorList.push(mn);
    }
    const huaList = [];
    for (let h = 0; h < 4; h++) {
      const hStar = siHua[h];
      if (hStar < 14 && stars[hStar] === diZhi) huaList.push(HUA_NAMES[h]);
    }
    palaces[name] = { 地支: diZhi, 主星: starList, 辅星: minorList, 四化: huaList };
  }

  const isYang = TIAN_GAN_IDX[yearGan] % 2 === 0;
  const isMale = gender === 'male';
  const shunXing = (isYang && isMale) || (!isYang && !isMale);
  const daxianRoute = shunXing ? DAXIAN_SHUN : DAXIAN_NI;
  const startAge = wuXingJu;
  const daxian = [];
  for (let i = 0; i < 12; i++) {
    const ageStart = startAge + i * 10;
    const ageEnd = ageStart + 9;
    const palaceIdx = daxianRoute[i];
    const palaceName = PALACE_NAMES[palaceIdx];
    const dz = (mingGong - palaceIdx + 12) % 12;
    const pStars = [];
    for (let s = 0; s < stars.length; s++) {
      if (stars[s] === dz) pStars.push(STAR_NAMES[s]);
    }
    daxian.push({
      大限: `${palaceName}`,
      年龄: `${ageStart}~${ageEnd}岁`,
      主星: pStars,
    });
  }

  return {
    success: true,
    基本信息: {
      生辰: `${year}年${month}月${day}日 ${hour}时`,
      性别: gender === 'male' ? '男' : '女',
      农历: `${lunarYear}年${lunar.getMonthInChinese()}月${lunar.getDayInChinese()}日`,
      八字: `${yearGan}${yearZhi} ${monthGan}${monthZhi} ${dayGan}${dayZhi} ${timeGan}${timeZhi}`,
      生肖: lunar.getYearShengXiao(),
      星座: solar.getXingZuo(),
      五行局: wuXingJuName,
      命主: MING_ZHU[mingGong],
      身主: SHEN_ZHU[DI_ZHI_IDX[yearZhi]],
      起运: `${startAge}岁`,
      阴阳: isYang ? '阳' : '阴',
    },
    命盘: palaces,
    大限: daxian,
    身宫: PALACE_NAMES[shenGong],
    紫微星宫位: DI_ZHI[ziWeiPos],
    命宫地支: mingGong,
  };
}

// ─── 每日运势计算 ─────────────────────────────────────────────
function calcDailyFortune(chart, targetDateStr) {
  // targetDateStr: "2026-05-18"
  const [y, m, d] = targetDateStr.split('-').map(Number);
  const solar = Solar.fromYmd(y, m, d);
  const lunar = solar.getLunar();
  const ec = lunar.getEightChar();

  const dayGan = ec.getDayGan();        // 日干 e.g. "辛"
  const dayZhi = ec.getDayZhi();        // 日支 e.g. "卯"
  const ganIdx = TIAN_GAN_IDX[dayGan];
  const zhiIdx = DI_ZHI_IDX[dayZhi];

  // 日干四化
  const daySiHua = SI_HUA[ganIdx];

  const palaces = chart.命盘;

  // 找到日干四化引动了哪些星 → 在哪一宫
  const huaStarNames = [];
  for (let h = 0; h < 4; h++) {
    const starIdx = daySiHua[h];
    if (starIdx < 14) huaStarNames.push(STAR_NAMES[starIdx]);
  }

  // 对每宫评分
  const palaceScores = [];
  for (const [pName, pData] of Object.entries(palaces)) {
    let score = 0;
    const activations = [];

    // 日干四化碰撞
    for (let h = 0; h < 4; h++) {
      const starIdx = daySiHua[h];
      if (starIdx < 14) {
        const sName = STAR_NAMES[starIdx];
        if (pData.主星.includes(sName)) {
          const hName = HUA_NAMES[h];
          activations.push({ star: sName, hua: hName });
          if (hName === '化禄') score += 2;
          else if (hName === '化忌') score -= 2;
          else if (hName === '化权') score += 1;
          else if (hName === '化科') score += 1;
        }
      }
    }

    // 日支与宫支关系
    const relation = getBranchRelation(zhiIdx, pData.地支);
    const relScore = getBranchRelationScore(relation);
    score += relScore;
    if (relation !== '无') {
      activations.push({ type: relation, detail: `${dayZhi}与${DI_ZHI[pData.地支]}${relation}` });
    }

    palaceScores.push({
      宫位: pName,
      地支: DI_ZHI[pData.地支],
      主星: pData.主星,
      辅星: pData.辅星,
      activations: activations,
      score: score,
    });
  }

  // 排序
  palaceScores.sort((a, b) => b.score - a.score);

  // 总分
  const overallScore = palaceScores.reduce((s, p) => s + p.score, 0);

  // 好运宫位（score > 0）
  const luckyPalaces = palaceScores.filter(p => p.score > 0);
  // 警示宫位（score < 0）
  const cautionPalaces = palaceScores.filter(p => p.score < 0);

  return {
    date: targetDateStr,
    dayGanZhi: `${dayGan}${dayZhi}`,
    dayGan: dayGan,
    dayZhi: dayZhi,
    dayStemIndex: ganIdx,
    dayBranchIndex: zhiIdx,
    overallScore: overallScore,
    palaceScores: palaceScores,
    luckyPalaces: luckyPalaces.map(p => p.宫位),
    cautionPalaces: cautionPalaces.map(p => p.宫位),
  };
}

// ─── 文本生成 ────────────────────────────────────────────────
// 运势模版
const FORTUNE_TEMPLATES = {
  '命宫': {
    '化禄': '今天命宫受化禄引动，自信心提升，做事顺遂，容易得到他人认可。适合主动出击、展现自我。',
    '化权': '命宫化权，今天你掌控力增强，适合做决策、担责任。但注意不要太过强势。',
    '化科': '命宫化科，今天名声运不错，适合学习、考试、发表观点。人前得体，容易留下好印象。',
    '化忌': '命宫化忌，今天容易自我怀疑、心神不宁。建议放慢节奏，先处理确定性高的小事。',
    'default': '命宫没有特殊引动，今天整体平稳，按部就班即可。',
  },
  '财帛宫': {
    '化禄': '今天财帛宫见化禄，财运有意外之喜，或有款项回笼。适合处理财务事务、做投资决策。',
    '化权': '财帛宫化权，今天在钱财上你有主动权，谈价、催款、签合同都得力。但勿贪心冒进。',
    '化科': '财帛宫化科，今天适合做财务规划、记账理财。小有偏财，但不宜豪赌。',
    '化忌': '财帛宫化忌，今天易破财，注意冲动消费、投资陷阱。宜守不宜攻。',
    'default': '今天财运平稳，没有大起大落，适合日常消费和储蓄。',
  },
  '官禄宫': {
    '化禄': '官禄宫化禄，事业运上升，今天工作顺利，可能有好消息或上级肯定。',
    '化权': '官禄宫化权，今天你在工作上有话语权，适合推进项目、主持会议。但避免与同事硬碰。',
    '化科': '官禄宫化科，今天职场人缘好，适合汇报、展示、撰写方案。口碑加分。',
    '化忌': '官禄宫化忌，今天工作容易出纰漏、与同事沟通不畅。重要文件多检查一遍。',
    'default': '今天事业运平淡，适合按计划执行，不宜推新方案或做重大决策。',
  },
  '夫妻宫': {
    '化禄': '夫妻宫化禄，感情运升温，今天适合约会、沟通、制造小惊喜。单身者桃花运不错。',
    '化权': '夫妻宫化权，今天你在感情中更主动，适合推进关系、坦诚表达需求。注意语气别太硬。',
    '化科': '夫妻宫化科，今天感情和谐，适合一起参加社交活动。旁人眼中你们很般配。',
    '化忌': '夫妻宫化忌，今天容易因小事争吵，注意语气。给彼此一些空间。',
    'default': '感情方面今天没有特殊波动，平淡中见真情。',
  },
  '迁移宫': {
    '化禄': '迁移宫化禄，适合外出、出差、见客户。路上可能有意外收获或贵人。',
    '化权': '迁移宫化权，今天你在外的表现力强，适合谈判、演讲、社交。异地事务进展顺利。',
    '化科': '迁移宫化科，出门会给人留下好印象，适合拓展人脉、参加活动。',
    '化忌': '迁移宫化忌，今天不宜远行或重要外出，容易迷路、延误、沟通不畅。',
    'default': '今天外出运一般，没有特别需要注意的。',
  },
  '疾厄宫': {
    '化禄': '疾厄宫化禄，今天身体状态不错，精力充沛。适合运动、养生、体检。',
    '化权': '疾厄宫化权，今天抵抗力强，小病小痛扛得住。但别透支身体。',
    '化科': '疾厄宫化科，今天状态平稳，之前的身体小问题有缓解迹象。',
    '化忌': '疾厄宫化忌，今天容易疲劳、头痛、肠胃不适。注意休息，少吃生冷。',
    'default': '今天身体状况普通，保持正常作息即可。',
  },
  '迁移宫': {
    '化禄': '迁移宫化禄，外出运势好，适合出行、拜访客户。路上可能有意外惊喜。',
    '化权': '迁移宫化权，今天在外有掌控力，适合谈业务、处理异地事务。',
    '化科': '迁移宫化科，出门得体，容易给人留下好印象。适合社交场合。',
    '化忌': '迁移宫化忌，今天不宜远行，外出容易出小状况。重要事情尽量在本地处理。',
    'default': '今天外出运势平稳。',
  },
  '交友宫': {
    '化禄': '交友宫化禄，今天人缘好，朋友、同事会主动帮你。适合团队合作、聚餐。',
    '化权': '交友宫化权，你在群体中有影响力，适合组织活动、分配任务。',
    '化科': '交友宫化科，今天你说话得体，容易获得他人好感。适合社交。',
    '化忌': '交友宫化忌，今天容易与人发生口角，注意言辞。不宜参与复杂的人际纠纷。',
    'default': '今天人际关系方面没有特殊波动。',
  },
  '田宅宫': {
    '化禄': '田宅宫化禄，家庭运好，适合和家人相处、处理房产事务。居家环境让你感到舒适。',
    '化权': '田宅宫化权，今天你在家中有主导权，适合做家庭决策、布置家居。',
    '化科': '田宅宫化科，家庭关系和谐，适合在家学习、工作。',
    '化忌': '田宅宫化忌，家庭容易有小摩擦，注意水电安全。适合独处静心。',
    'default': '家庭方面今天没有特殊变化。',
  },
  '福德宫': {
    '化禄': '福德宫化禄，今天心情愉快，精神满足。适合做自己喜欢的事，享受生活。',
    '化权': '福德宫化权，今天精神头足，意志力强。适合冥想、规划长远目标。',
    '化科': '福德宫化科，今天思维清晰，灵感多。适合创作、学习。',
    '化忌': '福德宫化忌，今天容易胡思乱想、焦虑。建议转移注意力，不做重大决定。',
    'default': '今天精神状态平稳。',
  },
  '父母宫': {
    '化禄': '父母宫化禄，今天与长辈关系融洽，容易得到他们的支持或馈赠。适合回家看看。',
    '化权': '父母宫化权，今天长辈方面的事情需要你拿主意，你有能力处理好。',
    '化科': '父母宫化科，长辈对你评价不错，适合向他们请教或寻求建议。',
    '化忌': '父母宫化忌，今天容易因为长辈的事操心，注意沟通方式。',
    'default': '今天与长辈关系方面没有特殊变化。',
  },
  '兄弟宫': {
    '化禄': '兄弟宫化禄，今天与兄弟姐妹、朋友聚会愉快，可能得到他们的帮助。',
    '化权': '兄弟宫化权，你在朋辈中有号召力，适合组织活动。',
    '化科': '兄弟宫化科，和亲友相处融洽，适合一起学习、交流。',
    '化忌': '兄弟宫化忌，今天容易和兄弟姐妹或密友产生误会，注意沟通。',
    'default': '今天与兄弟朋友关系平稳。',
  },
  '子女宫': {
    '化禄': '子女宫化禄，今天和孩子相处愉快，可能有关于孩子的喜讯。也适合创意、艺术活动。',
    '化权': '子女宫化权，今天在子女教育方面你有决断力，适合做规划。',
    '化科': '子女宫化科，子女方面有好事发生，或你在创作上有灵感。',
    '化忌': '子女宫化忌，今天容易为子女的事操心，或创意工作遇到瓶颈。',
    'default': '今天子女/创作方面没有特殊变化。',
  },
};

// 宫位中文名 → 生活领域
const PALACE_DOMAIN = {
  '命宫': '自我状态',
  '兄弟宫': '人际关系',
  '夫妻宫': '感情婚姻',
  '子女宫': '子女/创意',
  '财帛宫': '财运投资',
  '疾厄宫': '身体健康',
  '迁移宫': '出行际遇',
  '交友宫': '社交人脉',
  '官禄宫': '事业发展',
  '田宅宫': '家庭房产',
  '福德宫': '精神心灵',
  '父母宫': '长辈贵人',
};

// 日月支关系中文描述
const BRANCH_RELATION_TEXT = {
  '六合': '今日地支与宫位地支六合，运势提升，诸事顺遂。',
  '三合': '今日地支与宫位地支三合，气场相融，进展顺利。',
  '无': '',
  '三刑': '今日地支与宫位地支相刑，易有口舌小事，需注意分寸。',
  '六害': '今日地支与宫位地支相害，易有小人是非，低调为宜。',
  '六冲': '今日地支与宫位地支相冲，波动较大，不宜做重大决定。',
};

function generateFortuneText(chart, dailyFortune) {
  // 总运概述
  const overall = dailyFortune.overallScore;
  let overallText;
  if (overall >= 5) overallText = '今天整体运势不错，能量积极向上，适合行动。';
  else if (overall >= 1) overallText = '今天运势温和偏吉，有好事发生但也有需要注意的地方。';
  else if (overall >= -3) overallText = '今天运势平平，宜静不宜动，按部就班即可。';
  else overallText = '今天波动较大，建议放慢节奏，以守为攻。';

  // 宫位详情
  const details = [];
  for (const p of dailyFortune.palaceScores) {
    if (p.activations.length === 0) continue;

    const domain = PALACE_DOMAIN[p.宫位] || p.宫位;
    const activationTexts = [];
    let huaText = '';

    for (const act of p.activations) {
      if (act.hua) {
        // 四化文本
        const templates = FORTUNE_TEMPLATES[p.宫位];
        if (templates) {
          huaText = templates[act.hua] || templates.default || '';
        }
        activationTexts.push(`${act.star}${act.hua}`);
      } else if (act.type) {
        // 地支关系文本
        const relText = BRANCH_RELATION_TEXT[act.type] || '';
        if (relText) activationTexts.push(act.type);
      }
    }

    if (huaText) {
      details.push({
        宫位: p.宫位,
        领域: domain,
        影响: activationTexts,
        评分: p.score,
        详解: huaText,
      });
    }
  }

  // 幸运色
  const luckyColors = ['#FF6B6B', '#4ECDC4', '#FFD93D', '#6BCB77', '#A8E6CF', '#FF8A5C', '#7C3AED', '#F472B6'];
  const luckyColor = luckyColors[Math.abs(dailyFortune.dayStemIndex) % luckyColors.length];

  // 幸运数字 (日干索引+1)
  const luckyNumbers = [dailyFortune.dayStemIndex + 1, (dailyFortune.dayStemIndex + 5) % 10 + 1, (dailyFortune.dayStemIndex + 9) % 10 + 1];

  // 宜忌
  const lucks = dailyFortune.luckyPalaces.map(p => PALACE_DOMAIN[p] || p);
  const cautions = dailyFortune.cautionPalaces.map(p => PALACE_DOMAIN[p] || p);

  return {
    overall: overallText,
    overallScore: overall,
    details: details,
    luckyAreas: lucks.length > 0 ? lucks : ['一切如常'],
    cautionAreas: cautions.length > 0 ? cautions : ['无特殊警示'],
    luckyColor: luckyColor,
    luckyNumbers: luckyNumbers,
    tip: overall >= 0 ? '今天适合主动出击' : '今天适合保守行事',
  };
}

module.exports = {
  paiPan,
  calcDailyFortune,
  generateFortuneText,
  TIAN_GAN, DI_ZHI, PALACE_NAMES, STAR_NAMES, HUA_NAMES,
  TIAN_GAN_IDX, DI_ZHI_IDX,
};
