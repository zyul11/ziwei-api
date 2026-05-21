"""
Auto-generate chart landing pages for SEO content flywheel.
Generates 3 language variants per chart: zh-Hant, zh-Hans, en.
Each chart page is a unique URL with unique content.

Hooked into /v1/paipan-free after successful chart calculation.
"""

import json
import hashlib
import random
from datetime import datetime
from pathlib import Path
from typing import Optional

CHARTS_DIR = Path(__file__).parent.parent / "charts"

# ── City descriptions (for city-targeted SEO content) ──
# All 60+ cities from API CITY_PROFILES, in simplified Chinese as primary key
CITY_DESC_ALL = {
    "新加坡": {"hant": "新加坡是東南亞金融樞紐，華人文化濃厚，在此發展的命主多有跨國視野與國際商業機會",
              "hans": "新加坡是东南亚金融枢纽，华人文化浓厚，在此发展的命主多有跨国视野与国际商业机会",
              "en": "Singapore's multicultural environment matches the international outlook shown in this chart"},
    "吉隆坡": {"hant": "吉隆坡是馬來西亞首都，多元文化交融，命主在此發展易得跨文化合作與東南亞商業機遇",
              "hans": "吉隆坡是马来西亚首都，多元文化交融，命主在此发展易得跨文化合作与东南亚商业机遇",
              "en": "Kuala Lumpur's diverse business scene aligns with the adaptable star patterns in this chart"},
    "曼谷": {"hant": "曼谷是泰國首都，東南亞旅遊中心，命盤顯示在此發展者多有賺外地財的機遇與靈活應變特質",
              "hans": "曼谷是泰国首都，东南亚旅游中心，命盘显示在此发展者多有赚外地财的机遇与灵活应变特质",
              "en": "Bangkok's tourism-driven economy matches the adaptable and opportunistic stars in this chart"},
    "雅加达": {"hant": "雅加達是印尼首都，華人商業網絡發達，命盤顯示在此發展適合經貿與製造行業",
              "hans": "雅加达是印尼首都，华人商业网络发达，命盘显示在此发展适合经贸与制造行业",
              "en": "Jakarta's vast business networks align with the commercial potential of this chart"},
    "马尼拉": {"hant": "馬尼拉是菲律賓首都，BPO產業與服務業發達，命盤顯示在此發展適合服務與貿易領域",
              "hans": "马尼拉是菲律宾首都，BPO产业与服务业发达，命盘显示在此发展适合服务与贸易领域",
              "en": "Manila's BPO and service industries match the service-oriented stars in this reading"},
    "胡志明": {"hant": "胡志明市是越南經濟中心，新興製造業蓬勃，命盤顯示在此發展適合貿易與製造業",
              "hans": "胡志明市是越南经济中心，新兴制造业蓬勃，命盘显示在此发展适合贸易与制造业",
              "en": "Ho Chi Minh City's manufacturing boom aligns with the industrious star placements in this chart"},
    "台北": {"hant": "台北作為台灣的首都，紫微斗數命盤顯示在此發展的人常有強烈的事業企圖心與科技嗅覺",
              "hans": "台北作为台湾的首都，紫微斗数命盘显示在此发展的人常有强烈的事业企图心与科技嗅觉",
              "en": "Taipei offers strong career prospects; the Zi Wei chart indicates natural leadership qualities"},
    "新北": {"hant": "新北是台灣最大的城市之一，人口密集，紫微命盤反映此地發展需重視人際網絡與地產機遇",
              "hans": "新北是台湾最大的城市之一，人口密集，紫微命盘反映此地发展需重视人际网络与地产机遇",
              "en": "New Taipei's dense population rewards the networking potential indicated in this chart"},
    "台中": {"hant": "台中是台灣中部樞紐城市，命盤顯示在此定居者多有平衡事業與家庭的天賦與創意潛力",
              "hans": "台中是台湾中部枢纽城市，命盘显示在此定居者多有平衡事业与家庭的天赋与创意潜力",
              "en": "Taichung's balanced lifestyle matches the harmony-seeking energy of this birth chart"},
    "高雄": {"hant": "高雄是台灣南部國際港口城市，命主在此發展易得異地貴人相助與貿易機遇",
              "hans": "高雄是台湾南部国际港口城市，命主在此发展易得异地贵人相助与贸易机遇",
              "en": "Kaohsiung's port economy aligns with the travel and trade indicators in this chart"},
    "香港": {"hant": "香港是國際金融中心，命盤顯示在香港發展的人多有敏銳的商業嗅覺與理財天賦",
              "hans": "香港是国际金融中心，命盘显示在香港发展的人多有敏锐的商业嗅觉与理财天赋",
              "en": "Hong Kong's financial sector aligns with sharp business instincts shown in this chart"},
    "澳门": {"hant": "澳門是世界旅遊休閒中心，命盤顯示在此發展適合服務業、博彩與旅遊相關領域",
              "hans": "澳门是世界旅游休闲中心，命盘显示在此发展适合服务业、博彩与旅游相关领域",
              "en": "Macau's tourism and gaming industries match the risk-taking energy in this chart"},
    "上海": {"hant": "上海是中國金融中心，長三角核心城市，命盤顯示在此發展適合金融與貿易行業",
              "hans": "上海是中国金融中心，长三角核心城市，命盘显示在此发展适合金融与贸易行业",
              "en": "Shanghai's financial district corresponds with the wealth palaces in this chart"},
    "北京": {"hant": "北京是中國首都，政治文化中心，命盤顯示在此發展適合體制內與文化傳媒行業",
              "hans": "北京是中国首都，政治文化中心，命盘显示在此发展适合体制内与文化传媒行业",
              "en": "Beijing's political and cultural environment aligns with the authority stars in this chart"},
    "深圳": {"hant": "深圳是中國科技創新之都，命盤顯示在此發展適合科技創業與新興產業佈局",
              "hans": "深圳是中国科技创新之都，命盘显示在此发展适合科技创业与新兴产业布局",
              "en": "Shenzhen's tech innovation hub matches the entrepreneurial energy in this chart"},
    "广州": {"hant": "廣州是華南商貿中心，千年商都，命主在此發展易得商貿機遇與創業靈感",
              "hans": "广州是华南商贸中心，千年商都，命主在此发展易得商贸机遇与创业灵感",
              "en": "Guangzhou's millennia-old trade heritage aligns with the commercial stars in this chart"},
    "杭州": {"hant": "杭州是數字經濟重鎮，電商與互联网產業發達，命盤顯示在此適合科技與創意行業",
              "hans": "杭州是数字经济重镇，电商与互联网产业发达，命盘显示在此适合科技与创意行业",
              "en": "Hangzhou's digital economy matches tech-savvy star combinations in this reading"},
    "成都": {"hant": "成都以休閒安逸聞名，新經濟與文創產業崛起，命盤顯示在此適合文創與消費行業",
              "hans": "成都是以休闲安逸闻名，新经济与文创产业崛起，命盘显示在此适合文创与消费行业",
              "en": "Chengdu's laid-back yet innovative culture suits creative industries in this chart"},
    "纽约": {"hant": "紐約是全球金融中心，華人社區活躍，命盤顯示在此發展適合金融、法律與創意行業",
              "hans": "纽约是全球金融中心，华人社区活跃，命盘显示在此发展适合金融、法律与创意行业",
              "en": "New York's diverse opportunities align with the versatile star placements in this chart"},
    "洛杉矶": {"hant": "洛杉磯是美國西岸華人重鎮，娛樂產業中心，命盤顯示在此發展適合文化娛樂行業",
              "hans": "洛杉矶是美国西岸华人重镇，娱乐产业中心，命盘显示在此发展适合文化娱乐行业",
              "en": "Los Angeles entertainment industry connects with the artistic stars in this reading"},
    "旧金山": {"hant": "舊金山的矽谷是科技創新重鎮，命盤顯示在此發展適合科技創業與風險投資領域",
              "hans": "旧金山的硅谷是科技创新重镇，命盘显示在此发展适合科技创业与风险投资领域",
              "en": "San Francisco's Silicon Valley energy suites the innovative star placements here"},
    "西雅图": {"hant": "西雅圖是雲計算與航空產業中心，命盤顯示在此發展適合科技與工程領域",
              "hans": "西雅图是云计算与航空产业中心，命盘显示在此发展适合科技与工程领域",
              "en": "Seattle's tech and aerospace industries match the analytical stars in this chart"},
    "波士顿": {"hant": "波士頓是教育之都，哈佛MIT所在地，命盤顯示在此發展適合教育與生物科技領域",
              "hans": "波士顿是教育之都，哈佛MIT所在地，命盘显示在此发展适合教育与生物科技领域",
              "en": "Boston's academic excellence aligns with the wisdom-seeking stars in this chart"},
    "芝加哥": {"hant": "芝加哥是中西部經濟中心，大宗商品交易重鎮，命盤顯示適合金融與物流行業",
              "hans": "芝加哥是中西部经济中心，大宗商品交易重镇，命盘显示适合金融与物流行业",
              "en": "Chicago's trading hub energy matches the wealth-building stars in this chart"},
    "华盛顿": {"hant": "華盛頓是美國政治中心，政府與國際組織聚集地，命盤顯示適合政策與公共事務",
              "hans": "华盛顿是美国政治中心，政府与国际组织聚集地，命盘显示适合政策与公共事务",
              "en": "Washington DC's political scene aligns with authority-driven star patterns"},
    "休斯顿": {"hant": "休士頓是能源之都與航天中心，命盤顯示在此適合能源、醫療與航空領域",
              "hans": "休斯顿是能源之都与航天中心，命盘显示在此适合能源、医疗与航空领域",
              "en": "Houston's energy and space sectors match the pioneering stars in this chart"},
    "达拉斯": {"hant": "達拉斯是德州經濟中心，電信與金融業發達，命盤顯示適合科技與服務行業",
              "hans": "达拉斯是德州经济中心，电信与金融业发达，命盘显示适合科技与服务行业",
              "en": "Dallas' telecom and finance sectors align with this chart's professional stars"},
    "迈阿密": {"hant": "邁阿密是拉美門戶，旅遊與貿易金融中心，命盤顯示適合國際貿易與旅遊行業",
              "hans": "迈阿密是拉美门户，旅游与贸易金融中心，命盘显示适合国际贸易与旅游行业",
              "en": "Miami's Latin American gateway status matches the travel and trade stars here"},
    "亚特兰大": {"hant": "亞特蘭大是美國南方經濟中心，媒體與物流業發達，命盤顯示適合傳媒與交通行業",
              "hans": "亚特兰大是美国南方经济中心，媒体与物流业发达，命盘显示适合传媒与交通行业",
              "en": "Atlanta's media and logistics hub aligns with the communication stars in this chart"},
    "拉斯维加斯": {"hant": "拉斯維加斯是世界娛樂之都，命盤顯示在此發展適合旅遊、娛樂與酒店行業",
              "hans": "拉斯维加斯是世界娱乐之都，命盘显示在此发展适合旅游、娱乐与酒店行业",
              "en": "Las Vegas' entertainment focus matches the risk-taking and showmanship stars"},
    "温哥华": {"hant": "溫哥華是加拿大西岸華人聚居地，命盤顯示在此發展適合房地產、教育與自然相關行業",
              "hans": "温哥华是加拿大西岸华人聚居地，命盘显示在此发展适合房地产、教育与自然相关行业",
              "en": "Vancouver's multicultural Pacific vibe connects with the adaptable energy in this chart"},
    "多伦多": {"hant": "多倫多是加拿大最大城市，金融與多元文化中心，命盤顯示適合金融與科技行業",
              "hans": "多伦多是加拿大最大城市，金融与多元文化中心，命盘显示适合金融与科技行业",
              "en": "Toronto's diverse economy matches the multifaceted star combinations in this chart"},
    "蒙特利尔": {"hant": "蒙特婁是加拿大法語區文化中心，AI與遊戲產業發達，命盤顯示適合創意與科技行業",
              "hans": "蒙特利尔是加拿大法语区文化中心，AI与游戏产业发达，命盘显示适合创意与科技行业",
              "en": "Montreal's AI and gaming scene aligns with this chart's creative and technical stars"},
    "伦敦": {"hant": "倫敦是歐洲金融中心，文化底蘊深厚，命盤顯示在此發展適合金融、法律與文化產業",
              "hans": "伦敦是欧洲金融中心，文化底蕴深厚，命盘显示在此发展适合金融、法律与文化产业",
              "en": "London's global finance scene matches the international luck shown in this chart"},
    "巴黎": {"hant": "巴黎是藝術時尚之都，奢侈品與旅遊業興盛，命盤顯示適合美學與文化相關行業",
              "hans": "巴黎是艺术时尚之都，奢侈品与旅游业兴盛，命盘显示适合美学与文化相关行业",
              "en": "Paris' artistic heritage connects with the creative expressions in this chart"},
    "柏林": {"hant": "柏林是德國首都，創業與科技文化多元，命盤顯示適合初創、科技與文化領域",
              "hans": "柏林是德国首都，创业与科技文化多元，命盘显示适合初创、科技与文化领域",
              "en": "Berlin's startup scene matches the innovative and independent star patterns here"},
    "东京": {"hant": "東京是東亞經濟中心，精緻服務業與科技領先，命盤顯示適合專業技術與服務領域",
              "hans": "东京是东亚经济中心，精致服务业与科技领先，命盘显示适合专业技术与服务领域",
              "en": "Tokyo's precision industries suit the detail-oriented nature shown in this birth chart"},
    "首尔": {"hant": "首爾是韓國首都，韓流文化與科技產業發達，命盤顯示適合藝術與傳媒行業發展",
              "hans": "首尔是韩国首都，韩流文化与科技产业发达，命盘显示适合艺术与传媒行业发展",
              "en": "Seoul's creative industries match the artistic talents indicated in this chart"},
    "悉尼": {"hant": "雪梨是澳洲最大城市，南太平洋金融中心，命盤顯示在此發展適合教育與服務行業",
              "hans": "悉尼是澳洲最大城市，南太平洋金融中心，命盘显示在此发展适合教育与服务行业",
              "en": "Sydney's lifestyle-focused economy matches the balanced energy in this chart"},
    "墨尔本": {"hant": "墨爾本是澳洲文化之都，世界最宜居城市之一，命盤顯示適合教育與健康產業",
              "hans": "墨尔本是澳洲文化之都，世界最宜居城市之一，命盘显示适合教育与健康产业",
              "en": "Melbourne's arts and food scene aligns with the cultural appreciation stars here"},
    "迪拜": {"hant": "杜拜是中東商業旅遊中心，免稅經濟發達，命盤顯示適合國際貿易與服務行業",
              "hans": "迪拜是中东商业旅游中心，免税经济发达，命盘显示适合国际贸易与服务行业",
              "en": "Dubai's tax-free business hub matches the entrepreneurial and adventurous stars"},
}
# Simplified city name → data lookup (also handle common traditional variants)
CITY_ALIAS = {
    "雪梨": "悉尼", "悉尼": "悉尼",
    "紐約": "纽约", "纽约": "纽约",
    "洛杉磯": "洛杉矶", "洛杉矶": "洛杉矶",
    "舊金山": "旧金山", "旧金山": "旧金山",
    "倫敦": "伦敦", "伦敦": "伦敦",
    "溫哥華": "温哥华", "温哥华": "温哥华",
    "蒙特婁": "蒙特利尔", "蒙特利尔": "蒙特利尔",
    "杜拜": "迪拜", "迪拜": "迪拜",
    "墨爾本": "墨尔本", "墨尔本": "墨尔本",
    "休士頓": "休斯顿", "休斯顿": "休斯顿",
    "華盛頓": "华盛顿", "华盛顿": "华盛顿",
    "達拉斯": "达拉斯", "达拉斯": "达拉斯",
    "邁阿密": "迈阿密", "迈阿密": "迈阿密",
    "亞特蘭大": "亚特兰大", "亚特兰大": "亚特兰大",
    "拉斯維加斯": "拉斯维加斯", "拉斯维加斯": "拉斯维加斯",
    "鳳凰城": "凤凰城", "凤凰城": "凤凰城",
    "奧斯汀": "奥斯汀", "奥斯汀": "奥斯汀",
    "波特蘭": "波特兰", "波特兰": "波特兰",
    "奧蘭多": "奥兰多", "奥兰多": "奥兰多",
    "聖地亞哥": "圣地亚哥", "圣地亚哥": "圣地亚哥",
    "丹佛": "丹佛", "丹佛": "丹佛",
    "卡爾加里": "卡尔加里", "卡尔加里": "卡尔加里",
    "渥太華": "渥太华", "渥太华": "渥太华",
    "曼徹斯特": "曼彻斯特", "曼彻斯特": "曼彻斯特",
    "愛丁堡": "爱丁堡", "爱丁堡": "爱丁堡",
    "慕尼黑": "慕尼黑", "慕尼黑": "慕尼黑",
    "法蘭克福": "法兰克福", "法兰克福": "法兰克福",
    "阿姆斯特丹": "阿姆斯特丹", "阿姆斯特丹": "阿姆斯特丹",
    "蘇黎世": "苏黎世", "苏黎世": "苏黎世",
    "日內瓦": "日内瓦", "日内瓦": "日内瓦",
    "斯德哥爾摩": "斯德哥尔摩", "斯德哥尔摩": "斯德哥尔摩",
    "哥本哈根": "哥本哈根", "哥本哈根": "哥本哈根",
    "赫爾辛基": "赫尔辛基", "赫尔辛基": "赫尔辛基",
    "馬德里": "马德里", "马德里": "马德里",
    "巴塞隆納": "巴塞罗那", "巴塞罗那": "巴塞罗那", "巴塞隆拿": "巴塞罗那",
    "米蘭": "米兰", "米兰": "米兰",
    "羅馬": "罗马", "罗马": "罗马",
    "維也納": "维也纳", "维也纳": "维也纳",
    "布拉格": "布拉格", "布拉格": "布拉格",
    "都柏林": "都柏林", "都柏林": "都柏林",
    "布魯塞爾": "布鲁塞尔", "布鲁塞尔": "布鲁塞尔",
    "里斯本": "里斯本", "里斯本": "里斯本",
    "大阪": "大阪", "大阪": "大阪",
    "東京": "东京", "东京": "东京",
    "布里斯班": "布里斯班", "布里斯班": "布里斯班",
    "珀斯": "珀斯", "珀斯": "珀斯",
    "奧克蘭": "奥克兰", "奥克兰": "奥克兰",
    "開普敦": "开普敦", "开普敦": "开普敦",
    "孟買": "孟买", "孟买": "孟买",
    "班加羅爾": "班加罗尔", "班加罗尔": "班加罗尔",
    "胡志明市": "胡志明", "胡志明": "胡志明",
    "雅加達": "雅加达", "雅加达": "雅加达",
    "馬尼拉": "马尼拉", "马尼拉": "马尼拉",
}

