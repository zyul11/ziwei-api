#!/usr/bin/env python3
"""Add missing </body></html> tags to shop.html."""
with open('/home/ubuntu/ziwei-api/shop.html') as f:
    c = f.read()

# Check if </body> exists
if '</body>' not in c:
    # Add it after </script>
    c = c.rstrip()  # remove trailing whitespace
    if c.endswith('</script>'):
        c += '\n\n<div id="jsErr" style="display:none;background:#300;color:#f88;padding:8px;font-size:12px;position:fixed;bottom:0;left:0;right:0;z-index:999"></div>\n</body>\n</html>\n'
    elif c.endswith('</html>'):
        pass  # already has it
    else:
        c += '\n</body>\n</html>\n'
    
    with open('/home/ubuntu/ziwei-api/shop.html', 'w') as f:
        f.write(c)
    print("Added </body></html>")
else:
    print("</body> already exists")

# Verify
with open('/home/ubuntu/ziwei-api/shop.html') as f:
    content = f.read()
last_100 = content[-100:]
print("Last chars:", repr(last_100))
print("</body>:", '</body>' in content)
print("</html>:", '</html>' in content)
