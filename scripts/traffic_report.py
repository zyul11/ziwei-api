#!/usr/bin/env python3
"""
流量日报 + SEO优化建议（v2 — 增强型爬虫检测）
每天分析nginx日志，输出结构化报告
"""
import os, re, json
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from pathlib import Path

LOG_DIR = "/var/log/nginx"
TODAY = datetime.now().strftime("%Y-%m-%d")

# ─── 已知扫描路径（访问这些的100%不是真人） ────────────────
SCANNER_PATHS = {
    '/.git/config', '/.env', '/wp-admin', '/wp-login.php',
    '/wp-admin/install.php', '/v1/admin/login', '/v1/config',
    '/v1/stats', '/admin', '/administrator', '/phpmyadmin',
    '/xmlrpc.php', '/wp-includes', '/wp-content',
    '/.aws/credentials', '/backup', '/config.json',
    '/server-status', '/cgi-bin', '/.svn',
}

# ─── UA关键词 → 确认bot ──────────────────────────────────
BOT_UA_KEYWORDS = [
    'bot', 'crawler', 'spider', 'scanner', 'scrapy',
    'ahrefs', 'semrush', 'moz', 'mj12bot', 'dotbot',
    'probe', 'nmap', 'zgrab', 'masscan',
    'python-requests', 'python-urllib', 'go-http-client',
    'java/', 'ruby', 'wget', 'curl',  # library defaults
    'googlebot', 'bingbot', 'baiduspider', 'yandexbot',
    'sogou', 'exabot', 'facebookexternalhit',
    'slurp', 'duckduckbot', 'archive.org_bot',
]

# ─── 疑似扫描的UA特征（伪装度低） ─────────────────────────
SCANNER_UA_PATTERNS = [
    r'^Mozilla/5\.0\s*$',                            # 空壳UA
    r'^Mozilla/5\.0 \([^)]*Windows[^)]*\) AppleWebKit',
    r'^Mozilla/5\.0 \([^)]*Linux[^)]*\) AppleWebKit',
    r'^Mozilla/5\.0\s*\(compatible',                  # 兼容模式
]

# ─── 内部/监控IP（不计入访客） ───────────────────────────
INTERNAL_IPS = {'127.0.0.1', '::1', 'localhost'}

# 已知监控服务（Cloudflare, UptimeRobot 等）
MONITOR_UA_KEYWORDS = ['uptimerobot', 'datadog', 'newrelic', 'pingdom']


def parse_log(path):
    """解析nginx access log，返回请求列表"""
    entries = []
    if not os.path.exists(path):
        return entries
    pattern = re.compile(
        r'(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+) [^"]+" (\d+) \d+ "([^"]*)" "([^"]*)"'
    )
    with open(path, 'r') as f:
        for line in f:
            m = pattern.match(line)
            if m:
                ip, ts, method, path, status, referer, ua = m.groups()
                # 提取host（从referer）
                host = re.search(r'https?://([^/]+)', referer or '')
                host = host.group(1) if host else ''
                entries.append({
                    'ip': ip, 'time': ts, 'method': method,
                    'path': path, 'status': int(status),
                    'referer': referer or '', 'ua': ua or '',
                    'host': host,
                })
    return entries


