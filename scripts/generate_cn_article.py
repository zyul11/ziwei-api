#!/usr/bin/env python3
"""
紫微斗数中文SEO软文自动生成脚本（v2 - 支持真实命盘数据）
V2新特性：
- 随机生成日期+性别，调用本地API排盘
- 命盘数据嵌入文章，每篇独一无二
- 同时输出繁体+简体版本
- 自动更新 sitemap
"""

import os
import sys
import json
import random
import re
import unicodedata
import subprocess
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# ── 加载 .env ──
env_path = BASE_DIR / ".env"
if env_path.exists():
    for line in env_path.read_text().strip().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-chat"
WEBSITE = "https://ziweiapi.site"

# ── 城市列表 ──
CITIES = ["新加坡", "台北", "香港", "吉隆坡", "東京", "洛杉磯", "紐約", "雪梨", "曼谷", "上海", "首爾", "倫敦", "溫哥華", "墨爾本", "深圳"]

# ── 文章选题池（不重复前面脚本的50个主题） ──
ARTICLE_TOPICS = [
    # 真实命盘分析类
    "真實命盤解析：某命主的事業發展方向",
    "命盤中的四化飛星如何影響你的一生",
    "從命盤看你適合什麼行業",
    "命宮主星決定你的性格密碼",
    "這張命盤告訴我什麼時候該換工作",
    "命盤中桃花星多的人感情運如何",
    "財帛宮有化祿的人怎麼理財",
    "夫妻宮組合看你的婚姻模式",
    "遷移宮強的人在海外發展更好",
    "疾厄宮看你的健康隱患與保養方向",

    # 城市命理类
    "在台北打拼的你適合什麼命格",
    "新加坡工作運勢與命盤特徵",
    "香港金融業命盤有什麼共同點",
    "移居海外的命盤遷移宮特徵",
    "東京華人命盤有什麼特別之處",
    "上海創業者的命盤特質分析",
    "洛杉磯華人事業運命盤解析",
    "雪梨留學生的命盤遷移宮解析",

    # 热门话题类
    "2026下半年紫微斗數運勢提醒",
    "流年化忌來了怎麼辦？",
    "你的十年大限走到哪了？",
    "紫微斗數看近期貴人運",
    "怎麼從命盤看出你的財運高峰",
    "紫微斗數看你的職場貴人在哪",
    "命盤自化祿自化忌的深層含義",
    "命宮空宮的人如何解讀命盤",
    "今年適合轉職嗎？命盤告訴你",
    "十二宮哪一宮對你最重要",
]

