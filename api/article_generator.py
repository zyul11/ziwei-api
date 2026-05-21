"""
SEO Article Generator — generates anonymized SEO case study articles from audit reports.
"""
import re
import os
import json
from datetime import date, datetime

ARTICLES_DIR = "/home/ubuntu/textools/articles/en/"
INDEX_PATH = "/home/ubuntu/textools/articles/index.html"
INDEX_DEV = "/home/ubuntu/textools/versions/dev/articles/index.html"
INDEX_V1 = "/home/ubuntu/textools/versions/v1/articles/index.html"

EXPLANATIONS = {
    "https": "Google publicly confirmed HTTPS as a ranking signal back in 2014. Every modern browser marks HTTP sites as 'Not Secure' with a visible warning. Visitors seeing that warning will bounce immediately — that's lost traffic, lost trust, and lost sales because of a free SSL certificate that takes 15 minutes to set up.",
    "h1": "The H1 is the most important HTML heading — it tells search engines and users exactly what the page is about. Without it, Google has to guess your page's primary topic. Imagine writing a book without a title.",
    "structured data": "Structured data powers rich results in Google — product price snippets, star ratings, FAQ accordions, breadcrumb trails. Without it, your site misses out on the visual enhancements that make listings stand out in search results.",
    "json-ld": "Structured data powers rich results in Google — product price snippets, star ratings, FAQ accordions, breadcrumb trails. Without it, your site misses out on the visual enhancements that make listings stand out in search results.",
    "og:title": "When someone shares your site on social media — Facebook, Twitter/X, LinkedIn, WhatsApp — Open Graph tags control how the link renders. Without them, you get a bare URL with no image, no title, no description. Every social share becomes a wasted opportunity.",
    "twitter:card": "Twitter Card tags control how your content appears when shared on X/Twitter. Without them, your tweets look broken and unattractive, dramatically reducing click-through rates.",
    "og:image": "Social sharing requires OG image tags to display a preview thumbnail. Without it, shared links look broken and unappealing.",
    "meta description": "The meta description is what shows up under your page title in Google search results. A missing or weak description means Google will auto-generate one from random page content — often poorly.",
    "sitemap": "A sitemap is literally a map you give to Google saying 'here are all my pages, please index them.' Without it, Google has to discover pages by following links — and on a small site, that means many pages stay in indexing purgatory forever.",
    "robots.txt": "The robots.txt file tells search engine crawlers which pages they can and cannot access. Without it (or a broken one), crawlers may miss important pages or waste crawl budget on irrelevant ones.",
    "canonical": "Without a canonical tag, duplicate content issues can tank your rankings. Google might split ranking signals across multiple versions of the same page, or worse — index a scraper site as the original.",
    "viewport": "Without a proper viewport meta tag, your site doesn't scale correctly on mobile devices. With mobile-first indexing, this directly impacts search rankings.",
    "image alt": "Alt text helps Google understand image content, improves accessibility for visually impaired users, and can drive traffic through Google Image Search. Every missing alt attribute is a missed SEO opportunity.",
    "content length": "Search engines favor comprehensive content. Thin content pages struggle to rank for competitive keywords because they don't provide enough depth to satisfy the searcher's intent.",
    "content-length": "Search engines favor comprehensive content. Thin content pages struggle to rank for competitive keywords because they don't provide enough depth to satisfy the searcher's intent.",
    "word count": "Search engines favor comprehensive content. Thin content pages struggle to rank for competitive keywords because they don't provide enough depth to satisfy the searcher's intent.",
    "lang attribute": "The HTML lang attribute tells search engines what language your content is in. Without it, search engines must guess, which can lead to incorrect language targeting and reduced rankings.",
    "html lang": "The HTML lang attribute tells search engines what language your content is in. Without it, search engines must guess, which can lead to incorrect language targeting and reduced rankings.",
    "internal links": "Internal links help Google discover and understand the structure of your site. Pages without internal links are orphans — hard for search engines to find and even harder to rank.",
    "favicon": "A favicon appears in every browser tab. While not a direct ranking factor, it impacts brand trust and click-through rates in search results.",
    "analytics": "Without Google Analytics, you're flying blind — you can't track visitor behavior, traffic sources, or conversions. You also can't detect AI bot visits."
}