def _resolve_city(name: str) -> str:
    """Convert any city name variant to the lookup key"""
    return CITY_ALIAS.get(name, name)

def get_city_desc(name: str, lang: str = "hant") -> str:
    key = _resolve_city(name)
    data = CITY_DESC_ALL.get(key, {})
    return data.get(lang, f"{name}是{_region_fallback(name)}，在此發展的命主命盤與當地能量交互影響深遠")

def _region_fallback(name: str) -> str:
    regions = {"新加坡":"東南亞金融中心","吉隆坡":"馬來西亞首都","曼谷":"泰國首都",
               "台北":"台灣首都","香港":"國際都市","上海":"中國經濟中心",
               "北京":"中國首都","纽约":"美国東岸大都市","东京":"日本首都",
               "伦敦":"欧洲金融中心","巴黎":"法国首都","首尔":"韩国首都",
               "悉尼":"澳洲最大城市","迪拜":"中东商业中心"}
    return regions.get(_resolve_city(name), "華人聚居城市")

# ── Star names translation ──
STAR_NAMES = {
    "紫微": {"zh-Hant": "紫微", "zh-Hans": "紫微", "en": "Zi Wei (Emperor)"},
    "天机": {"zh-Hant": "天機", "zh-Hans": "天机", "en": "Tian Ji (Wisdom)"},
    "太阳": {"zh-Hant": "太陽", "zh-Hans": "太阳", "en": "Tai Yang (Sun)"},
    "武曲": {"zh-Hant": "武曲", "zh-Hans": "武曲", "en": "Wu Qu (Finance)"},
    "天同": {"zh-Hant": "天同", "zh-Hans": "天同", "en": "Tian Tong (Harmony)"},
    "廉贞": {"zh-Hant": "廉貞", "zh-Hans": "廉贞", "en": "Lian Zhen (Integrity)"},
    "天府": {"zh-Hant": "天府", "zh-Hans": "天府", "en": "Tian Fu (Stability)"},
    "太阴": {"zh-Hant": "太陰", "zh-Hans": "太阴", "en": "Tai Yin (Moon)"},
    "贪狼": {"zh-Hant": "貪狼", "zh-Hans": "贪狼", "en": "Tan Lang (Romance)"},
    "巨门": {"zh-Hant": "巨門", "zh-Hans": "巨门", "en": "Ju Men (Eloquence)"},
    "天相": {"zh-Hant": "天相", "zh-Hans": "天相", "en": "Tian Xiang (Aid)"},
    "天梁": {"zh-Hant": "天梁", "zh-Hans": "天梁", "en": "Tian Liang (Blessing)"},
    "七杀": {"zh-Hant": "七殺", "zh-Hans": "七杀", "en": "Qi Sha (Valor)"},
    "破军": {"zh-Hant": "破軍", "zh-Hans": "破军", "en": "Po Jun (Change)"},
}

