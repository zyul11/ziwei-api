#!/usr/bin/env python3
"""Fix modalPkg unit text to be language-aware."""
with open('/home/ubuntu/ziwei-api/shop.html') as f:
    c = f.read()

old = "document.getElementById('modalPkg').textContent = `${p.name} · ${p.quota}次`;"
new = "document.getElementById('modalPkg').textContent = `${p.name} · ${p.quota} ${lang==='zh'?'次':'calls'}`;"

if old in c:
    c = c.replace(old, new)
    with open('/home/ubuntu/ziwei-api/shop.html', 'w') as f:
        f.write(c)
    print("Fixed!")
else:
    print("Pattern not found!")
    # Let's see what's there
    import re
    m = re.search(r'modalPkg.*textContent.*quota', c)
    if m:
        print(f"Found: {m.group()[:80]}")
