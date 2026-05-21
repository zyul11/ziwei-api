#!/usr/bin/env python3
"""Fix the broken end of shop.html by appending missing functions and closing tags."""
with open('/home/ubuntu/ziwei-api/shop.html') as f:
    content = f.read()

# Find the last line and check what's missing
# The file currently ends with truncated code
# Let's find the proper place to insert — after the last complete line of code

# Find the last occurrence of the Self-Executing function
marker = "// Check for successful return from payment provider"
idx = content.find(marker)
if idx < 0:
    print("ERROR: cannot find payment return check")
    exit(1)

# Find the end of the IIFE
# The file content after the IIFE should be the truncated queryKey
truncated = content[idx:]

# Find where the IIFE ends (should be })(); )
iife_end = truncated.find("})();")
if iife_end > 0:
    end_pos = idx + iife_end + 6
    content = content[:end_pos]
else:
    print("ERROR: cannot find IIFE end")
    exit(1)

# Now add missing functions and closing tags
content += r'''

function closeModal(){
  document.getElementById('modal').classList.remove('show');
}
function openFreeDemo(){
  window.open(API + '/', '_blank');
}
function goToTest(){
  window.open(API + '/', '_blank');
}
function showKeyResult(key, pkgName, balance){
  document.getElementById('keyResult').classList.add('show');
  document.getElementById('payStep').style.display = 'none';
  document.getElementById('keyDisplay').textContent = key;
  document.getElementById('resultPkg').textContent = pkgName;
  document.getElementById('resultBalance').textContent = balance;
}
function copyKey(){
  var key = document.getElementById('keyDisplay').textContent;
  navigator.clipboard.writeText(key).then(function() {
    document.querySelector('.copy-btn').textContent = '\u2705 Copied!';
    setTimeout(function() {
      document.querySelector('.copy-btn').textContent = '\U0001f4cb Copy Key';
    }, 2000);
  });
}
function toggleFaq(el){
  el.classList.toggle('open');
}
async function queryKey(){
  var input = document.getElementById('qKeyInput');
  var key = input.value.trim();
  if(!key) return;
  var res = await fetch(API + '/v1/key/balance', {
    headers: {'Authorization': 'Bearer ' + key}
  });
  var d = await res.json();
  var result = document.getElementById('qResult');
  result.style.display = 'block';
  if(d.success){
    result.innerHTML = '<div style="color:#f0e0c8;font-size:14px">' + (lang==='zh'?'\u4f59\u989d':'Balance') + ': ' + d.balance + ' ' + (lang==='zh'?'\u6b21':'calls') + '</div>';
  } else {
    result.innerHTML = '<div style="color:#dd8866">' + (lang==='zh'?'Key\u65e0\u6548':'Invalid key') + '</div>';
  }
}
</script>
</html>
'''

with open('/home/ubuntu/ziwei-api/shop.html', 'w') as f:
    f.write(content)

# Verify
with open('/home/ubuntu/ziwei-api/shop.html') as f:
    lines = f.readlines()

print(f"File now has {len(lines)} lines")
print("Last 10 lines:")
for line in lines[-10:]:
    print(repr(line))

# Check for required elements
all_text = ''.join(lines)
for fn in ['closeModal', 'openFreeDemo', 'goToTest', 'showKeyResult', 'copyKey', 'toggleFaq', 'queryKey']:
    if fn in all_text:
        print(f"  ✅ {fn}")
    else:
        print(f"  ❌ {fn}")

for tag in ['</script>', '</html>']:
    if tag in all_text:
        print(f"  ✅ {tag}")
    else:
        print(f"  ❌ {tag}")
