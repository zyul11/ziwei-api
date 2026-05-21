#!/usr/bin/env python3
"""Clean fix for shop.html PKGS section."""
with open('/home/ubuntu/ziwei-api/shop.html') as f:
    c = f.read()

p_start = c.index('const PKGS = {')
p_end = c.index('};', p_start) + 2

pkg_block = """const PKGS = {
  starter:{icon:'\U0001f31f',name:'Starter',price:9.9,quota:10,color:'#b08860',popular:true,per:'$0.99/call',value:'Perfect to get started'},
  standard:{icon:'\U0001f680',name:'Standard',price:29.9,quota:50,color:'#a0a060',popular:false,per:'$0.60/call',value:'Best value'},
  pro:{icon:'\u2728',name:'Pro',price:99,quota:500,color:'#e8a040',popular:false,per:'$0.20/call',value:'Most popular'},
  business:{icon:'\U0001f4bc',name:'Business',price:49,quota:2000,color:'#d08060',popular:false,per:'$0.025/call',value:'Monthly subscription'},
  enterprise:{icon:'\U0001f451',name:'Enterprise',price:999,quota:99999,color:'#c06040',popular:false,per:'',value:'White-label / reseller'},
};
"""

c = c[:p_start] + pkg_block + c[p_end:]

# Clean up duplicates from failed fixes
seen_first = False
lines = c.split('\n')
result = []
for line in lines:
    if 'const PKGS = {' in line:
        if seen_first:
            continue
        seen_first = True
        result.append(line)
        continue
    if seen_first:
        if line.strip() == '};':
            seen_first = False
            continue
        if 'name:' in line and 'icon:' in line:
            continue
    result.append(line)

c = '\n'.join(result)

with open('/home/ubuntu/ziwei-api/shop.html', 'w') as f:
    f.write(c)

# Show result
for i, line in enumerate(c.split('\n'), 1):
    if 379 < i < 392:
        print(f'{i}: {line}')