# ── 工具函数 ──
PINYIN_MAP = {
    '七':'qi','殺':'sha','坐':'zuo','命':'ming','事':'shi','業':'ye','運':'yun',
    '破':'po','軍':'jun','創':'chuang','廉':'lian','貞':'zhen','感':'gan','情':'qing',
    '貪':'tan','狼':'lang','桃':'tao','花':'hua','紫':'zi','微':'wei','鬥':'dou','數':'shu',
    '帝':'di','王':'wang','格':'ge','局':'ju','機':'ji','智':'zhi','慧':'hui',
    '太':'tai','陽':'yang','光':'guang','明':'ming','武':'wu','曲':'qu','財':'cai',
    '天':'tian','同':'tong','府':'fu','相':'xiang','陰':'yin','福':'fu','氣':'qi',
    '庫':'ku','看':'kan','婚':'hun','姻':'yin','健':'jian','康':'kang','學':'xue',
    '子':'zi','女':'nv','父':'fu','母':'mu','兄':'xiong','弟':'di','緣':'yuan',
    '貴':'gui','人':'ren','日':'ri','月':'yue','輝':'hui','映':'ying',
    '風':'feng','流':'liu','口':'kou','剛':'gang','柔':'rou','並':'bing','濟':'ji',
    '空':'kong','宮':'gong','怎':'zen','麼':'me','辦':'ban','解':'jie','析':'xi',
    '走':'zou','向':'xiang','前':'qian','世':'shi','生':'sheng',
    '遷':'qian','移':'yi','外':'wai','出':'chu','疾':'ji','厄':'e','隱':'yin','患':'huan',
    '手':'shou','足':'zu','房':'fang','產':'chan','聯':'lian','繫':'xi',
    '化':'hua','祿':'lu','權':'quan','科':'ke','忌':'ji',
    '錢':'qian','成':'cheng','就':'jiu','與':'yu','西':'xi','方':'fang','星':'xing','座':'zuo',
    '所':'suo','有':'you','版':'ban','權':'quan','保':'bao','留':'liu',
    '真':'zhen','實':'shi','盤':'pan','析':'xi','適':'shi','合':'he',
    '什':'shen','麼':'me','行':'hang','業':'ye','密':'mi','碼':'ma',
    '換':'huan','工':'gong','作':'zuo','桃':'tao','管':'guan','理':'li',
    '海':'hai','外':'wai','健':'jian','康':'kang','隱':'yin','患':'huan',
    '打':'da','拼':'pin','移':'yi','居':'ju','共':'gong','同':'tong',
    '特':'te','別':'bie','創':'chuang','留':'liu','學':'xue',
    '2026':'2026','下':'xia','半':'ban','年':'nian','提':'ti','醒':'xing',
    '流':'liu','限':'xian','到':'dao','了':'le','近':'jin','期':'qi',
    '高':'gao','峰':'feng','職':'zhi','場':'chang','深':'shen','層':'ceng',
    '今':'jin','轉':'zhuan','第':'di','一':'yi','重':'zhong',
    '你':'ni','的':'de','生':'sheng','年':'nian','大':'da','提':'ti','升':'sheng',
    '經':'jing','驗':'yan','歷':'li','史':'shi','淵':'yuan','安':'an','門':'men',
    '教':'jiao','懂':'dong','二':'er','詳':'xiang','主':'zhu','身':'shen',
    '術':'shu','語':'yu','全':'quan','使':'shi','石':'shi','中':'zhong',
    '文':'wen','2025':'2025','與':'yu','MBTI':'mbti','祕':'mi',
    '巡':'xun','逢':'feng','將':'jiang','得':'de','地':'di','武':'zhi','榮':'rong','顯':'xian',
    '朝':'chao','垣':'yuan','雄':'xiong','宿':'su','乾':'qian','元':'yuan',
    '朗':'lang','並':'bing','名':'ming','望':'wang','雙':'shuang','收':'shou',
    '提':'ti','醒':'xing','飛':'fei','祕':'mi','訣':'jue',
    '自':'zi','含':'han','義':'yi','一':'yi','生':'shun','遂':'sui',
    '美':'mei','滿':'man','十':'shi','百':'bai','影':'ying','響':'xiang',
}

STAR_NAMES = {"紫微","天機","太陽","武曲","天同","廉貞","天府","太陰","貪狼","巨門","天相","天梁","七殺","破軍"}
AUX_STAR_NAMES = {"左輔","右弼","文昌","文曲","天魁","天鉞","祿存","擎羊","陀羅","火星","鈴星","地空","地劫","天馬"}


def simple_pinyin(text: str) -> str:
    """将繁体中文转换为简单拼音（用于文件名）"""
    result = []
    for ch in text:
        if ch in PINYIN_MAP:
            result.append(PINYIN_MAP[ch])
        elif '\u4e00' <= ch <= '\u9fff':
            result.append(f'u{ord(ch):04x}')
        elif ch.isalnum():
            result.append(ch.lower())
    return '-'.join(filter(None, result)).replace('--', '-').strip('-')


def run_engine(year: int, month: int, day: int, hour: float, gender: str) -> dict:
    """调用 Node.js 排盘引擎"""
    engine_path = BASE_DIR / "api" / "ziwei-engine.js"
    inp = json.dumps({"year": year, "month": month, "day": day, "hour": hour, "gender": gender})
    r = subprocess.run(
        ["node", str(engine_path)],
        input=inp, capture_output=True, text=True, timeout=10,
        cwd=str(BASE_DIR)
    )
    if r.returncode != 0:
        raise RuntimeError(f"Engine error: {r.stderr}")
    return json.loads(r.stdout)