PALACE_NAMES = {
    "命宫": {"zh-Hant": "命宮", "zh-Hans": "命宫", "en": "Life Palace"},
    "兄弟宫": {"zh-Hant": "兄弟宮", "zh-Hans": "兄弟宫", "en": "Siblings Palace"},
    "夫妻宫": {"zh-Hant": "夫妻宮", "zh-Hans": "夫妻宫", "en": "Marriage Palace"},
    "子女宫": {"zh-Hant": "子女宮", "zh-Hans": "子女宫", "en": "Children Palace"},
    "财帛宫": {"zh-Hant": "財帛宮", "zh-Hans": "财帛宫", "en": "Wealth Palace"},
    "疾厄宫": {"zh-Hant": "疾厄宮", "zh-Hans": "疾厄宫", "en": "Health Palace"},
    "迁移宫": {"zh-Hant": "遷移宮", "zh-Hans": "迁移宫", "en": "Travel Palace"},
    "交友宫": {"zh-Hant": "交友宮", "zh-Hans": "交友宫", "en": "Friends Palace"},
    "官禄宫": {"zh-Hant": "官祿宮", "zh-Hans": "官禄宫", "en": "Career Palace"},
    "田宅宫": {"zh-Hant": "田宅宮", "zh-Hans": "田宅宫", "en": "Property Palace"},
    "福德宫": {"zh-Hant": "福德宮", "zh-Hans": "福德宫", "en": "Fortune Palace"},
    "父母宫": {"zh-Hant": "父母宮", "zh-Hans": "父母宫", "en": "Parents Palace"},
}

