#!/usr/bin/env python3
"""Fix lang auto-detect default for Chinese users."""
with open('/home/ubuntu/ziwei-api/index.html') as f:
    c = f.read()

old = "const targetLang = saved || (userLang === 'zh' ? 'zh' : 'en');"
new = "const targetLang = saved || (userLang.startsWith('zh') ? 'zh-Hans' : 'en');"

if old in c:
    c = c.replace(old, new)
    with open('/home/ubuntu/ziwei-api/index.html', 'w') as f:
        f.write(c)
    print("Fixed: zh default → zh-Hans")
else:
    print("Pattern not found!")
    # Try to find what's around
    import re
    m = re.search(r'targetLang.*saved.*userLang', c)
    if m:
        print(f"Found: {m.group()[:80]}")