# Issue name → severity mapping for common keywords
SEVERITY_WORDS = {
    "https": "high", "ssl": "high", "h1": "high", "title tag": "high",
    "structured data": "high", "json-ld": "high", "schema": "high",
    "og:": "high", "twitter": "high", "open graph": "high",
    "sitemap": "high", "robots.txt": "high", "canonical": "high",
    "meta description": "medium", "image alt": "medium", "alt text": "medium",
    "content": "medium", "word count": "medium", "viewport": "medium",
    "lang": "medium", "favicon": "low", "internal link": "medium",
    "analytics": "medium", "heading": "high", "h2": "medium"
}


def _count_severities(issues):
    high = med = low = 0
    for iss in issues:
        sev = iss.get("severity", "low") or "low"
        if sev == "high":
            high += 1
        elif sev == "medium":
            med += 1
        else:
            low += 1
    return high, med, low


def _pick_title(score):
    if score < 30:
        return f"This Website Scored {score}/100 on SEO — Here's Every Mistake It Made"
    elif score < 60:
        return f"This Website Scored {score}/100 on SEO — The Problems Behind the Numbers"
    elif score < 80:
        return f"This Website Scored {score}/100 on SEO — What's Working and What's Not"
    else:
        return f"This Website Scored {score}/100 on SEO — Here's What They're Doing Right"


def _pick_description(score, issues, checks_passed, total_checks):
    if score < 30:
        top = issues[0]["title"][:40] if issues else "multiple issues"
        return f"We audited a real website. Score: {score}/100. {len(issues)} issues. {top} — here's exactly what went wrong and how to fix it."
    elif score < 60:
        return f"A real website scored {score}/100 on our SEO audit. {checks_passed}/{total_checks} checks passed with {len(issues)} issues identified. Full breakdown inside."
    elif score < 80:
        return f"This website scored {score}/100 on our SEO audit. {checks_passed}/{total_checks} checks passed. See what's working and what needs attention."
    else:
        return f"Impressive: this website scored {score}/100 on our SEO audit. {checks_passed}/{total_checks} checks passed. Here's what they're doing right."


def _find_key_issues(issues):
    """Group issues by high/medium and return structured data."""
    high_issues = [i for i in issues if i.get("severity") == "high"]
    med_issues = [i for i in issues if i.get("severity") == "medium"]
    low_issues = [i for i in issues if i.get("severity") == "low"]

    def _explain(title):
        title_lower = title.lower()
        # Check for keyword matches
        for kw, explanation in EXPLANATIONS.items():
            if kw in title_lower:
                return explanation
        # Generic fallback
        return f"This issue directly impacts your site's search rankings and user experience. Fixing it should be a priority for better SEO performance."

    return high_issues[:6], med_issues[:3], low_issues[:5], _explain


def _make_slug(text):
    """Create a URL slug from article title."""
    s = text.lower().replace("'s", "s").replace("'", "")
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = s.strip('-')
    return s[:60]