# ── Rotating advice pools (for content variety) ──
# Each pool has 20+ items. Combined with city + birthday + star, yields huge variety.
LUCKY_ITEMS_HANT = [
    "幸運顏色：金色與紫色，有助提升貴人運",
    "幸運方向：東南方，利於事業發展",
    "幸運數字：3、6、9，可作為日常選擇參考",
    "幸運方位：北方，適合遠行與簽約",
    "幸運色系：藍色系，有助沉穩思考",
    "幸運物品：玉石飾品，可增強能量場",
    "幸運色：綠色與白色，助健康和諧",
    "幸運食物：紅豆與地瓜，補氣養身",
    "開運方位：西南方，桃花人際兩得意",
    "幸運月份：農曆二月與八月，事務順遂",
    "配戴金屬飾品可助財運流通",
    "幸運寶石：黃水晶，招財聚福",
    "幸運時間：午時與酉時，決策大事吉",
    "幸運方向：東方，利於求學考運",
    "開運植物：綠蘿與發財樹，旺宅運",
    "幸運數字組合：2、5、8，購物選號參考",
    "幸運色系：紅色系，增強自信與行動力",
    "幸運物品：木雕工藝品，有助創意靈感",
    "開運方向：正南，適合事業拓展談判",
    "幸運飾品：珍珠或水晶，安神定心",
    "幸運活動：登山健行，吸收自然能量",
    "幸運之風水：書桌靠窗，前途光明",
]
LUCKY_ITEMS_HANS = [
    "幸运颜色：金色与紫色，有助提升贵人运",
    "幸运方向：东南方，利于事业发展",
    "幸运数字：3、6、9，可作为日常选择参考",
    "幸运方位：北方，适合远行与签约",
    "幸运色系：蓝色系，有助沉稳思考",
    "幸运物品：玉石饰品，可增强能量场",
    "幸运色：绿色与白色，助健康和谐",
    "幸运食物：红豆与地瓜，补气养身",
    "开运方位：西南方，桃花人际两得意",
    "幸运月份：农历二月与八月，事务顺遂",
    "佩戴金属饰品可助财运流通",
    "幸运宝石：黄水晶，招财聚福",
    "幸运时间：午时与酉时，决策大事吉",
    "幸运方向：东方，利于求学考运",
    "开运植物：绿萝与发财树，旺宅运",
    "幸运数字组合：2、5、8，购物选号参考",
    "幸运色系：红色系，增强自信与行动力",
    "幸运物品：木雕工艺品，有助创意灵感",
    "开运方向：正南，适合事业拓展谈判",
    "幸运饰品：珍珠或水晶，安神定心",
    "幸运活动：登山健行，吸收自然能量",
    "幸运之风：书桌靠窗，前途光明",
]
LUCKY_ITEMS_EN = [
    "Lucky color: Gold and purple — enhances mentor luck",
    "Lucky direction: Southeast — beneficial for career",
    "Lucky numbers: 3, 6, 9 — consider for daily choices",
    "Lucky direction: North — good for travel and signing",
    "Lucky color: Blue tones — promotes calm thinking",
    "Lucky item: Jade accessories — amplifies energy field",
    "Lucky color: Green and white — supports health and harmony",
    "Lucky meal: Red beans and sweet potato — nourishing energy",
    "Lucky direction: Southwest — good for relationships",
    "Lucky months: 2nd and 8th lunar month — smooth sailing",
    "Wearing metal accessories supports wealth flow",
    "Lucky crystal: Citrine — attracts prosperity",
    "Lucky hours: 11am-1pm and 5-7pm — best for decisions",
    "Lucky direction: East — beneficial for studies and exams",
    "Lucky plant: Pothos and money tree — enhances home luck",
    "Lucky numbers: 2, 5, 8 — reference for daily choices",
    "Lucky color: Red tones — boosts confidence and action",
    "Lucky item: Wood carvings — sparks creative inspiration",
    "Lucky direction: South — ideal for career negotiations",
    "Lucky accessory: Pearl or crystal — calms the mind",
    "Lucky activity: Hiking — absorbs natural energy",
    "Lucky feng shui: Desk near window — bright future",
]

