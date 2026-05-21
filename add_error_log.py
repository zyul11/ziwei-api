#!/usr/bin/env python3
"""Add error logging to shop.html."""
with open('/home/ubuntu/ziwei-api/shop.html') as f:
    c = f.read()

# Add error handler after <script> tag
c = c.replace(
    '<script>',
    '<script>\nwindow.onerror = function(msg,url,line){document.getElementById("jsErr").textContent=msg+" at line "+line;};'
)

# Add error display div before </body>
c = c.replace(
    '</body>',
    '<div id="jsErr" style="display:none;background:#300;color:#f88;padding:8px;font-size:12px;position:fixed;bottom:0;left:0;right:0;z-index:999"></div>\n</body>'
)

with open('/home/ubuntu/ziwei-api/shop.html', 'w') as f:
    f.write(c)

print("Error logging added!")