def generate_article(domain, report):
    """Generate an anonymized SEO case study article from audit results.

    Returns dict with 'url', 'path', 'slug', 'title' on success,
    or 'error' on failure.
    """
    score = report.get("score", 0)
    issues = report.get("issues", [])
    checks = report.get("checks", [])
    summary = report.get("summary", {})

    checks_passed = summary.get("passed", 0)
    total_checks = summary.get("total_checks", len(checks))
    warnings = summary.get("warnings", 0)
    failed = summary.get("failed", 0)

    high_c, med_c, low_c = _count_severities(issues)

    title = _pick_title(score)
    description = _pick_description(score, issues, checks_passed, total_checks)

    today = date.today()
    date_str = today.strftime("%Y-%m-%d")
    date_display = today.strftime("%B %d, %Y")
    slug = _make_slug(title[:40])
    filename = f"{date_str}-seo-case-study-{slug}.html"
    filepath = os.path.join(ARTICLES_DIR, filename)
    article_url = f"https://textools.site/articles/en/{filename}"

    # Build checks section
    checks_rows = ""
    for c in checks:
        icon = "✅" if c.get("pass") else ("⚠️" if c.get("warn") else "❌")
        status = "PASS" if c.get("pass") else ("WARN" if c.get("warn") else "FAIL")
        checks_rows += f'<li>{icon} <strong>{c.get("name", "")}</strong> — {status}</li>\n'

    # Build issues section
    high_issues, med_issues, low_issues, explain = _find_key_issues(issues)
    issues_html = ""

    if high_issues:
        issues_html += '<h2>🔴 Critical Issues</h2>\n'
        for iss in high_issues:
            t = iss.get("title", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            exp = explain(t)
            issues_html += f'<h3>{t}</h3>\n<p><strong>Why it matters:</strong> {exp}</p>\n'

    if med_issues:
        issues_html += '<h2>⚠️ Major Issues</h2>\n'
        for iss in med_issues:
            t = iss.get("title", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            sug = iss.get("suggestion", "") or ""
            if sug:
                sug = sug[:150].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                issues_html += f'<h3>{t}</h3>\n<p>{sug}</p>\n'
            else:
                exp = explain(t)
                issues_html += f'<h3>{t}</h3>\n<p><strong>Why it matters:</strong> {exp}</p>\n'

    if low_issues:
        issues_html += '<h2>🟡 Informational Issues</h2>\n<ul>\n'
        for iss in low_issues:
            t = iss.get("title", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            issues_html += f'<li><strong>{t}</strong></li>\n'
        issues_html += '</ul>\n'

    # Bottom summary
    if score < 60:
        big_picture = (
            f"A score of {score} out of 100 isn't just 'bad SEO' — it means the site is "
            f"functioning without the basic plumbing that modern search engines expect. "
            f"Every page is harder to find. Every link share looks broken. "
            f"Every potential customer who lands on the site has a reason to leave."
        )
    elif score < 80:
        big_picture = (
            f"A score of {score} out of 100 shows there's solid groundwork, but important "
            f"improvements are still needed. With some targeted fixes, this site could be "
            f"well on its way to the 80+ range."
        )
    else:
        big_picture = (
            f"A score of {score} out of 100 is impressive. This site has the fundamentals "
            f"down and is well-positioned for search visibility."
        )

    # Build article HTML
    article_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} | Textools Blog</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{article_url}">
<link rel="alternate" hreflang="en" href="{article_url}">
<link rel="alternate" hreflang="x-default" href="{article_url}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{article_url}">
<meta property="og:type" content="article">
<meta property="og:image" content="https://textools.site/og-tools.svg">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="https://textools.site/og-tools.svg">
<meta name="robots" content="index, follow">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "{title}",
  "description": "{description}",
  "datePublished": "{date_str}T00:00:00+00:00",
  "author": {{"@type": "Organization", "name": "Textools"}},
  "publisher": {{"@type": "Organization", "name": "Textools"}}
}}
</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#1e1e2e;color:#cdd6f4;line-height:1.8;max-width:700px;margin:0 auto;padding:30px 20px}}
.nav{{font-size:12px;color:#585b70;margin-bottom:30px}}
.nav a{{color:#89b4fa;text-decoration:none;margin-right:12px}}
h1{{font-size:22px;color:#cdd6f4;margin-bottom:8px;line-height:1.4}}
.date{{font-size:11px;color:#585b70;margin-bottom:20px}}
h2{{font-size:16px;color:#cdd6f4;margin:24px 0 10px}}
h3{{font-size:14px;color:#a6adc8;margin:20px 0 8px}}
p{{font-size:14px;color:#a6adc8;margin-bottom:14px;line-height:1.8}}
ul{{font-size:14px;color:#a6adc8;margin-bottom:14px;padding-left:20px}}
li{{margin-bottom:6px}}
.highlight{{background:rgba(250,179,135,.08);border-left:3px solid #fab387;padding:12px 16px;margin:16px 0;border-radius:0 6px 6px 0;font-size:13px;color:#cdd6f4}}
.tag{{display:inline-block;font-size:10px;padding:2px 8px;border-radius:4px;background:rgba(243,139,168,.1);color:#f38ba8;margin-bottom:4px}}
.cta{{margin:24px 0;text-align:center}}
.cta a{{display:inline-block;padding:10px 24px;border-radius:8px;background:linear-gradient(135deg,#89b4fa,#b4befe);color:#11111b;font-size:13px;font-weight:700;text-decoration:none}}
.cta .small{{display:block;font-size:10px;color:#585b70;margin-top:6px}}
.footer{{font-size:11px;color:#45475a;text-align:center;margin-top:40px;border-top:1px solid rgba(137,180,250,.06);padding-top:20px}}
.footer a{{color:#585b70;text-decoration:none;margin:0 6px}}
</style>
</head>
<body>

<div class="nav"><a href="https://textools.site/">← Text Tools</a> <a href="https://textools.site/articles/">Blog</a> <a href="https://seo.textools.site/">Free SEO Audit</a></div>

<h1>{title}</h1>
<div class="date">📅 {date_display} · <span class="tag">Case Study</span> <span class="tag">SEO Audit</span></div>

<p>We ran a free SEO audit on a website. The result was telling:</p>

<div class="highlight">
<strong>Score: {score} / 100</strong><br>
{checks_passed} of {total_checks} checks passed · {len(issues)} issues found<br>
{high_c} critical · {med_c} major · {low_c} informational
</div>

<p>Here's the full breakdown of what was found, and how <strong>any</strong> site in a similar situation can fix it.</p>

{issues_html}

<h2>The Bigger Picture: A {score}/100 Score</h2>
<p>{big_picture}</p>
<p>But here's the good news: fixing these issues doesn't require a full-time SEO specialist or a $5,000 audit. It requires a checklist and the discipline to work through it, one issue at a time.</p>

<h2>How to Check Your Own Site's Score</h2>
<p>If any of the above sounded uncomfortably familiar, grab your URL and run a full SEO audit. It's free, takes 30 seconds, and checks all {total_checks} points including:</p>
<ul>
<li>✅ HTTPS / SSL status</li>
<li>✅ H1 tags and heading hierarchy</li>
<li>✅ JSON-LD structured data</li>
<li>✅ OG / Twitter meta tags</li>
<li>✅ Sitemap and robots.txt</li>
<li>✅ Canonical URLs</li>
<li>✅ Image alt text coverage</li>
<li>✅ Page content length</li>
<li>✅ GA4 / AI Visibility detection</li>
<li>✅ And more technical checks</li>
</ul>

<div class="cta">
<a href="https://seo.textools.site/">🔍 Run Your Free SEO Audit Now</a>
<span class="small">No sign-up required · Results in ~30 seconds · {total_checks}-point check</span>
</div>

<div class="footer">
<a href="https://textools.site/">Text Tools</a> ·
<a href="https://seo.textools.site/">Free SEO Audit</a> ·
<a href="https://textools.site/articles/">Blog</a>
</div>

</body>
</html>"""

    # Write article
    os.makedirs(ARTICLES_DIR, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(article_html)

    return {
        "success": True,
        "url": article_url,
        "path": filepath,
        "filename": filename,
        "title": title
    }


def _update_index(index_path, filename, title):
    """Add new article link to an index HTML at the TOP of the list."""
    if not os.path.exists(index_path):
        return False

    # Build the new list item HTML
    today = date.today()
    date_str = today.strftime("%Y-%m-%d")
    new_item = f"""<li>
<a href="/articles/en/{filename}">
<span class="cat-label">🔍 Case Study</span> {title}
<div class="date">{date_str}</div>
</a>
</li>
<li>"""

    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the first <li> in the article list and insert before it
    # The article list section starts with <!-- or <ul class="article-list">
    markers = ['<ul class="article-list">\n<li>', '<ul class="article-list">\n  <li>', '<ul class="article-list">\n<li']
    found = False
    for marker in markers:
        idx = content.find(marker)
        if idx != -1:
            insert_pos = idx + len(marker)
            new_content = content[:insert_pos] + "\n" + new_item + content[insert_pos:]
            found = True
            break
    if not found:
        return False

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return True


def add_article_to_indexes(filename, title):
    """Update all article indexes with the new article."""
    _update_index(INDEX_PATH, filename, title)
    _update_index(INDEX_DEV, filename, title)
    _update_index(INDEX_V1, filename, title)