ATTENTIONS_HANT = [
    "注意人際關係中的溝通方式，避免因直率引發誤會",
    "投資理財宜保守，短期內避免高風險操作",
    "健康方面注意腸胃問題，飲食規律為上",
    "事業上適合穩中求進，不宜急於求成",
    "感情運勢平穩，單身者可多參與社交活動",
    "出行注意交通安全，尤其夜間外出",
    "近期財運波動，謹慎處理大額支出",
    "注意職場小人，重要事項留書面記錄",
    "健康提示：睡眠品質需改善，避免熬夜",
    "家庭關係和諧為重，避免因小事起爭執",
    "本月不宜簽訂長約，宜觀望為主",
    "子女教育需耐心引導，不宜過度施壓",
    "注意牙齒健康，定期檢查",
    "合作項目需明確分工，避免責任不清",
    "出國運勢平穩，但需確認文件齊全",
    "注意肩頸酸痛，定時伸展活動",
    "人際往來量力而為，勿過度承諾",
    "購屋置產宜多方比較，不急於下決定",
    "寵物健康需留意，飲食要規律",
    "法律事務需諮詢專業人士，勿自行處理",
    "投資新領域前先做足功課",
    "注意用水用電安全，定期檢查管線",
]
ATTENTIONS_HANS = [
    "注意人际关系中的沟通方式，避免因直率引发误会",
    "投资理财宜保守，短期内避免高风险操作",
    "健康方面注意肠胃问题，饮食规律为上",
    "事业上适合稳中求进，不宜急于求成",
    "感情运势平稳，单身者可多参与社交活动",
    "出行注意交通安全，尤其夜间外出",
    "近期财运波动，谨慎处理大额支出",
    "注意职场小人，重要事项留书面记录",
    "健康提示：睡眠品质需改善，避免熬夜",
    "家庭关系和谐为重，避免因小事起争执",
    "本月不宜签订长约，宜观望为主",
    "子女教育需耐心引导，不宜过度施压",
    "注意牙齿健康，定期检查",
    "合作项目需明确分工，避免责任不清",
    "出国运势平稳，但需确认文件齐全",
    "注意肩颈酸痛，定时伸展活动",
    "人际往来量力而为，勿过度承诺",
    "购屋置产宜多方比较，不急於下决定",
    "宠物健康需留意，饮食要规律",
    "法律事务需咨询专业人士，勿自行处理",
    "投资新领域前先做足功课",
    "注意用水用电安全，定期检查管线",
]
ATTENTIONS_EN = [
    "Watch your communication style — directness may cause misunderstandings",
    "Conservative approach to investments, avoid high-risk moves short-term",
    "Pay attention to digestive health — keep regular eating habits",
    "Steady progress in career — don't rush for quick wins",
    "Love life is stable — singles should attend more social events",
    "Be careful with travel safety, especially at night",
    "Watch for financial fluctuations — be cautious with large expenses",
    "Beware of workplace politics — document important matters",
    "Sleep quality needs improvement — avoid staying up late",
    "Prioritize family harmony — don't let small things cause arguments",
    "Avoid signing long-term contracts this month — better to wait",
    "Be patient with children's education — don't over-pressure them",
    "Pay attention to dental health — regular checkups recommended",
    "Clearly define responsibilities in collaborative projects",
    "International travel luck is stable — confirm documents are ready",
    "Watch for shoulder and neck tension — stretch regularly",
    "Don't overcommit socially — know your limits",
    "Compare options carefully before real estate purchases",
    "Monitor pet health — keep a regular feeding schedule",
    "Consult professionals for legal matters — don't DIY",
    "Do thorough research before investing in new areas",
    "Check water and electrical safety — inspect pipes regularly",
]

CAREER_TIPS_HANT = [
    "適合從事管理、策劃類工作",
    "創意與藝術相關行業有發展潛力",
    "教育、諮詢類職業能發揮你的優勢",
    "技術研發領域適合你的性格特質",
    "人際交往密集的行業如公關、銷售值得考慮",
    "自由職業或創業在當前運勢中有利",
    "金融與會計領域可發揮你的細心特質",
    "醫療健康產業適合有服務熱忱的你",
    "科技新創環境能激發你的創新潛能",
    "文化傳媒行業適合表達能力出眾的你",
    "國際貿易與跨國業務與你的命格契合",
    "地產與物業管理行業有長期發展空間",
    "物流運輸業在未來數年呈上升趨勢",
    "餐飲與酒店管理適合注重細節的你",
    "法律與合規領域能發揮你的邏輯思維",
    "人力資源與培訓行業適合善於溝通者",
    "建築與室內設計發揮你的審美能力",
    "非營利組織與公益事業能實現價值感",
    "數據分析與AI行業與你的命盤呼應",
    "翻譯與語言相關工作適合你的天賦",
    "體育健身產業在當前運勢中有潛力",
    "農業與食品科技是新興好方向",
]
CAREER_TIPS_HANS = [
    "适合从事管理、策划类工作",
    "创意与艺术相关行业有发展潜力",
    "教育、咨询类职业能发挥你的优势",
    "技术研发领域适合你的性格特质",
    "人际交往密集的行业如公关、销售值得考虑",
    "自由职业或创业在当前运势中有利",
    "金融与会计领域可发挥你的细心特质",
    "医疗健康产业适合有服务热忱的你",
    "科技新创环境能激发你的创新潜能",
    "文化传媒行业适合表达能力出众的你",
    "国际贸易与跨国业务与你的命格契合",
    "地产与物业管理行业有长期发展空间",
    "物流运输业在未来数年呈上升趋势",
    "餐饮与酒店管理适合注重细节的你",
    "法律与合规领域能发挥你的逻辑思维",
    "人力资源与培训行业适合善于沟通者",
    "建筑与室内设计发挥你的审美能力",
    "非营利组织与公益事业能实现价值感",
    "数据分析与AI行业与你的命盘呼应",
    "翻译与语言相关工作适合你的天赋",
    "体育健身产业在当前运势中有潜力",
    "农业与食品科技是新兴好方向",
]
CAREER_TIPS_EN = [
    "Suited for management and planning roles",
    "Creative and artistic fields show potential",
    "Education and consulting leverage your strengths",
    "Technical R&D aligns with your character",
    "People-oriented fields like PR and sales are worth considering",
    "Freelancing or entrepreneurship is favorable in current运势",
    "Finance and accounting play to your detail-oriented nature",
    "Healthcare suits those with a service-oriented spirit",
    "Tech startup environments spark your innovative potential",
    "Media and communications fit your expressive abilities",
    "International trade aligns with your destiny pattern",
    "Real estate offers long-term growth potential",
    "Logistics industry is on an upward trend",
    "Hospitality management suits your attention to detail",
    "Legal and compliance fields leverage your logical thinking",
    "HR and training roles suit your communication skills",
    "Architecture and interior design express your aesthetic sense",
    "Non-profit work fulfills your sense of purpose",
    "Data analytics and AI resonate with your chart",
    "Translation and language work match your talents",
    "Fitness industry has potential in current运势",
    "Agriculture and food tech are emerging good paths",
]

