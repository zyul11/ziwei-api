#!/usr/bin/env python3
"""Fix PKGS section in shop.html."""
with open('/home/ubuntu/ziwei-api/shop.html') as f:
    content = f.read()

# Find the PKGS object
marker = 'const PKGS = {'
idx = content.find(marker)
if idx == -1:
    print("ERROR: cannot find PKGS marker")
    exit(1)

# Find the actual end - look for "};" followed by newline and not inside template
end = content.find('\n};\n', idx)
# But there are "};" inside template strings too. Let me find the one after enterprise
enterprise_marker = "enterprise"
e_idx = content.find(enterprise_marker, idx)
if e_idx > 0:
    end = content.find('\n};', e_idx)
    if end == -1:
        end = content.find('};', e_idx)

# If end is after others, find it differently
# Let me just splice at the enterprise line end + 1
lines = content.split('\n')
new_lines = []
in_pkgs = False
for line in lines:
    if 'const PKGS = {' in line:
        in_pkgs = True
        new_lines.append(line)
        new_lines.append("  starter:{icon:'\U0001f31f',name:'Starter',price:9.9,quota:10,color:'#b08860',popular:true,per:'$0.99/call',value:'Perfect to get started'},")
        new_lines.append("  standard:{icon:'\U0001f680',name:'Standard',price:29.9,quota:50,color:'#a0a060',popular:false,per:'$0.60/call',value:'Best value'},")
        new_lines.append("  pro:{icon:'\u2728',name:'Pro',price:99,quota:500,color:'#e8a040',popular:false,per:'$0.20/call',value:'Most popular'},")
        new_lines.append("  business:{icon:'\U0001f4bc',name:'Business',price:49,quota:2000,color:'#d08060',popular:false,per:'$0.025/call',value:'Monthly subscription'},")
        new_lines.append("  enterprise:{icon:'\U0001f451',name:'Enterprise',price:999,quota:99999,color:'#c06040',popular:false,per:'',value:'White-label / reseller'},")
        new_lines.append("};")
        continue
    if in_pkgs and (line.strip().startswith('};') or ':name:' in line or ':price:' in line or ':quota:' in line or ':icon:' in line):
        continue  # skip old PKGS content
    if in_pkgs:
        in_pkgs = False  # reached end of PKGS section
    
    new_lines.append(line)

content = '\n'.join(new_lines)

with open('/home/ubuntu/ziwei-api/shop.html', 'w') as f:
    f.write(content)

print("PKGS section fixed!")

# Verify
with open('/home/ubuntu/ziwei-api/shop.html') as f:
    for i, line in enumerate(f, 1):
        if 380 < i < 390:
            print(f'{i}: {line.rstrip()}')
