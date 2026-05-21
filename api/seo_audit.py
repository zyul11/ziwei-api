"""
SEO Audit Engine — crawls a URL and runs configurable SEO checks
Rules loaded from seo-rules.json (generated from knowledge base)
"""
import re
import json
import os
import requests
from pathlib import Path
from urllib.parse import urlparse, urljoin
from html.parser import HTMLParser


class SEOAuditor(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.title = ''
        self.meta_desc = ''
        self.meta_keywords = ''
        self.h1_tags = []
        self.h2_tags = []
        self.h3_tags = []
        self.images = []  # (src, alt)
        self.links = []  # (href, rel, is_internal)
        self.og_tags = {}
        self.twitter_tags = {}
        self.hreflang_tags = []
        self.canonical = ''
        self.robots_meta = ''
        self.charset = ''
        self.viewport = ''
        self.json_ld_blocks = []
        self.in_script = False
        self.in_title = False
        self.title_buffer = ''
        self.words = []
        self.in_body = False
        self.body_text = ''
        self._current_tag = ''
        self._schema_found = False

    def handle_starttag(self, tag, attrs):
        self._current_tag = tag
        attrs_dict = dict(attrs)

        if tag == 'title':
            self.in_title = True
            self.title_buffer = ''
        elif tag == 'meta':
            name = attrs_dict.get('name', '').lower()
            prop = attrs_dict.get('property', '').lower()
            content = attrs_dict.get('content', '')
            charset_val = attrs_dict.get('charset', '')
            if name == 'description':
                self.meta_desc = content
            elif name == 'keywords':
                self.meta_keywords = content
            elif name == 'robots':
                self.robots_meta = content
            elif name == 'viewport':
                self.viewport = content
            elif charset_val:
                self.charset = charset_val
            elif prop == 'og:title': self.og_tags['title'] = content
            elif prop == 'og:description': self.og_tags['description'] = content
            elif prop == 'og:image': self.og_tags['image'] = content
            elif prop == 'og:url': self.og_tags['url'] = content
            elif prop == 'og:type': self.og_tags['type'] = content
            elif name == 'twitter:card': self.twitter_tags['card'] = content
            elif name == 'twitter:title': self.twitter_tags['title'] = content
            elif name == 'twitter:description': self.twitter_tags['description'] = content
        elif tag == 'img':
            src = attrs_dict.get('src', '')
            alt = attrs_dict.get('alt', '')
            self.images.append((src, alt))
        elif tag == 'a':
            href = attrs_dict.get('href', '')
            rel = attrs_dict.get('rel', '')
            if href and not href.startswith('#') and not href.startswith('javascript:'):
                parsed = urlparse(href)
                base_parsed = urlparse(self.base_url)
                is_internal = not parsed.netloc or parsed.netloc == base_parsed.netloc
                self.links.append((href, rel, is_internal))
        elif tag == 'link':
            rel = attrs_dict.get('rel', '')
            href = attrs_dict.get('href', '')
            if rel == 'canonical':
                self.canonical = attrs_dict.get('href', '')
            elif rel == 'alternate':
                hreflang = attrs_dict.get('hreflang', '')
                if hreflang:
                    self.hreflang_tags.append((hreflang, href))
        elif tag == 'script':
            if attrs_dict.get('type') == 'application/ld+json':
                self._schema_found = True
                self.in_script = True
        elif tag in ('h1', 'h2', 'h3'):
            pass

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
            self.title = self.title_buffer.strip()
        elif tag == 'script':
            self.in_script = False
        self._current_tag = ''

    def handle_data(self, data):
        if self.in_title:
            self.title_buffer += data
        elif self.in_script:
            if self._schema_found:
                self.json_ld_blocks.append(data.strip())
                self._schema_found = False
        elif self._current_tag == 'h1':
            self.h1_tags.append(data.strip())
        elif self._current_tag == 'h2':
            self.h2_tags.append(data.strip())
        elif self._current_tag == 'h3':
            self.h3_tags.append(data.strip())


def load_rules():
    """Load SEO rules from seo-rules.json"""
    rules_path = Path(__file__).resolve().parent / "seo-rules.json"
    if not rules_path.exists():
        return None
    try:
        return json.loads(rules_path.read_text(encoding="utf-8"))
    except:
        return None


# ── Check functions ──

def check_https(parser, rule, final_url, **kw):
    https_pass = final_url.startswith('https://')
    return {
        'pass': https_pass, 'warn': False,
        'note': None if https_pass else 'Install SSL certificate and redirect HTTP → HTTPS'
    }

def check_viewport(parser, rule, **kw):
    ok = bool(parser.viewport)
    return {'pass': ok, 'warn': False, 'note': None if ok else 'Add <meta name="viewport">'}

def check_charset(parser, rule, **kw):
    ok = bool(parser.charset) or bool(kw.get('html', '').lower().find('charset=utf-8') >= 0)
    return {'pass': ok, 'warn': False, 'note': None if ok else 'Add <meta charset="UTF-8">'}

def check_canonical(parser, rule, **kw):
    ok = bool(parser.canonical)
    return {'pass': ok, 'warn': False, 'note': None if ok else 'Add <link rel="canonical">'}

def check_title(parser, rule, **kw):
    title = parser.title
    ok = bool(title)
    warn = False
    note = None
    if ok:
        threshold = rule.get('threshold', {})
        min_l = threshold.get('min_length', 0)
        max_l = threshold.get('max_length', 200)
        if len(title) < min_l or len(title) > max_l:
            warn = True
            note = f'{len(title)} chars. Optimal: {min_l}-{max_l}'
    else:
        note = 'No title tag found'
    return {'pass': ok, 'warn': warn, 'note': note}

def check_meta_desc(parser, rule, **kw):
    desc = parser.meta_desc
    ok = bool(desc)
    warn = False
    note = None
    if ok:
        threshold = rule.get('threshold', {})
        min_l = threshold.get('min_length', 0)
        max_l = threshold.get('max_length', 200)
        if len(desc) < min_l or len(desc) > max_l:
            warn = True
            note = f'{len(desc)} chars. Optimal: {min_l}-{max_l}'
    else:
        note = 'No meta description found'
    return {'pass': ok, 'warn': warn, 'note': note}

def check_h1(parser, rule, **kw):
    count = len(parser.h1_tags)
    if count == 0:
        return {'pass': False, 'warn': False, 'note': 'No H1 tag'}
    elif count > 1:
        return {'pass': False, 'warn': True, 'note': f'{count} H1 tags — use exactly 1'}
    return {'pass': True, 'warn': False, 'note': None}

def check_heading_hierarchy(parser, rule, **kw):
    h1 = len(parser.h1_tags)
    h2 = len(parser.h2_tags)
    ok = h1 >= 1 and h2 > 0
    return {'pass': ok, 'warn': h1 == 0 or h2 == 0, 'note': None if ok else f'H1:{h1}, H2:{h2}'}

def check_image_alt(parser, rule, **kw):
    imgs = parser.images
    missing = sum(1 for _, alt in imgs if not alt)
    total = len(imgs)
    ok = missing == 0
    return {'pass': ok, 'warn': missing > 0, 'note': None if ok else f'{missing}/{total} missing alt text'}

def check_jsonld(parser, rule, **kw):
    count = len(parser.json_ld_blocks)
    ok = count > 0
    return {'pass': ok, 'warn': False, 'note': None if ok else 'No structured data found'}

def check_og_tags(parser, rule, **kw):
    count = len(parser.og_tags)
    threshold = rule.get('threshold', {}).get('min_og_count', 3)
    ok = count >= threshold
    return {'pass': ok, 'warn': count > 0 and count < threshold, 'note': None if ok else f'{count} OG tags (need ≥{threshold})'}

def check_twitter_card(parser, rule, **kw):
    count = len(parser.twitter_tags)
    threshold = rule.get('threshold', {}).get('min_twitter_count', 2)
    ok = count >= threshold
    return {'pass': ok, 'warn': count > 0 and count < threshold, 'note': None if ok else f'{count} Twitter tags (need ≥{threshold})'}

def check_robots_meta(parser, rule, **kw):
    robots = parser.robots_meta.lower()
    noindex = 'noindex' in robots
    ok = not noindex
    return {'pass': ok, 'warn': False, 'note': f'Has noindex' if noindex else None}

def check_robots_txt(parser, rule, domain, **kw):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; SEOAuditBot/1.0)',
            'Accept': 'text/plain'
        }
        r = requests.get(f'https://{domain}/robots.txt', timeout=5, headers=headers)
        ok = r.status_code == 200 and len(r.text) > 0
        return {'pass': ok, 'warn': False, 'note': None if ok else 'robots.txt not found'}
    except:
        return {'pass': False, 'warn': False, 'note': 'robots.txt unreachable'}