# ── New content dimension pools ──
# Writing angles / tones to create variety for same-birthday pages
WRITING_ANGLES_HANT = [
    "仔細觀察命宮的星曜配置，",
    "本命盤揭示的訊息十分耐人尋味，",
    "紫微斗數中有一句經典斷語：吉星入命，福祿隨身，",
    "有趣的是，這張命盤呈現了一種平衡之美——",
    "透過命盤的十二宮位，我們能看到人生各面向的互動，",
    "這是一張充滿張力的命盤，吉凶交織中透露出命主的獨特氣質，",
    "若從宏觀角度審視此盤，",
    "翻開這張人生地圖，首先映入眼簾的是",
]
WRITING_ANGLES_HANS = [
    "从紫微斗数的角度来看，",
    "仔细观察命宫的星曜配置，",
    "本命盘揭示的信息十分耐人寻味，",
    "紫微斗数中有一句经典断语：吉星入命，福禄随身，",
    "有趣的是，这张命盘呈现了一种平衡之美——",
    "透过命盘的十二宫位，我们能看到人生各面向的互动，",
    "这是一张充满张力的命盘，吉凶交织中透露出命主的独特气质，",
    "若从宏观角度审视此盘，",
    "翻开这张人生地图，首先映入眼帘的是",
]
WRITING_ANGLES_EN = [
    "This chart reveals a fascinating blueprint of potential paths — ",
    "Looking closely at the stars in the Life Palace shows that ",
    "What makes this chart particularly interesting is ",
    "An ancient Zi Wei saying goes: 'When auspicious stars guard the Life Palace, fortune follows' — and here we see ",
    "This birth chart presents a beautiful balance — ",
    "Examining all twelve palaces reveals interesting interactions, starting with ",
    "This is a chart full of dynamic tension, where the interplay of stars reveals ",
    "Taking a wide-angle view of this life map, we first notice ",
    "The celestial arrangement here tells a compelling story — ",
]

# Palace focus — emphasize different palaces to vary content
PALACE_FOCUS_HANT = ["財帛宮", "官祿宮", "夫妻宮", "遷移宮", "田宅宮", "福德宮"]
PALACE_FOCUS_HANS = ["财帛宫", "官禄宫", "夫妻宫", "迁移宫", "田宅宫", "福德宫"]
PALACE_FOCUS_EN = ["Wealth Palace", "Career Palace", "Marriage Palace", "Travel Palace", "Property Palace", "Fortune Palace"]

PALACE_DESCS_HANT = {
    "財帛宮": "理財能力與財源方向是人生的核心課題之一，",
    "官祿宮": "事業發展與社會地位決定了人生成就的高度，",
    "夫妻宮": "情感世界與婚姻質量深刻影響人生的幸福感，",
    "遷移宮": "外出發展與人際拓展往往帶來意想不到的機遇，",
    "田宅宮": "居所與資產配置反映了命主的安定感需求，",
    "福德宮": "精神世界與內在修養是人生質量的底色，",
}
PALACE_DESCS_HANS = {
    "财帛宫": "理财能力与财源方向是人生的核心课题之一，",
    "官禄宫": "事业发展与社会地位决定了人生成就的高度，",
    "夫妻宫": "情感世界与婚姻质量深刻影响人生的幸福感，",
    "迁移宫": "外出发展与人际拓展往往带来意想不到的机遇，",
    "田宅宫": "居所与资产配置反映了命主的安定感需求，",
    "福德宫": "精神世界与内在修养是人生质量的底色，",
}
PALACE_DESCS_EN = {
    "Wealth Palace": "Financial skills and income sources shape the core of life's journey — ",
    "Career Palace": "Career development and social standing define the heights one can reach — ",
    "Marriage Palace": "Emotional bonds and partnership quality deeply influence life's happiness — ",
    "Travel Palace": "Exploring beyond borders often brings unexpected opportunities — ",
    "Property Palace": "Home and asset arrangements reflect one's need for stability — ",
    "Fortune Palace": "Inner peace and spiritual growth form the foundation of life quality — ",
}

def _pick(seq, seed):
    """Deterministic pick from a list based on seed hash"""
    idx = hash(seed) % len(seq)
    return seq[idx]

def _slug(text):
    s = text.lower().strip()
    s = ''.join(c for c in s if c.isalnum() or c in '- _').replace(' ', '-')[:40]
    return s