def classify_ip(entries_by_ip):
    """
    对每个IP做多维度分类。
    返回: {ip: 'human' | 'scanner' | 'monitor' | 'bot'}
    """
    ip_class = {}
    
    for ip, ip_entries in entries_by_ip.items():
        if ip in INTERNAL_IPS:
            ip_class[ip] = 'monitor'
            continue
        
        total = len(ip_entries)
        paths = set(e['path'] for e in ip_entries)
        uas = set(e['ua'].lower() for e in ip_entries)
        primary_ua = ip_entries[0]['ua'].lower()
        
        # 1. 监控服务
        if any(m in primary_ua for m in MONITOR_UA_KEYWORDS):
            ip_class[ip] = 'monitor'
            continue
        
        # 2. UA明确是bot
        if any(k in primary_ua for k in BOT_UA_KEYWORDS):
            ip_class[ip] = 'bot'
            continue
        
        # 3. 扫描路径命中
        scanner_hits = sum(1 for p in paths if any(sp in p for sp in SCANNER_PATHS))
        
        # 4. 行为特征
        unique_paths = len(paths)
        # 时间跨度（秒）
        try:
            times = []
            for e in ip_entries:
                dt = datetime.strptime(e['time'].split()[0], "%d/%b/%Y:%H:%M:%S")
                times.append(dt)
            times.sort()
            span_sec = (times[-1] - times[0]).total_seconds() if len(times) > 1 else 1
            rate = total / max(1, span_sec) * 60  # req/min
        except:
            rate = 0
            span_sec = 0
        
        # ── 分类决策 ──
        is_scanner = False
        
        # 命中扫描路径 >= 2 个
        if scanner_hits >= 2:
            is_scanner = True
        
        # 高频 + 多路径
        if rate > 30 and unique_paths >= 3:
            is_scanner = True
        
        # 低频但命中扫描路径（单次探测）
        if scanner_hits >= 1 and total <= 3:
            is_scanner = True
        
        # 高频单一页面（可能是真用户刷新）
        if rate >= 60 and unique_paths <= 2:
            # 检查是不是正常页面
            normal_paths = True
            for p in paths:
                if any(sp in p for sp in SCANNER_PATHS):
                    normal_paths = False
                    break
            if not normal_paths:
                is_scanner = True
            # 高频刷新正常页面 → 保持human（可能是真用户）
        
        if is_scanner:
            ip_class[ip] = 'scanner'
        else:
            ip_class[ip] = 'human'
    
    return ip_class


def analyze(entries, label):
    total = len(entries)
    
    # 按IP分组
    by_ip = defaultdict(list)
    for e in entries:
        by_ip[e['ip']].append(e)
    
    # 分类
    ip_class = classify_ip(by_ip)
    
    humans = [e for e in entries if ip_class.get(e['ip']) == 'human']
    bots = [e for e in entries if ip_class.get(e['ip']) == 'bot']
    scanners = [e for e in entries if ip_class.get(e['ip']) == 'scanner']
    monitors = [e for e in entries if ip_class.get(e['ip']) == 'monitor']
    
    human_ips = set(e['ip'] for e in humans)
    bot_ips = set(e['ip'] for e in bots)
    scanner_ips = set(e['ip'] for e in scanners)
    monitor_ips = set(e['ip'] for e in monitors)
    
    # Status codes (all traffic)
    status_2xx = sum(1 for e in entries if 200 <= e['status'] < 300)
    status_3xx = sum(1 for e in entries if 300 <= e['status'] < 400)
    status_4xx = sum(1 for e in entries if 400 <= e['status'] < 500)
    status_5xx = sum(1 for e in entries if 500 <= e['status'] < 600)
    
    # Most visited pages (filtered to likely-human)
    page_hits = Counter()
    suspicious_hits = Counter()
    for e in humans:
        p = e['path']
        is_suspicious = any(sp in p for sp in SCANNER_PATHS)
        if '.' not in p.split('/')[-1] or p.endswith('.html') or p.endswith('.htm'):
            if is_suspicious:
                suspicious_hits[p] += 1
            else:
                page_hits[p] += 1
    
    # ZIWEIAPI vs TEXTOOLS (human only)
    ziwei_humans = [e for e in humans if e['host'] in ('ziweiapi.site', 'www.ziweiapi.site', '')]
    textools_humans = [e for e in humans if e['host'] in ('textools.site', 'www.textools.site')]
    
    # 404 pages
    not_found = Counter()
    for e in entries:
        if e['status'] == 404:
            not_found[e['path']] += 1
    
    # Top bot agents
    top_bot_ua = Counter(
        e['ua'][:80] for e in bots + scanners
        if e['ua']
    )
    
    return {
        'label': label,
        'total_requests': total,
        'human_requests': len(humans),
        'bot_requests': len(bots),
        'scanner_requests': len(scanners),
        'monitor_requests': len(monitors),
        'human_ips': len(human_ips),
        'bot_ips': len(bot_ips),
        'scanner_ips': len(scanner_ips),
        'monitor_ips': len(monitor_ips),
        'status_2xx': status_2xx,
        'status_3xx': status_3xx,
        'status_4xx': status_4xx,
        'status_5xx': status_5xx,
        'top_pages': page_hits.most_common(10),
        'suspicious_pages': suspicious_hits.most_common(5),
        'top_bot_ua': top_bot_ua.most_common(3),
        'not_found': not_found.most_common(10),
        'ziwei_humans': len(ziwei_humans),
        'textools_humans': len(textools_humans),
    }