def check_sitemap(parser, rule, domain, **kw):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; SEOAuditBot/1.0)'}
        for path in ['/sitemap.xml', '/sitemap_index.xml']:
            r = requests.get(f'https://{domain}{path}', timeout=5, headers=headers)
            if r.status_code == 200 and 'xml' in r.headers.get('Content-Type', ''):
                return {'pass': True, 'warn': False, 'note': None}
        return {'pass': False, 'warn': False, 'note': 'sitemap.xml not found'}
    except:
        return {'pass': False, 'warn': False, 'note': 'sitemap.xml unreachable'}

def check_internal_links(parser, rule, **kw):
    internal = sum(1 for _, _, is_int in parser.links if is_int)
    threshold = rule.get('threshold', {}).get('min_internal_links', 1)
    ok = internal >= threshold
    return {'pass': ok, 'warn': False, 'note': None if ok else f'{internal} internal links (need ≥{threshold})'}

def check_content_length(parser, rule, html, **kw):
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()
    word_count = len(text.split())
    threshold = rule.get('threshold', {}).get('min_words', 300)
    ok = word_count >= threshold
    return {
        'pass': ok,
        'warn': word_count >= threshold // 2 and word_count < threshold,
        'note': None if ok else f'~{word_count} words (need ≥{threshold})',
        'extra': {'word_count': word_count}
    }