def build_chart_page(chart: dict, birth_info: dict, reading: str = "",
                     request_lang: str = "zh-Hant", city: str = "") -> list:
    """
    Generate chart landing pages for all 3 languages.
    Returns list of (filepath, url_path) tuples.
    
    chart: return value from ziwei-engine.js
    birth_info: {year, month, day, hour, gender}
    reading: AI reading text (zh-Hant)
    city: city name for geo-targeted SEO (e.g., "新加坡", "香港", "東京")
    """
    import os, re
    
    today = datetime.now()
    date_str = today.strftime("%Y%m%d")
    
    # Build a unique page ID - use counter to prevent duplicate chart overwrites
    _counter_file = CHARTS_DIR / ".counter"
    try:
        counter = int(_counter_file.read_text().strip())
    except:
        counter = 0
    counter += 1
    _counter_file.write_text(str(counter))
    
    raw = json.dumps(chart.get("命盤", {}), ensure_ascii=False, sort_keys=True)
    uid = hashlib.md5(raw.encode()).hexdigest()[:6]
    page_id = f"{date_str}-{counter:04d}"
    
    # Extract chart info
    info = chart.get("基本信息", {})
    birth_y = birth_info.get("year", 0)
    birth_m = birth_info.get("month", 0)
    birth_d = birth_info.get("day", 0)
    birth_h = birth_info.get("hour", 0)
    gender = birth_info.get("gender", "male")
    
    minggong = info.get("命宮", "")
    wuxingju = info.get("五行局", "")
    bazi = info.get("八字", "")
    
    # Get 命宫主星
    pan = chart.get("命盤", {})
    minggong_star = ""
    minggong_data = pan.get("命宮", {}) if isinstance(pan, dict) else {}
    if isinstance(minggong_data, dict):
        minggong_star = minggong_data.get("主星", "")
    
    # Collect star placement text
    palace_lines_hant = []
    palace_lines_hans = []
    palace_lines_en = []
    
    main_star_in_palace = ""  # for URL slug
    if isinstance(pan, dict):
        for pname, pdata in pan.items():
            if isinstance(pdata, dict):
                star = pdata.get("主星", "")
                if star and star in STAR_NAMES:
                    p_en = PALACE_NAMES.get(pname, {}).get("en", pname)
                    palace_lines_hant.append(f"　{pname} — {STAR_NAMES[star]['zh-Hant']}")
                    palace_lines_hans.append(f"　{pname} — {STAR_NAMES[star]['zh-Hans']}")
                    palace_lines_en.append(f"　{p_en} — {STAR_NAMES[star]['en']}")
                    if not main_star_in_palace:
                        main_star_in_palace = f"{star}-{pname}"
    
    # Generate short unique description (if reading available, extract first sentence)
    short_desc_hant = "此命盤展現獨特的星曜組合，反映命主的天賦特質與人生軌跡。"
    short_desc_hans = "此命盘展现独特的星曜组合，反映命主的天赋特质与人生轨迹。"
    short_desc_en = "This chart reveals a unique combination of stars, reflecting the native's inherent qualities and life path."
    
    if reading:
        sentences = [s.strip() for s in reading.split('。') if s.strip()]
        if sentences:
            s = sentences[0][:100]
            short_desc_hant = s + ("。" if not s.endswith("。") else "")
            # rough simplified conversion
            short_desc_hans = short_desc_hant.replace("鬥", "斗").replace("宮", "宫").replace("殺", "杀")
            short_desc_en = "This Chinese astrology chart reveals insights about the native's personality, talents, and life path."
    
    # Build slug for URL
    star_slug = _slug(main_star_in_palace or f"chart-{uid}")
    base_url = f"/charts/{page_id}"
    
    # Template selector (3 visual templates based on hash)
    template_ver = int(uid[:2], 16) % 3
    
    # Generate 3 language files
    results = []
    langs = ["zh-Hant", "zh-Hans", "en"]
    lang_suffixes = {"zh-Hant": "", "zh-Hans": "-zhs", "en": "-en"}
    lang_html = {"zh-Hant": "zh-Hant", "zh-Hans": "zh-Hans", "en": "en"}
    # City-aware titles and descriptions
    city_hant = ""
    city_hans = ""
    city_en = ""
    city_slug = ""
    if city:
        city_hant = get_city_desc(city, "hant")
        city_hans = get_city_desc(city, "hans")
        city_en = get_city_desc(city, "en")
        city_slug = _slug(_resolve_city(city))
    
    lang_titles = {
        "zh-Hant": f"{minggong_star}坐命 — {birth_y}年{birth_m}月{birth_d}日命盤解析" + (f"｜{city}" if city else ""),
        "zh-Hans": f"{minggong_star}坐命 — {birth_y}年{birth_m}月{birth_d}日命盘解析" + (f"｜{city}" if city else ""),
        "en": f"Chinese Astrology Chart: {minggong_star} in Life Palace — {birth_y}-{birth_m:02d}-{birth_d:02d}" + (f" ({city})" if city else ""),
    }
    lang_descs = {
        "zh-Hant": f"{birth_y}年{birth_m}月{birth_d}日出生，{minggong_star}坐命。免費紫微斗數排盤即得完整命盤解讀。" + (f" {city}在地命理指南。" if city else ""),
        "zh-Hans": f"{birth_y}年{birth_m}月{birth_d}日出生，{minggong_star}坐命。免费紫微斗数排盘即得完整命盘解读。" + (f" {city}在地命理指南。" if city else ""),
        "en": f"Free Chinese astrology chart for {birth_y}-{birth_m:02d}-{birth_d:02d}. {minggong_star} in Life Palace. Get your free birth chart reading." + (f" Local guide for {city}." if city else ""),
    }
    
    # Build hreflang links
    def hreflang_links(lang):
        links = ""
        for l in langs:
            sfx = lang_suffixes[l]
            links += f'    <link rel="alternate" hreflang="{lang_html[l]}" href="https://ziweiapi.site{base_url}{sfx}.html">\n'
        links += f'    <link rel="alternate" hreflang="x-default" href="https://ziweiapi.site{base_url}.html">\n'
        return links
    
    def lang_switcher(current_lang):
        btns = ""
        for l in langs:
            sfx = lang_suffixes[l]
            active = ' class="lang-btn active"' if l == current_lang else ''
            label = {"zh-Hant": "繁", "zh-Hans": "简", "en": "EN"}[l]
            btns += f'      <a href="{base_url}{sfx}.html"{active}>{label}</a>\n'
        return btns
    
    def reading_section(txt, lang):
        if not txt or len(txt) < 10:
            return ""
        # Split into paragraphs
        paras = txt.replace("\n\n", "||").replace("\n", " ").split("||")
        html = ""
        for p in paras:
            p = p.strip()
            if p:
                html += f'    <p style="font-size:13px;color:#7a6a9a;line-height:1.9;margin-bottom:10px">{p}</p>\n'
        return html
    
    for lang in langs:
        suffix = lang_suffixes[lang]
        filename = f"{page_id}{suffix}.html"
        filepath = CHARTS_DIR / filename
        
        lucky = _pick(LUCKY_ITEMS_HANT if lang == "zh-Hant" else (LUCKY_ITEMS_HANS if lang == "zh-Hans" else LUCKY_ITEMS_EN), uid)
        attention = _pick(ATTENTIONS_HANT if lang == "zh-Hant" else (ATTENTIONS_HANS if lang == "zh-Hans" else ATTENTIONS_EN), uid + "a")
        career = _pick(CAREER_TIPS_HANT if lang == "zh-Hant" else (CAREER_TIPS_HANS if lang == "zh-Hans" else CAREER_TIPS_EN), uid + "b")
        # New content dimensions for variety
        angle = _pick(WRITING_ANGLES_HANT if lang == "zh-Hant" else (WRITING_ANGLES_HANS if lang == "zh-Hans" else WRITING_ANGLES_EN), uid + "c")
        focus_palace = _pick(PALACE_FOCUS_HANT if lang == "zh-Hant" else (PALACE_FOCUS_HANS if lang == "zh-Hans" else PALACE_FOCUS_EN), uid + "d")
        focus_desc = (PALACE_DESCS_HANT if lang == "zh-Hant" else (PALACE_DESCS_HANS if lang == "zh-Hans" else PALACE_DESCS_EN)).get(focus_palace, "")
        
        lang_attr = lang_html[lang]
        title = lang_titles[lang]
        desc = lang_descs[lang]
        
        palace_lines = palace_lines_hant if lang == "zh-Hant" else (palace_lines_hans if lang == "zh-Hans" else palace_lines_en)
        palace_text = "\n".join(palace_lines)
        
        reading_html = reading_section(reading, lang) if lang == "zh-Hant" else ""
        if not reading_html and lang == "zh-Hans":
            reading_html = reading_section(reading, lang)
        if not reading_html and lang == "en":
            short = reading[:300] if reading else ""
            reading_html = f'<p style="font-size:13px;color:#7a6a9a;line-height:1.9;margin-bottom:10px">{short}...</p>' if short else ""
        
        # Build the main star link to z/ page
        star_file = f"{_slug(minggong_star)}-minggong.html" if minggong_star else ""
        star_link = f"/z/{star_file}" if star_file else ""
        
        # Different visual template
        if template_ver == 0:
            # template A: reading first
            extra_style = ""
        elif template_ver == 1:
            # template B: palace list first
            extra_style = ""
        else:
            # template C: balanced
            extra_style = ""
        
        # Page sections order based on template
        reading_first = template_ver == 0
        palace_first = template_ver == 1
        
        content_before_reading = ""
        content_after_reading = ""
        
        # Build HTML
        page_html = f"""<!DOCTYPE html>
<html lang="{lang_attr}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="https://ziweiapi.site{base_url}{suffix}.html">
{hreflang_links(lang)}
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="https://ziweiapi.site{base_url}{suffix}.html">
<meta property="og:image" content="https://ziweiapi.site/og-image.jpg">
<meta name="twitter:card" content="summary_large_image">
<meta name="robots" content="index, follow">
<script type="application/ld+json">{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "{title}",
  "description": "{desc}",
  "url": "https://ziweiapi.site{base_url}{suffix}.html"
}}</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Noto Sans SC',sans-serif;background:#0f0b14;color:#d0c8e0;line-height:1.6}}
.container{{max-width:720px;margin:0 auto;padding:24px 20px}}
h1{{font-size:22px;font-weight:700;color:#e8c8a0;margin-bottom:4px;text-align:center;letter-spacing:1px}}
.meta{{font-size:11px;color:#5a4a6a;text-align:center;margin-bottom:16px}}
.lang-switcher{{display:flex;gap:6px;justify-content:center;margin-bottom:16px}}
.lang-btn{{background:transparent;border:1px solid rgba(232,215,0,.12);color:#7a6a9a;padding:4px 12px;border-radius:6px;font-size:11px;cursor:pointer;letter-spacing:1px;text-decoration:none}}
.lang-btn.active{{background:rgba(232,160,64,.12);border-color:#e8a040;color:#e8b860;font-weight:600}}
.section{{margin:18px 0;padding:14px;background:linear-gradient(135deg,rgba(26,22,36,.93),rgba(18,14,28,.93));border:1px solid rgba(160,120,200,.08);border-radius:10px}}
.section h2{{font-size:14px;color:#c8a8e0;margin-bottom:8px;font-weight:600;letter-spacing:.5px}}
.section p{{font-size:13px;color:#7a6a9a;line-height:1.8}}
.star-list{{font-size:12px;color:#7a6a9a;line-height:2}}
.star-list span{{color:#c8a8e0}}
.cta-box{{text-align:center;margin:24px 0;padding:18px;background:linear-gradient(135deg,rgba(123,104,238,.06),rgba(90,74,205,.06));border:1px solid rgba(123,104,238,.12);border-radius:12px}}
.cta-box p{{font-size:12px;color:#7a6a9a;margin-bottom:10px}}
.cta-btn{{display:inline-block;padding:10px 24px;background:linear-gradient(135deg,#7b68ee,#5a4acd);color:#fff;border-radius:10px;text-decoration:none;font-size:13px;font-weight:600;letter-spacing:1px}}
.cta-btn:hover{{opacity:.9}}
.footer{{text-align:center;padding:20px 0;color:#3a2a5a;font-size:11px;border-top:1px solid rgba(160,120,200,.06);margin-top:20px}}
.footer a{{color:#5a4a7a;text-decoration:none;margin:0 4px}}
.footer a:hover{{color:#7b68ee}}
@media(max-width:600px){{h1{{font-size:20px}}.container{{padding:16px 14px}}}}
</style>
</head>
<body>
<div class="container">
  <div class="lang-switcher">
{lang_switcher(lang)}
  </div>

  <h1>{title}</h1>
  <div class="meta">{wuxingju} · {bazi}</div>

  <div class="section" style="border-color:rgba(232,160,64,.15)">
    <p style="font-size:13px;color:#c0b0d0;line-height:1.9;font-style:italic;text-align:center;margin:0">{angle}{focus_desc}</p>
  </div>

  <div class="section">
    <h2>{"命盤概覽" if lang != "en" else "Chart Overview"}</h2>
    <div class="star-list">
"""
        
        if lang == "en":
            page_html += palace_text
        else:
            page_html += palace_text
        
        page_html += f"""
    </div>
  </div>

  {f'''
  <div class="section">
    <h2>{"命盤解讀" if lang != "en" else "Chart Reading"}</h2>
    {reading_html}
  </div>
  ''' if reading_html else ''}

  <div class="section">
    <h2>{"運勢提示" if lang != "en" else "Fortune Tips"}</h2>
    <p>✨ {lucky}</p>
    <p>💡 {attention}</p>
    <p>💼 {career}</p>
  </div>

  {f'''
  <div class="section">
    <h2>{"城市命理解讀" if lang != "en" else "City Fortune Guide"}</h2>
    <p>{city_hant if lang == "zh-Hant" else (city_hans if lang == "zh-Hans" else city_en)}</p>
    <p style="font-size:11px;color:#5a4a6a;margin-top:6px"><a href="/z/{city_slug}.html" style="color:#7a6a9a;text-decoration:none;border-bottom:1px solid rgba(160,120,200,.15)">{"了解更多關於" if lang != "en" else "Learn more about "}{city}{"的紫微命理" if lang != "en" else ""}</a></p>
  </div>
  ''' if city and city_slug else ''}

  <div class="cta-box">
    <p>{"想知道自己的命盤？輸入出生資訊，30秒免費排盤。" if lang != "en" else "Want to see your own chart? Enter your birth info — 30 seconds, completely free."}</p>
    <a href="/" class="cta-btn">{"🆓 免費排盤" if lang != "en" else "🆓 Free Chart Reading"}</a>
  </div>

  {f'''
  <div class="section" style="font-size:12px;color:#5a4a6a">
    <p>{"相關命盤" if lang != "en" else "Related Charts"}: <a href="{star_link}" style="color:#7a6a9a">{lang_titles[lang]}</a></p>
  </div>
  ''' if star_link else ''}

  <div class="footer">
    <a href="/">{"首頁" if lang != "en" else "Home"}</a> ·
    <a href="/articles/">{"文章" if lang != "en" else "Articles"}</a> ·
    <a href="/shop.html">{"購買Key" if lang != "en" else "Get API Key"}</a>
    <br><br>
    {"© 2026 ZiweiAPI — 免費紫微斗數排盤" if lang != "en" else "© 2026 ZiweiAPI — Free Chinese Astrology"}
  </div>
</div>
</body>
</html>"""
        
        # Write file
        CHARTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(page_html)
        
        url_path = f"{base_url}{suffix}.html"
        results.append((str(filepath), url_path))
    
    return results

def add_charts_to_sitemap(sitemap_path: str = "/home/ubuntu/ziwei-api/sitemap.xml"):
    """Scan charts/ directory and add any new URLs to sitemap"""
    import xml.etree.ElementTree as ET
    
    if not Path(sitemap_path).exists():
        return
    
    # Read existing sitemap
    tree = ET.parse(sitemap_path)
    root = tree.getroot()
    ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    
    existing = set()
    for url_elem in root.findall("ns:url", ns):
        loc = url_elem.find("ns:loc", ns)
        if loc is not None:
            existing.add(loc.text)
    
    # Find new chart pages
    new_urls = []
    for f in sorted(CHARTS_DIR.glob("*.html")):
        url = f"https://ziweiapi.site/charts/{f.name}"
        if url not in existing:
            new_urls.append(url)
    
    if not new_urls:
        return
    
    # Add to sitemap
    for url in new_urls:
        url_elem = ET.SubElement(root, "url")
        loc = ET.SubElement(url_elem, "loc")
        loc.text = url
        pri = ET.SubElement(url_elem, "priority")
        pri.text = "0.5"
    
    tree.write(sitemap_path, encoding="UTF-8", xml_declaration=True)
    return new_urls