def get_log_timerange(entries):
    if not entries:
        return "? - ?"
    times = [e['time'] for e in entries]
    start = times[0].split()[0][:17]
    end = times[-1].split()[0][:17]
    return f"{start} → {end}"


def is_partial_day(entries):
    if not entries:
        return True
    times = []
    for e in entries:
        try:
            dt = datetime.strptime(e['time'].split()[0], "%d/%b/%Y:%H:%M:%S")
            times.append(dt)
        except:
            pass
    if not times:
        return True
    hours = (max(times) - min(times)).total_seconds() / 3600
    return hours < 18


def generate_report(today, yesterday, today_partial=False,
                    timerange_today="", timerange_yesterday=""):
    lines = []
    lines.append(f"📊 流量日报 · {TODAY}")
    lines.append("=" * 40)
    lines.append("")
    
    for data in [today, yesterday]:
        d = data
        label = d['label']
        timerange = timerange_today if label == '今日' else timerange_yesterday
        is_partial = today_partial if label == '今日' else False
        time_suffix = f" ({timerange})" if timerange else ""
        partial_note = " [部分时段]" if is_partial else ""
        lines.append(f"── {label}{time_suffix}{partial_note} ──")
        lines.append(f"  📍 总请求: {d['total_requests']}")
        lines.append(f"  👤 真人(预估): {d['human_requests']} ({d['human_ips']} IP)")
        lines.append(f"  🕵️ 扫描器: {d['scanner_requests']} ({d['scanner_ips']} IP)")
        lines.append(f"  🤖 爬虫: {d['bot_requests']} ({d['bot_ips']} IP)")
        lines.append(f"  📡 监控: {d['monitor_requests']} ({d['monitor_ips']} IP)")
        lines.append(f"  📈 状态码: 2xx={d['status_2xx']} 3xx={d['status_3xx']} 4xx={d['status_4xx']} 5xx={d['status_5xx']}")
        lines.append(f"  🌐 ziweiapi: {d['ziwei_humans']} req | textools: {d['textools_humans']} req")
        lines.append("")
        
        if d['top_pages']:
            lines.append("  热门页面（真人）:")
            for path, count in d['top_pages'][:5]:
                lines.append(f"    {count:>4}x  {path}")
            lines.append("")
        
        if d['suspicious_pages']:
            lines.append("  ⚠️ 疑似扫描的热门路径:")
            for path, count in d['suspicious_pages'][:3]:
                lines.append(f"    {count:>4}x  {path} ← 非真人，已被过滤")
            lines.append("")
        
        if d['not_found']:
            lines.append("  404 页面（需修复）:")
            for path, count in d['not_found'][:5]:
                lines.append(f"    {count:>4}x  {path}")
            lines.append("")
        
        if d['top_bot_ua']:
            lines.append("  爬虫/扫描器TOP3:")
            for ua, cnt in d['top_bot_ua'][:3]:
                short = ua[:50]
                lines.append(f"    {cnt:>4}x  {short}")
            lines.append("")
    
    # 趋势对比（用真实IP总和不含监控）
    today_total_real = today['human_ips'] + today['scanner_ips']
    yesterday_total_real = yesterday['human_ips'] + yesterday['scanner_ips']
    if today_total_real > 0 and yesterday_total_real > 0:
        lines.append(f"📈 用户对比: {today['human_ips']} 真人 vs {yesterday['human_ips']} 昨天")
        if today_partial:
            hourly_rate = today['human_ips'] / max(1, 9)
            projected = int(hourly_rate * 24)
            lines.append(f"⏰ 今日为部分时段，全天推算 ≈ {projected} 真人IP")
            lines.append(f"📊 预估趋势: {(projected - yesterday['human_ips'])/yesterday['human_ips']:+.1f}% vs 昨日")
        else:
            change = ((today['human_ips'] - yesterday['human_ips']) / yesterday['human_ips']) * 100
            lines.append(f"📊 环比: {change:+.1f}%")
        lines.append("")
    
    # SEO优化建议
    lines.append("🔍 SEO优化建议")
    lines.append("-" * 40)
    
    suggestions = []
    
    if today['not_found']:
        top_404 = today['not_found'][0][0]
        # 忽略已知扫描路径的404
        real_404 = [(p, c) for p, c in today['not_found'] 
                    if not any(sp in p for sp in SCANNER_PATHS)][:3]
        if real_404:
            for p, c in real_404:
                suggestions.append(f"  ⚠️ 404: {p} ({c}x) — 建议修复或301")
        else:
            suggestions.append(f"  ✅ 今日404均为扫描路径，无需处理")
    
    has_tools = any('/tools/' in p for p, _ in today['top_pages'])
    if not has_tools and today['ziwei_humans'] > 100:
        suggestions.append(f"  💡 工具页流量不足 → 首页/文章页已增加入口链接")
    
    if today['scanner_requests'] > today['human_requests'] * 2:
        suggestions.append(f"  🕵️ 扫描流量占比高 ({today['scanner_requests']}/{today['human_requests']})")
        suggestions.append(f"     → 可考虑 fail2ban 或 Cloudflare WAF 规则")
    
    if today['textools_humans'] < 30:
        suggestions.append(f"  📌 textools.site 真人仅 {today['textools_humans']} → 继续交叉推广")
    
    if today['status_5xx'] > 0:
        suggestions.append(f"  🔴 服务器错误 {today['status_5xx']} 次")
    
    suggestions.append(f"  🎯 首页日真人 ~{today['human_ips']}人，若转化率2%")
    suggestions.append(f"     → 日付费 ~{max(1, today['human_ips']//50)}人 | 月收 ~${max(9, today['human_ips']//2*9//100):.0f}")
    
    if not suggestions:
        suggestions.append("  ✅ 暂无异常")
    
    lines.extend(suggestions)
    lines.append("")
    lines.append("=" * 40)
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    return "\n".join(lines)


def main():
    today_log = os.path.join(LOG_DIR, "access.log")
    yesterday_log = os.path.join(LOG_DIR, "access.log.1")
    
    today_entries = parse_log(today_log)
    yesterday_entries = parse_log(yesterday_log)
    
    today_data = analyze(today_entries, "今日")
    yesterday_data = analyze(yesterday_entries, "昨日")
    
    today_timerange = get_log_timerange(today_entries)
    yesterday_timerange = get_log_timerange(yesterday_entries)
    today_partial = is_partial_day(today_entries)
    
    report = generate_report(today_data, yesterday_data,
                              today_partial, today_timerange, yesterday_timerange)
    print(report)
    
    out_dir = os.path.expanduser("~/ziwei-api/reports")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"traffic_{TODAY}.md")
    with open(path, 'w') as f:
        f.write(report)
    print(f"\n📁 日报已保存: {path}")


if __name__ == "__main__":
    main()
