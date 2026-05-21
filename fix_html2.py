#!/usr/bin/env python3
"""Force-add closing HTML tags to shop.html."""
with open('/home/ubuntu/ziwei-api/shop.html') as f:
    c = f.read()

# Strip trailing whitespace
c = c.rstrip()

# Remove any partial closing tags at the end
while c.endswith('</html>'):
    c = c[:-7]
while c.endswith('</body>'):
    c = c[:-7]

# Find the last </script>
idx = c.rfind('</script>')
if idx > 0:
    before = c[:idx+9]  # up to and including </script>
    remainder = c[idx+9:]
    
    # Add error div + body + html close
    c = before + '\n\n<div id="jsErr" style="display:none;background:#300;color:#f88;padding:8px;font-size:12px;position:fixed;bottom:0;left:0;right:0;z-index:999"></div>\n</body>\n</html>'
    if remainder.strip():
        c += '\n' + remainder

with open('/home/ubuntu/ziwei-api/shop.html', 'w') as f:
    f.write(c)

# Verify
with open('/home/ubuntu/ziwei-api/shop.html') as f:
    content = f.read()
last = content[-120:]
print("Last 120 chars:", repr(last))
print("Has </body>:", '</body>' in last)
print("Has </html>:", '</html>' in last)