def format_chart_summary(chart: dict) -> str:
    """从命盘数据中提取关键信息，生成文章可用的摘要"""
    lines = []
    try:
        stars = chart.get("stars", {})
        palaces = chart.get("palaces", [])

        # 命宫主星
        ming_palace = next((p for p in palaces if p.get("宫名") == "命宮" or p.get("name") == "ming"), None)
        if ming_palace:
            ms = ming_palace.get("主星", ming_palace.get("main_stars", []))
            if ms:
                lines.append(f"命宮主星：{''.join(ms)}")
            else:
                lines.append("命宮：空宮（借對宮星曜）")

        # 四化
        hua = chart.get("四化", chart.get("huas", []))
        if hua:
            hua_str = "、".join([f"{h.get('星曜', h.get('star',''))}{h.get('化', h.get('type',''))}" for h in hua[:4]])
            if hua_str:
                lines.append(f"四化：{hua_str}")

        # 身宮
        shen = chart.get("身宮", chart.get("shen_palace", ""))
        if shen:
            lines.append(f"身宮：{shen}")

        # 命主 / 身主
        mingzhu = chart.get("命主", chart.get("ming_zhu", ""))
        shenzhu = chart.get("身主", chart.get("shen_zhu", ""))
        if mingzhu:
            lines.append(f"命主：{mingzhu}")
        if shenzhu:
            lines.append(f"身主：{shenzhu}")

        # 三方四正信息
        if palaces:
            palace_names = [p.get("宫名", p.get("name", "")) for p in palaces[:6]]
            if palace_names:
                lines.append(f"主要宮位：{'、'.join(filter(None, palace_names))}")

    except Exception:
        pass

    return "；".join(lines) if lines else "命盤包含完整十二宮星曜配置"


def get_article_topic(index: Optional[int] = None) -> str:
    """轮换获取文章主题"""
    if index is not None:
        return ARTICLE_TOPICS[index % len(ARTICLE_TOPICS)]
    day_of_year = date.today().timetuple().tm_yday
    return ARTICLE_TOPICS[(day_of_year + random.randint(0, 5)) % len(ARTICLE_TOPICS)]


def build_prompt(topic: str, city: str, chart_summary: str, birth_info: dict) -> list:
    """构建 DeepSeek 生成文章的 prompt，嵌入命盘数据"""
    birthday_str = f"{birth_info['year']}年{birth_info['month']}月{birth_info['day']}日"

    system_prompt = """你是紫微斗数专家，精通繁体中文命理写作。请用专业但通俗易懂的繁体中文写一篇 SEO 优化的紫微斗数软文。

写作要求：
1. 标题格式：使用「紫微斗數XXX」或「XXX命盤解析」作为标题
2. 文章长度：1000-1500字
3. 语言风格：繁体中文，亲切神秘，有真实命盘分析的质感
4. SEO优化：自然融入长尾关键词，标题包含核心关键词
5. 内容结构：开篇引言（介绍命盘背景）→ 命盘核心分析（3-4小节带小标题，结合具体星曜）→ 给读者的建议 → CTA引导
6. 文章底部必须包含CTA，引导读者到 /index.html 免费排盘体验 和 /shop.html 购买完整解读
7. 文章要引用具体命盘数据（星曜、四化、宫位），让读者感觉基于真实数据
8. 情感基调：积极正面，给人希望和方向
9. 每段都不超过200字，段落之间空一行

输出格式为 JSON：
{
  "title": "文章标题（繁体）",
  "description": "SEO meta description，不超过160字",
  "keywords": "SEO keywords，逗号分隔，不超过10个",
  "content_html": "文章HTML正文（繁体，包含h2小标题、p段落，末尾CTA）"
}"""

    user_prompt = f"""请写一篇面向 {city} 读者的紫微斗数文章。

主题：{topic}

命盘背景信息：
- 出生时间：{birthday_str}（随机生成）
- 性别：{'男' if birth_info['gender'] == 'male' else '女'}
- 命盘摘要：{chart_summary}

请在文章中自然地融入以上命盘数据，让文章看起来是基于真实命盘分析的。
文章中的命盘数据可以适当演绎和扩展，使其更丰富有趣。

文章末尾的CTA请使用繁体中文，引导用户：
- 前往 /index.html 免费体验紫微斗数排盘
- 前往 /shop.html 购买完整AI解读

请直接输出JSON，不要加markdown代码块标记。"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def call_deepseek(messages: list) -> Optional[dict]:
    """调用 DeepSeek API 生成文章"""
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "***":
        print("⚠️  未设置 DEEPSEEK_API_KEY，使用模拟数据")
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            temperature=0.8,
            max_tokens=4000,
            timeout=60,
        )
        content = resp.choices[0].message.content.strip()
        # 去掉可能的 markdown 代码块包裹
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        return json.loads(content)
    except Exception as e:
        print(f"❌ DeepSeek API 调用失败: {e}")
        return None


def get_mock_article(topic: str, city: str, chart_summary: str, birth_info: dict) -> dict:
    """当API不可用时返回模拟文章"""
    gender_cn = '男' if birth_info['gender'] == 'male' else '女'
    birthday_str = f"{birth_info['year']}年{birth_info['month']}月{birth_info['day']}日"
    return {
        "title": f"紫微斗數看{topic} — 基於真實命盤深度解析",
        "description": f"紫微斗數專家為{city}讀者深度解析{topic}，結合真實命盤數據（{birthday_str}生，{gender_cn}），提供專業的運勢指引與人生建議。",
        "keywords": f"紫微斗數,{topic},{city}紫微斗數,命盤解析,真實命盤,排盤",
        "content_html": f"""<h2>開篇：命盤背景介紹</h2>
