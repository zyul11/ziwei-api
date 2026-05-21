#!/usr/bin/env python3
"""Fix line 584 and any remaining hardcoded Chinese units."""
with open('/home/ubuntu/ziwei-api/shop.html') as f:
    c = f.read()

c = c.replace(
    "document.getElementById('modalPkg').textContent = `${p.name} · ${p.quota}次`;",
    "document.getElementById('modalPkg').textContent = `${p.name} · ${p.quota} ${lang==='zh'?'次':'calls'}`;"
)

# Fix the hardcoded 次 in 4th stat label
c = c.replace(
    "· ${p.quota}次</div>",
    "· ${p.quota} ${lang==='zh'?'次':'calls'}</div>"
)

with open('/home/ubuntu/ziwei-api/shop.html', 'w') as f:
    f.write(c)

print("Unit fix applied!")

with open('/home/ubuntu/ziwei-api/shop.html') as f:
    for i, line in enumerate(f, 1):
        if 583 < i < 586:
            print(f'{i}: {line.rstrip()}')