def check_hreflang(parser, rule, **kw):
    """hreflang tags for multilingual sites"""
    tags = parser.hreflang_tags
    count = len(tags)
    ok = count >= 2  # at least 2 language variants
    return {
        'pass': ok,
        'warn': count > 0 and count < 2,
        'note': None if ok else f'{count} hreflang tags (need ≥2 for multi-lang site)'
    }

def check_faq_schema(parser, rule, **kw):
    """Check for FAQPage schema specifically"""
    for block in parser.json_ld_blocks:
        if '"FAQPage"' in block or '"FaqPage"' in block or 'faq' in block.lower():
            return {'pass': True, 'warn': False, 'note': None}
    return {'pass': False, 'warn': False, 'note': 'No FAQPage schema found'}

def check_dead_links(parser, rule, **kw):
    """Spot-check first 5 internal links"""
    internal_links = [href for href, _, is_int in parser.links if is_int][:5]
    dead = 0
    if internal_links:
        for href in internal_links:
            try:
                absolute = urljoin(parser.base_url, href)
                r = requests.head(absolute, timeout=3)
                if r.status_code >= 400:
                    dead += 1
            except:
                dead += 1
    ok = dead == 0
    return {'pass': ok, 'warn': dead > 0, 'note': None if ok else f'{dead} dead links in sample'}

def check_homepage_bloat(parser, rule, url, **kw):
    """Check if homepage has excessive content"""
    if urlparse(url).path not in ('', '/', '/index.html'):
        return {'pass': True, 'warn': False, 'note': 'Not homepage — skipped'}
    text = re.sub(r'<[^>]+>', ' ', kw.get('html', ''))
    text = re.sub(r'\s+', ' ', text).strip()
    wc = len(text.split())
    bloat = wc > 2000
    return {
        'pass': not bloat,
        'warn': wc > 1000 and wc <= 2000,
        'note': f'~{wc} words on homepage' if bloat else None
    }


# ── Industry-specific check functions ──

def check_tool_result_display(parser, rule, html, **kw):
    """Check tool page has input form and result area"""
    h = html.lower()
    has_input = bool(re.search(r'<input|<select|<textarea', html))
    has_button = bool(re.search(r'<button.*?>|type="submit"', html))
    has_result = bool(re.search(r'result|output|preview|display', h))
    score = sum([has_input, has_button, has_result])
    return {
        'pass': score >= 2,
        'warn': score == 1,
        'note': 'Missing: ' + ', '.join(
            [] if has_input else ['input form'] +
            [] if has_button else ['submit button'] +
            [] if has_result else ['result area']
        ) if score < 2 else None
    }


def check_tool_navigation(parser, rule, **kw):
    """Check tool site has proper navigation"""
    links = parser.links
    has_home_link = any('/' in href or 'home' in href.lower() for href, _, _ in links)
    nav_count = sum(1 for href, _, _ in links if not href.startswith('#') and not href.startswith('javascript:'))
    return {
        'pass': nav_count >= 5,
        'warn': nav_count >= 2 and nav_count < 5,
        'note': f'Only {nav_count} navigable links found' if nav_count < 5 else None
    }


