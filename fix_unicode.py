#!/usr/bin/env python3
"""Fix literal Unicode escapes in shop.html."""
with open('/home/ubuntu/ziwei-api/shop.html') as f:
    c = f.read()

# The raw string in the previous script left literal \u4f59\u989d and \u6b21
# These need to be actual Unicode characters
c = c.replace('\\u4f59\\u989d', '\u4f59\u989d')  # 余额
c = c.replace('\\u6b21', '\u6b21')  # 次
c = c.replace('\\u65e0\\u6548', '\u65e0\u6548')  # 无效

with open('/home/ubuntu/ziwei-api/shop.html', 'w') as f:
    f.write(c)

# Verify
with open('/home/ubuntu/ziwei-api/shop.html') as f:
    content = f.read()

for text in ['\u4f59\u989d', '\u6b21', '\u65e0\u6548']:
    if text in content:
        print(f'  ✅ {text} found')
    else:
        print(f'  ❌ {text} missing')

print(f'File: {len(content)} bytes, {len(content.splitlines())} lines')
