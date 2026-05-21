#!/usr/bin/env python3
"""
哥飞SEO优化 - z/页面内链矩阵
在每个z/页面的</body>前添加"相關命盤"模块，链接到：
1. 同主星的其他宫位
2. 同宫位的其他主星
"""
import os
import re

Z_DIR = '/home/ubuntu/ziwei-api/z'

# 14主星
STARS = [
    'ziwei', 'tianji', 'taiyang', 'wuqu', 'tiantong', 'lianzhen',
    'tianfu', 'taiyin', 'tanlang', 'jumen', 'tianxiang', 'tianliang',
    'qisha', 'pojun'
]

STAR_NAMES = {
    'ziwei': '紫微', 'tianji': '天機', 'taiyang': '太陽', 'wuqu': '武曲',
    'tiantong': '天同', 'lianzhen': '廉貞', 'tianfu': '天府', 'taiyin': '太陰',
    'tanlang': '貪狼', 'jumen': '巨門', 'tianxiang': '天相', 'tianliang': '天梁',
    'qisha': '七殺', 'pojun': '破軍'
}

# 12宫位
PALACES = ['minggong', 'xiongdi', 'fuqi', 'zinv', 'caibo', 'jie',
           'qianyi', 'jiaoyou', 'guanlu', 'tianzhai', 'fude', 'fumu']

PALACE_NAMES = {
    'minggong': '命宮', 'xiongdi': '兄弟宮', 'fuqi': '夫妻宮', 'zinv': '子女宮',
    'caibo': '財帛宮', 'jie': '疾厄宮', 'qianyi': '遷移宮', 'jiaoyou': '交友宮',
    'guanlu': '官祿宮', 'tianzhai': '田宅宮', 'fude': '福德宮', 'fumu': '父母宮'
}

def generate_related_section(star, palace):
    """Generate the related panels HTML for a given star+palace page."""
    # Same star, other palaces
    same_star_links = []
    for p in PALACES:
        if p == palace:
            continue
        same_star_links.append(
            f'    <a href="{star}-{p}.html">{STAR_NAMES[star]}在{PALACE_NAMES[p]}</a>'
        )
    
    # Same palace, other stars
    same_palace_links = []
    for s in STARS:
        if s == star:
            continue
        same_palace_links.append(
            f'    <a href="{s}-{palace}.html">{STAR_NAMES[s]}在{PALACE_NAMES[palace]}</a>'
        )
    
    links_html = '\n'.join(same_star_links + ['    <span style="color:#4a3a5a;font-size:11px;padding:0 8px">│</span>'] + same_palace_links)
    
    return f'''  <div class="related-panels" style="margin-top:30px;padding-top:20px;border-top:1px solid rgba(232,160,64,.1)">
    <h3 style="font-size:14px;color:#e8b860;margin-bottom:10px">📌 相關命盤</h3>
    <div class="related-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:6px">
{links_html}
    </div>
  </div>
<style>
.related-grid a{{font-size:12px;color:#8a7a9a;text-decoration:none;padding:4px 8px;border-radius:4px;transition:all .2s;display:block}}
.related-grid a:hover{{color:#e8b860;background:rgba(232,160,64,.06)}}
</style>'''


def process_file(filepath, star, palace):
    """Process a single z/ page file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already has related-panels
    if 'related-panels' in content:
        print(f"  SKIP (already has related-panels): {filepath}")
        return False
    
    # Generate related section
    related_html = generate_related_section(star, palace)
    
    # Insert before </body>
    if '</body>' not in content:
        print(f"  ERROR (no </body>): {filepath}")
        return False
    
    content = content.replace('</body>', f'{related_html}\n</body>', 1)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  OK: {filepath}")
    return True


def main():
    print("=== Task 1: Adding internal link matrix to z/ pages ===\n")
    
    processed = 0
    skipped = 0
    errors = 0
    
    for star in STARS:
        for palace in PALACES:
            filename = f'{star}-{palace}.html'
            filepath = os.path.join(Z_DIR, filename)
            
            if not os.path.exists(filepath):
                print(f"  NOT FOUND: {filepath}")
                errors += 1
                continue
            
            if process_file(filepath, star, palace):
                processed += 1
            else:
                skipped += 1
    
    print(f"\nDone! Processed: {processed}, Skipped: {skipped}, Errors: {errors}")
    
    # Also handle special pages (city pages, hua-* pages) - skip those, they're not star+palace pages
    # But check if they exist and don't have the section
    print("\n--- Checking special pages ---")
    for fname in os.listdir(Z_DIR):
        if not fname.endswith('.html'):
            continue
        # Check if it's a star-palace page pattern
        parts = fname.replace('.html', '').split('-')
        if len(parts) == 2 and parts[0] in STARS and parts[1] in PALACES:
            continue  # already processed above
        # Skip non-star-palace pages
        fpath = os.path.join(Z_DIR, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        if 'related-panels' in content:
            print(f"  Has related (special page): {fname}")
    
    print("=== Task 1 complete ===\n")


if __name__ == '__main__':
    main()