def check_product_schema(parser, rule, **kw):
    """Check for Product schema with price and availability"""
    for block in parser.json_ld_blocks:
        if '"Product"' in block:
            has_price = '"price"' in block.lower() or '"priceCurrency"' in block
            has_avail = '"availability"' in block.lower()
            if has_price and has_avail:
                return {'pass': True, 'warn': False, 'note': None}
            elif has_price or has_avail:
                return {'pass': False, 'warn': True, 'note': 'Product schema found but missing price or availability'}
    return {'pass': False, 'warn': False, 'note': 'No Product schema found'}


# ── Site type detection ──

def detect_site_type(parser, html, url):
    """Auto-detect site type from content, URL, and schema"""
    signals = {'tool': 0, 'blog': 0, 'ecommerce': 0, 'saas': 0}

    url_lower = url.lower()
    html_lower = html.lower()

    # URL path signals
    if any(w in url_lower for w in ['/tool', '/tools', 'calculator', 'generator',
                                      'converter', 'checker', 'estimator', 'counter']):
        signals['tool'] += 3
    if any(w in url_lower for w in ['/blog', '/article', '/post', '/news', '/guide']):
        signals['blog'] += 3
    if any(w in url_lower for w in ['/shop', '/product', '/store', '/cart', '/checkout']):
        signals['ecommerce'] += 3
    if any(w in url_lower for w in ['/app', '/login', '/signup', '/dashboard']):
        signals['saas'] += 2

    # Schema signals
    for block in parser.json_ld_blocks:
        if '"Article"' in block or '"NewsArticle"' in block:
            signals['blog'] += 3
        if '"Product"' in block:
            signals['ecommerce'] += 3
        if '"SoftwareApplication"' in block or '"WebApplication"' in block:
            signals['saas'] += 2

    # Content signals
    if any(w in html_lower for w in ['calculate', 'generate', 'convert', 'check ',
                                       'analyze', 'estimate', 'compute', 'validate']):
        signals['tool'] += 2
    if any(w in html_lower for w in ['add to cart', 'buy now', 'shopping cart',
                                       'checkout', 'add to bag']):
        signals['ecommerce'] += 3
    if any(w in html_lower for w in ['sign up', 'get started', 'start free',
                                       'subscribe now', 'create account']):
        signals['saas'] += 2

    # Title signals
    title = (parser.title or '').lower()
    for t in ['calculator', 'generator', 'converter', 'checker', 'tool']:
        if t in title:
            signals['tool'] += 2
    for t in ['blog', 'article', 'guide', 'tutorial']:
        if t in title:
            signals['blog'] += 2

    best_type = max(signals, key=signals.get)
    best_score = signals[best_type]
    return best_type if best_score >= 2 else 'general'


# ── Back Button Hijacking check — from Google April 2026 spam policy ──

def check_back_button_hijacking(parser, rule, html, **kw):
    """Google April 2026: back button hijacking is now an explicit spam violation"""
    h = html.lower()

    # Check for suspicious patterns
    signs = []

    # 1. beforeunload handler (often used to trap users)
    if 'beforeunload' in h or 'onbeforeunload' in h:
        signs.append('beforeunload handler detected')

    # 2. Excessive history.pushState in loops
    pushstate_count = h.count('history.pushstate')
    if pushstate_count > 3:
        signs.append(f'excessive history.pushState ({pushstate_count}x)')

    # 3. history.replaceState with same URL (loop pattern)
    if 'history.pushstate' in h and h.count('addeventlistener') > 5:
        signs.append('pushState + multiple event listeners (loop risk)')

    # 4. Popup-on-unload pattern
    if 'window.open' in h and ('onunload' in h or 'onbeforeunload' in h):
        signs.append('window.open + unload handler (popup trap)')

    ok = len(signs) == 0
    return {
        'pass': ok,
        'warn': len(signs) > 0 and len(signs) <= 2,
        'note': '; '.join(signs) if signs else None
    }


# ── Rule ID → Check function mapping ──
CHECK_FUNCTIONS = {
    'https': check_https,
    'viewport': check_viewport,
    'charset': check_charset,
    'canonical': check_canonical,
    'title': check_title,
    'meta_desc': check_meta_desc,
    'h1_unique': check_h1,
    'heading_hierarchy': check_heading_hierarchy,
    'image_alt': check_image_alt,
    'jsonld': check_jsonld,
    'og_tags': check_og_tags,
    'twitter_card': check_twitter_card,
    'robots_meta': check_robots_meta,
    'robots_txt': check_robots_txt,
    'sitemap': check_sitemap,
    'internal_links': check_internal_links,
    'content_length': check_content_length,
    'hreflang': check_hreflang,
    'faq_schema': check_faq_schema,
    'dead_links': check_dead_links,
    'homepage_not_bloated': check_homepage_bloat,
    'tool_result_display': check_tool_result_display,
    'tool_navigation': check_tool_navigation,
    'product_schema': check_product_schema,
    'back_button_hijacking': check_back_button_hijacking,
}