<p>本次命盤分析的主角出生於{gender_cn}性命主，生辰為{biday_str if False else birthday_str}。這是一張充滿潛力的命盤，命宮中的星曜組合展現出獨特的性格特質與人生走向。透過紫微斗數的深度解析，我們將一一揭開命盤中的奧秘。</p>

<h2>命盤核心數據：{topic}</h2>
<p>從命盤數據來看，{chart_summary}。這些星曜的排列與四化飛星的分布，構成了命主獨一無二的人生藍圖。特別值得注意的是，命宮中的主星決定了命主的核心性格，而財帛宮、官祿宮等宮位的配置則反映了事業發展與財富積累的潛力。</p>

<p>在紫微斗數的體系中，星曜的能量並非單獨運作，而是相互影響、彼此制衡。命盤中吉星的匯聚為命主帶來了貴人運與機遇，而煞星的存在則提醒命主需要更加謹慎行事，在挑戰中尋找成長的機會。</p>

<h2>對{city}命主的啟發</h2>
<p>對於身在{city}的命主來說，這座城市的能量與命盤中的遷移宮、財帛宮有著密切的聯繫。{city}作為國際都市，提供了豐富的發展機會，尤其適合命盤中遷移宮強旺、有化祿或化權的人在此發展事業。</p>

<p>命盤顯示，命主在{city}這片土地上，若能善用自身的星曜特質，結合城市的地緣優勢，將有機會在事業上取得突破性的進展。紫微斗數不僅是預測工具，更是一面鏡子，幫助我們看清自身的優勢與潛力。</p>

<h2>給命主的實用建議</h2>
<p>基於命盤分析，我們建議命主：</p>
<p>一、充分發揮命宮主星的優勢，選擇適合自己性格的職業方向。</p>
<p>二、關注流年運勢的變化，在化祿的年份積極進取，在化忌的年份保守穩健。</p>
<p>三、善用身邊的貴人資源，命盤中的左輔、右弼、天魁、天鉞等吉星顯示命主不乏貴人相助。</p>
<p>四、重視健康管理，疾厄宮的星曜配置提醒命主需要關注特定的健康議題。</p>