def run_audit(url: str, timeout: int = 15) -> dict:
    """Run a full SEO audit on a URL using seo-rules.json configuration."""

    parsed = urlparse(url)
    if not parsed.scheme:
        url = 'https://' + url
        parsed = urlparse(url)

    domain = parsed.netloc

    result = {
        'url': url,
        'domain': domain,
        'score': 0,
        'checks': [],
        'issues': [],
        'summary': {},
        'rule_source': None
    }

    # Load rules
    rules_config = load_rules()
    if rules_config:
        result['rule_source'] = {
            'generated_at': rules_config['meta']['generated_at'],
            'source': rules_config['meta']['source'],
            'total_rules': rules_config['meta']['total_rules']
        }

    # Fetch the page
    try:
        import urllib.request, ssl
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.split(':')[0]

        # Map domains to local file paths (for sites hosted on same server)
        local_paths = {
            'ziweiapi.site': '/home/ubuntu/ziwei-api/index.html',
            'www.ziweiapi.site': '/home/ubuntu/ziwei-api/index.html',
            'game.ziweiapi.site': '/home/ubuntu/ziwei-games/index.html',
            'www.game.ziweiapi.site': '/home/ubuntu/ziwei-games/index.html',
            'seo.textools.site': '/home/ubuntu/seo-tools/index.html',
            'textools.site': '/home/ubuntu/textools/index.html',
        }
        if domain in local_paths and os.path.exists(local_paths[domain]):
            with open(local_paths[domain], 'r', encoding='utf-8') as f:
                html = f.read()
            final_url = url
            status = 200
        else:
            # For external sites, fetch via HTTPS
            req = urllib.request.Request(url,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; SEOAuditBot/1.0; +https://textools.site/seo-audit)',
                         'Accept': 'text/html,application/xhtml+xml',
                         'Accept-Language': 'en-US,en;q=0.5'})
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            resp = urllib.request.urlopen(req, context=ctx, timeout=timeout)
            html = resp.read().decode('utf-8', errors='replace')
            final_url = resp.geturl()
            status = resp.getcode()
    except Exception as e:
        return {'success': False, 'error': f'Cannot fetch URL: {str(e)}'}

    # Parse HTML
    parser = SEOAuditor(final_url)
    try:
        parser.feed(html)
    except:
        pass

    checks = []
    issues = []
    score = 100
    industry_info = None

    # ── Detect site type ──
    site_type = detect_site_type(parser, html, url)
    industry_config = (rules_config or {}).get('industry_overrides', {}).get(site_type, {})

    # Apply industry-based threshold overrides
    threshold_overrides = industry_config.get('override_thresholds', {})

    # Build rule list with industry-adjusted weights
    all_rules = []
    weight_adjustments = industry_config.get('weight_adjustments', {})

    if rules_config:
        for category in ['core', 'knowledge_high', 'knowledge_medium', 'experimental']:
            for rule in rules_config.get(category, []):
                if rule.get('scored', True) or category != 'experimental':
                    rule_copy = dict(rule)  # shallow copy so we can modify

                    # Apply industry weight adjustment
                    adj = weight_adjustments.get(rule_copy['id'], 0)
                    rule_copy['weight'] = max(0, rule_copy.get('weight', 5) + adj)

                    # Apply industry threshold override
                    if rule_copy['id'] in threshold_overrides:
                        ov = dict(rule_copy.get('threshold', {}))
                        ov.update(threshold_overrides[rule_copy['id']])
                        rule_copy['threshold'] = ov

                    all_rules.append((category, rule_copy))
    else:
        # Fallback: minimal hardcoded rules when no rules_config
        fallback_ids = ['https', 'viewport', 'title', 'meta_desc', 'h1_unique',
                        'jsonld', 'og_tags', 'robots_meta', 'content_length', 'canonical', 'sitemap']
        fallback_weights = {
            'https': 10, 'viewport': 8, 'title': 12, 'meta_desc': 10, 'h1_unique': 8,
            'jsonld': 8, 'og_tags': 5, 'robots_meta': 15, 'content_length': 8, 'canonical': 5, 'sitemap': 4
        }
        fallback_thresholds = {
            'title': {'min_length': 30, 'max_length': 60},
            'meta_desc': {'min_length': 100, 'max_length': 165},
            'content_length': {'min_words': 300},
            'og_tags': {'min_og_count': 3}
        }
        for fid in fallback_ids:
            all_rules.append(('high' if fid not in ('https','viewport','canonical') else 'core',
                              {'id': fid, 'name': fid.replace('_',' ').title(), 'weight': fallback_weights.get(fid, 5),
                               'threshold': fallback_thresholds.get(fid, {})}))

    # Add industry-specific extra rules
    industry_extra_rules = industry_config.get('extra_rules', [])
    for extra_rule in industry_extra_rules:
        all_rules.append(('knowledge_medium', extra_rule))

    # Build industry info for result
    industry_info = {
        'detected': site_type,
        'label': industry_config.get(f'label_{"en"}', site_type),
        'weight_adjustments': weight_adjustments,
        'extra_rules': [r['id'] for r in industry_extra_rules]
    }
    result['site_type'] = industry_info

    for category, rule in all_rules:
        rule_id = rule['id']
        check_fn = CHECK_FUNCTIONS.get(rule_id)
        if not check_fn:
            continue

        try:
            check_result = check_fn(
                parser, rule,
                url=url,
                domain=domain,
                html=html,
                final_url=final_url
            )
        except Exception as e:
            check_result = {'pass': False, 'warn': True, 'note': f'Check error: {str(e)}'}

        is_scored = category != 'experimental' and rule.get('scored', True)
        weight = rule.get('weight', 5)

        check_entry = {
            'rule_id': rule_id,
            'name': rule.get('name', rule_id),
            'pass': check_result['pass'],
            'warn': check_result.get('warn', False),
            'note': check_result.get('note'),
            'confidence': rule.get('confidence', 'unknown'),
            'category': category,
            'scored': is_scored,
            'source': rule.get('source', '')
        }
        checks.append(check_entry)

        # Generate issue if not passed
        if not check_result['pass'] and is_scored:
            severity = 'high' if weight >= 8 else ('medium' if weight >= 4 else 'low')
            suggestion = rule.get('suggestion', check_result.get('note', ''))
            if check_result.get('note'):
                suggestion = check_result['note']
            issues.append({
                'title': f"{rule.get('name', rule_id)}",
                'severity': severity,
                'weight': weight,
                'suggestion': suggestion[:200],
                'rule_id': rule_id,
                'confidence': rule.get('confidence', 'unknown')
            })
            score -= weight

        # Also warn-level issues (scored less)
        if check_result.get('warn') and is_scored:
            if not any(i.get('rule_id') == rule_id for i in issues):
                issues.append({
                    'title': f"{rule.get('name', rule_id)} (Warning)",
                    'severity': 'low',
                    'weight': max(1, weight // 3),
                    'suggestion': (check_result.get('note') or '')[:200],
                    'rule_id': rule_id,
                    'confidence': rule.get('confidence', 'unknown'),
                    'source': rule.get('source', '')
                })
                score -= max(1, weight // 3)

    # Normalize score
    score = max(0, min(100, score))

    # Sort issues by severity
    severity_order = {'high': 0, 'medium': 1, 'low': 2}
    issues.sort(key=lambda x: (severity_order.get(x.get('severity', 'low'), 99), -x.get('weight', 0)))

    word_count = 0
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()
    word_count = len(text.split())

    result['score'] = score
    result['checks'] = checks
    result['issues'] = issues[:25]
    result['success'] = True
    result['summary'] = {
        'total_checks': len(checks),
        'scored_checks': sum(1 for c in checks if c.get('scored', True)),
        'passed': sum(1 for c in checks if c['pass'] and c.get('scored', True)),
        'warnings': sum(1 for c in checks if c['warn'] and c.get('scored', True)),
        'failed': sum(1 for c in checks if not c['pass'] and not c['warn'] and c.get('scored', True)),
        'issues_count': len(issues),
        'word_count': word_count,
        'title': parser.title[:100] if parser.title else '(no title)',
        'description': parser.meta_desc[:150] if parser.meta_desc else '(no description)'
    }

    return result


if __name__ == '__main__':
    import sys, json
    url = sys.argv[1] if len(sys.argv) > 1 else 'https://example.com'
    result = run_audit(url)
    print(json.dumps(result, indent=2, ensure_ascii=False))