<div class="cta-section">
<p><strong>✨ 準備好探索您的命盤了嗎？</strong></p>
<p>👉 <a href="/index.html" style="color:#7b68ee;font-weight:600;">免費體驗紫微斗數排盤 →</a> 輸入出生資訊即可查看您的專屬命盤</p>
<p>👉 <a href="/shop.html" style="color:#f0d060;font-weight:600;">購買完整AI解讀 →</a> 解鎖3000+字的深度命盤分析</p>
</div>"""
    }


def traditional_to_simplified(text: str) -> str:
    """繁体中文转简体中文（使用 opencc 库）"""
    try:
        from opencc import OpenCC
        converter = OpenCC('t2s')
        return converter.convert(text)
    except ImportError:
        pass
    try:
        import zhconv
        return zhconv.convert(text, 'zh-cn')
    except ImportError:
        pass
    # Fallback: basic char-by-char mapping for common chars
    SIMPLE_MAP = {
        '為':'为','雲':'云','電':'电','發':'发','體':'体','會':'会','個':'个',
        '時':'时','說':'说','話':'话','學':'学','習':'习','書':'书','讀':'读',
        '寫':'写','後':'后','開':'开','關':'关','門':'门','問':'问','題':'题',
        '對':'对','錯':'错','點':'点','線':'线','麵':'面','機':'机','權':'权',
        '術':'术','運':'运','動':'动','勢':'势','態':'态','氣':'气','風':'风',
        '龍':'龙','鳳':'凤','萬':'万','億':'亿','數':'数','經':'经','驗':'验',
        '業':'业','從':'从','來':'来','東':'东','國':'国','時':'时','間':'间',
        '關':'关','係':'系','聯':'联','繫':'系','與':'与','並':'并','於':'于',
        '過':'过','還':'还','這':'这','麼':'么','嗎':'吗','裡':'里','裏':'里',
        '們':'们','沒':'没','讓':'让','給':'给','聽':'听','講':'讲','見':'见',
        '覺':'觉','愛':'爱','歡':'欢','離':'离','結':'结','束':'束','終':'终',
        '長':'长','淺':'浅','廣':'广','寬':'宽','強':'强','壞':'坏','麗':'丽',
        '醜':'丑','惡':'恶','偽':'伪','誠':'诚','實':'实','虛':'虚','優':'优',
        '勝':'胜','敗':'败','贏':'赢','輸':'输','戰':'战','鬥':'斗','爭':'争',
        '險':'险','財':'财','產':'产','貴':'贵','貧':'贫','窮':'穷','勞':'劳',
        '職':'职','階':'阶','級':'级','層':'层','際':'际','組':'组','織':'织',
        '團':'团','隊':'队','員':'员','師':'师','醫':'医','護':'护','盤':'盘',
        '宮':'宫','祿':'禄','殺':'杀','軍':'军','貪':'贪','狼':'狼','廉':'廉',
        '貞':'贞','梁':'梁','輔':'辅','弼':'弼','鉞':'钺','羅':'罗','鈴':'铃',
        '馬':'马','陽':'阳','陰':'阴','簡':'简','體':'体','瀏':'浏','覽':'览',
        '網':'网','頁':'页','資':'资','訊':'讯','編':'编','輯':'辑','標':'标',
        '準':'准','備':'备','檔':'档','案':'案','類':'类','區':'区','塊':'块',
        '處':'处','範':'范','圍':'围','創':'创','設':'设','計':'计','畫':'画',
        '圖':'图','聲':'声','樂':'乐','腦':'脑','視':'视','頻':'频','遊':'游',
        '戲':'戏','應':'应','該':'该','當':'当','雖':'虽','為':'为','變':'变',
        '現':'现','傳':'传','統':'统','專':'专','領':'领','導':'导','總':'总',
        '經':'经','歷':'历','進':'进','產':'产','務':'务','項':'项','計':'计',
        '劃':'划','規':'规','執':'执','監':'监','評':'评','報':'报','記':'记',
        '錄':'录','儲':'储','備':'备','復':'复','啟':'启','異':'异','錯':'错',
        '誤':'误','參':'参','數':'数','變':'变','類':'类','型':'型','協':'协',
        '議':'议','權':'权','義':'义','規':'规','條':'条','確':'确','認':'认',
        '驗':'验','證':'证','檢':'检','測':'测','試':'试','構':'构','據':'据',
        '庫':'库','連':'连','張':'张','該':'该','換':'换','訴':'诉','麼':'么',
        '還':'还','運':'运','勢':'势','態':'态','異':'异','鬥':'斗','數':'数',
        '飛':'飞','馬':'马','簽':'签','頻':'频','導':'导','準':'准','備':'备',
        '檔':'档','塊':'块','畫':'画','樂':'乐','戲':'戏','應':'应','當':'当',
        '雖':'虽','變':'变','現':'现','傳':'传','統':'统','專':'专','領':'领',
        '總':'总','歷':'历','進':'进','項':'项','計':'计','劃':'划','規':'规',
        '執':'执','監':'监','評':'评','報':'报','記':'记','錄':'录','儲':'储',
        '復':'复','啟':'启','異':'异','參':'参','數':'数','類':'类','型':'型',
        '協':'协','議':'议','權':'权','義':'义','規':'规','條':'条','確':'确',
        '認':'认','驗':'验','證':'证','檢':'检','測':'测','試':'试','構':'构',
        '據':'据','庫':'库','連':'连',
    }
    result = []
    for ch in text:
        if ch in SIMPLE_MAP:
            result.append(SIMPLE_MAP[ch])
        else:
            result.append(ch)
    return ''.join(result)


# ── 中文站特定样式 ──
CN_PAGE_STYLE = """
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif;background:#0a0a14;color:#d0c8e0;min-height:100vh;position:relative;line-height:1.8}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(1px 1px at 10%20%,rgba(255,255,255,.3),transparent),radial-gradient(1px 1px at 30%60%,rgba(255,255,255,.2),transparent),radial-gradient(1px 1px at 50%10%,rgba(255,255,255,.25),transparent),radial-gradient(1.5px 1.5px at 85%65%,rgba(255,215,0,.2),transparent),radial-gradient(1.5px 1.5px at 25%55%,rgba(123,104,238,.2),transparent);pointer-events:none;z-index:0}
body::after{content:'';position:fixed;top:50%;left:50%;width:700px;height:700px;margin:-350px 0 0 -350px;border-radius:50%;background:conic-gradient(from 0deg,transparent,rgba(123,104,238,.04),transparent 30%,rgba(123,104,238,.02),transparent 60%,rgba(123,104,238,.03),transparent);pointer-events:none;z-index:0;animation:bgSpin 40s linear infinite}
@keyframes bgSpin{from{transform:translate(-50%,-50%) rotate(0deg)}to{transform:translate(-50%,-50%) rotate(360deg)}}
.container{max-width:800px;margin:0 auto;padding:24px 20px;position:relative;z-index:1}
.article-header{text-align:center;padding:30px 0 20px;border-bottom:1px solid rgba(123,104,238,.12);margin-bottom:24px}
.article-header .meta{font-size:11px;color:#5a4a7a;letter-spacing:1px;margin-bottom:8px}
.article-header .meta .tag{display:inline-block;background:rgba(123,104,238,.12);border:1px solid rgba(123,104,238,.15);border-radius:4px;padding:1px 8px;font-size:10px;color:#7b68ee;margin-left:6px}
.article-header h1{font-family:'Noto Serif SC','Noto Serif TC',serif;font-size:26px;font-weight:900;background:linear-gradient(135deg,#e0c8ff,#7b68ee,#4a3aa0);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:2px;line-height:1.4}
.article-body{font-size:15px;color:#c8c0d8;padding:0 4px}
.article-body h2{font-size:18px;font-weight:700;color:#c4a0ff;margin:28px 0 12px;padding-bottom:6px;border-bottom:1px solid rgba(123,104,238,.1);letter-spacing:1.5px}
.article-body p{margin-bottom:16px;text-indent:2em}
.article-body a{color:#7b68ee;text-decoration:none;border-bottom:1px solid rgba(123,104,238,.2);transition:all .2s}
.article-body a:hover{color:#a080ff;border-color:#7b68ee}
.cta-section{margin-top:32px;padding:24px;border-radius:14px;background:linear-gradient(135deg,rgba(26,26,46,.93),rgba(16,16,30,.93));border:1px solid rgba(123,104,238,.18);text-align:center}
.cta-section p{text-indent:0!important;margin-bottom:10px!important}
.cta-section .cta-title{font-size:17px;font-weight:700;color:#e0c8ff;margin-bottom:12px;letter-spacing:1.5px}
.cta-section .cta-btn{display:inline-block;padding:10px 28px;margin:4px 6px;border-radius:10px;text-decoration:none;font-size:14px;font-weight:600;letter-spacing:1px;transition:all .3s}
.cta-section .cta-btn.primary{background:linear-gradient(135deg,#7b68ee,#5a4acd);color:#fff;border:none;box-shadow:0 4px 16px rgba(123,104,238,.25)}
.cta-section .cta-btn.primary:hover{transform:translateY(-2px);box-shadow:0 6px 24px rgba(123,104,238,.4)}
.cta-section .cta-btn.secondary{background:transparent;color:#c4a0ff;border:1px solid rgba(123,104,238,.25)}
.cta-section .cta-btn.secondary:hover{border-color:#7b68ee;background:rgba(123,104,238,.08)}
.city-badge{display:inline-flex;align-items:center;gap:4px;background:rgba(123,104,238,.08);border:1px solid rgba(123,104,238,.12);border-radius:20px;padding:3px 12px;font-size:11px;color:#9a8aaa}
.footer{text-align:center;padding:30px 0;color:#3a2a5a;font-size:11px;letter-spacing:.5px;line-height:1.8}
@media(max-width:600px){.article-header h1{font-size:22px}.article-body{font-size:14px}}
</style>
"""


def build_html(article: dict, topic: str, city: str, published_date: str, lang: str = "zh-Hant") -> str:
    """构建最终的文章 HTML 文件（含完整SEO：OG、Twitter、JSON-LD）"""
    lang_attr = lang
    lang_code = "zh-Hant" if lang == "zh-Hant" else "zh-Hans"
    locale = "zh_TW" if lang == "zh-Hant" else "zh_CN"
    schema_lang = "zh-Hant" if lang == "zh-Hant" else "zh-Hans"
    canonical_url = f"{WEBSITE}/articles/{published_date}-{simple_pinyin(topic)}.html"

    title_tag = article['title']
    # If simplified, convert title
    if lang == "zh-Hans":
        title_tag = traditional_to_simplified(article['title'])
        canonical_url = f"{WEBSITE}/articles/{published_date}-{simple_pinyin(topic)}-zhs.html"

    description = article.get('description', article['title'])
    if lang == "zh-Hans":
        description = traditional_to_simplified(description)

    content_html = article['content_html']
    if lang == "zh-Hans":
        # Simplify the content_html but preserve HTML tags
        def simplify_html(match):
            return traditional_to_simplified(match.group(0))
        content_html = re.sub(r'(?s)(<[^>]*>)|([^<]*)', lambda m: m.group(1) if m.group(1) else traditional_to_simplified(m.group(0)), content_html)

    city_title = city
    region_label = "华人区" if lang == "zh-Hans" else "華人區"

    og_title = title_tag[:80].replace('"', "'")
    og_desc = description[:150].replace('"', "'")
    pub_iso = f"{published_date[:4]}-{published_date[4:6]}-{published_date[6:8]}"
    json_ld = f"""{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "{og_title}",
  "description": "{og_desc}",
  "datePublished": "{pub_iso}",
  "author": {{"@type": "Person", "name": "Ziwei Master"}},
  "publisher": {{"@type": "Organization", "name": "Ziwei API"}},
  "inLanguage": "{schema_lang}"
}}"""

    return f"""<!DOCTYPE html>
<html lang="{lang_code}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title_tag}</title>
<meta name="description" content="{description}">
<meta name="keywords" content="{article.get('keywords', topic)}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{canonical_url}">
<meta property="og:type" content="article">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{og_desc}">
<meta property="og:url" content="{canonical_url}">
<meta property="og:locale" content="{locale}">
<meta property="og:image" content="https://ziweiapi.site/og-image.jpg">
<meta property="og:image:alt" content="紫微鬥數命盤推演">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{og_title}">
<script type="application/ld+json">{json_ld}</script>
{CN_PAGE_STYLE}
</head>
<body>
<div class="container">
  <article>
    <div class="article-header">
      <div class="meta">
        <span>{published_date}</span>
        <span class="tag">📊 真實命盤</span>
        <span class="city-badge">📍 {city_title}</span>
      </div>
      <h1>{title_tag}</h1>
    </div>
    <div class="article-body">
      {content_html}
    </div>
  </article>
  <div class="subscribe-section" style="margin-top:24px;padding:20px;border-radius:14px;background:linear-gradient(135deg,rgba(26,26,46,.93),rgba(16,16,30,.93));border:1px solid rgba(123,104,238,.18);text-align:center">
    <h3 style="font-size:16px;color:#c4a0ff;margin-bottom:10px">{'每日紫微运势订阅' if lang == 'zh-Hans' else '每日紫微運勢訂閱'}</h3>
    <p style="font-size:13px;color:#a898b8;margin-bottom:12px;text-indent:0">{'基于您的命盘，每日推送专属运势分析' if lang == 'zh-Hans' else '基於您的命盤，每日推送專屬運勢分析'}</p>
    <a href="/index.html#subscribe" class="cta-btn primary">{'立即订阅' if lang == 'zh-Hans' else '立即訂閱'}</a>
  </div>
  <div class="footer">
    <p>{'⚠️ AI生成内容仅供娱乐参考' if lang == 'zh-Hans' else '⚠️ AI生成內容僅供娛樂參考'}</p>
    <p>{'紫微斗数 · AI 命盘推演' if lang == 'zh-Hans' else '紫微鬥數 · AI 命盤推演'} | <a href="/index.html" style="color:#5a4a7a;text-decoration:none;">{'免费排盘' if lang == 'zh-Hans' else '免費排盤'}</a> | <a href="/shop.html" style="color:#5a4a7a;text-decoration:none;">{'购买 Key' if lang == 'zh-Hans' else '購買 Key'}</a></p>
    <p style="margin-top:6px;font-size:10px">© {datetime.now().year} {'紫微斗数 AI' if lang == 'zh-Hans' else '紫微鬥數 AI'} · {'版权所有' if lang == 'zh-Hans' else '版權所有'}</p>
  </div>
</div>
</body>
</html>"""


def generate_birth_info() -> dict:
    """生成随机的出生信息"""
    year = random.randint(1960, 2008)
    month = random.randint(1, 12)
    # 根据月份确定最大天数
    if month in [1, 3, 5, 7, 8, 10, 12]:
        max_day = 31
    elif month in [4, 6, 9, 11]:
        max_day = 30
    else:
        # 2月
        if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
            max_day = 29
        else:
            max_day = 28
    day = random.randint(1, max_day)
    hour = random.choice([0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22])
    gender = random.choice(["male", "female"])
    return {"year": year, "month": month, "day": day, "hour": hour, "gender": gender}


def run(index: Optional[int] = None, city: Optional[str] = None):
    """主运行函数"""
    if city is None:
        city = random.choice(CITIES)

    topic = get_article_topic(index)
    today_str = date.today().strftime("%Y%m%d")
    output_dir = BASE_DIR / "articles"

    print(f"📝 生成文章（基于真实命盘）：{topic}")
    print(f"📍 面向城市：{city}")
    print(f"📅 日期：{today_str}")

    # 1. 生成随机出生信息
    birth_info = generate_birth_info()
    gender_cn = '男' if birth_info['gender'] == 'male' else '女'
    print(f"👤 命盘：{birth_info['year']}年{birth_info['month']}月{birth_info['day']}日 時辰{birth_info['hour']}点，{gender_cn}性")

    # 2. 调用排盘引擎
    chart = None
    chart_summary = ""
    try:
        chart = run_engine(
            birth_info['year'], birth_info['month'], birth_info['day'],
            birth_info['hour'], birth_info['gender']
        )
        if chart.get("success") is not False:
            chart_summary = format_chart_summary(chart)
            print(f"🔮 排盘成功：{chart_summary[:80]}...")
        else:
            print("⚠️  排盘返回失败，使用通用命盘描述")
            chart_summary = f"{birth_info['year']}年{birth_info['month']}月生{gender_cn}命"
    except Exception as e:
        print(f"⚠️  排盘引擎异常: {e}，使用通用命盘描述")
        chart_summary = f"{birth_info['year']}年{birth_info['month']}月生{gender_cn}命"

    # 3. 调用 DeepSeek 生成文章
    messages = build_prompt(topic, city, chart_summary, birth_info)
    result = call_deepseek(messages)

    if result is None:
        print("🔧 使用模拟文章（API未配置或调用失败）")
        result = get_mock_article(topic, city, chart_summary, birth_info)

    # 4. 输出繁体版本
    pinyin = simple_pinyin(topic)
    filename_hant = f"{today_str}-{pinyin}.html"
    filepath_hant = output_dir / filename_hant

    html_hant = build_html(result, topic, city, today_str, lang="zh-Hant")
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath_hant.write_text(html_hant, encoding="utf-8")
    print(f"✅ 繁体文章已生成：{filepath_hant}")

    # 5. 输出简体版本
    filename_hans = f"{today_str}-{pinyin}-zhs.html"
    filepath_hans = output_dir / filename_hans

    html_hans = build_html(result, topic, city, today_str, lang="zh-Hans")
    filepath_hans.write_text(html_hans, encoding="utf-8")
    print(f"✅ 简体文章已生成：{filepath_hans}")

    print(f"📌 标题（繁）：{result['title']}")
    print(f"📌 标题（简）：{traditional_to_simplified(result['title'])}")
    print(f"🏷️  关键词：{result.get('keywords', '')}")

    return filepath_hant, filepath_hans


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="紫微斗数中文SEO软文自动生成（v2 - 真实命盘）")
    parser.add_argument("--index", type=int, default=None, help="文章主题索引")
    parser.add_argument("--city", type=str, default=None, help=f"面向城市（默认随机）")
    args = parser.parse_args()

    run(index=args.index, city=args.city)
