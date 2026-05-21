#!/usr/bin/env python3
"""Add missing init calls after PKGS definition in shop.html."""
with open('/home/ubuntu/ziwei-api/shop.html') as f:
    c = f.read()

# After PKGS definition, before function renderPricing, add init calls
old = "};\n\nfunction renderPricing(){"
new = """};

// ─── Init ──
(function(){
  renderPricing();
  loadStats();

  // Check URL params for existing key
  const params = new URLSearchParams(window.location.search);
  if (params.get('key')) {
    localStorage.setItem(URL_KEY_STORAGE, params.get('key'));
  }

  // Free trial check
  if (localStorage.getItem(FREE_STORAGE_KEY)) {
    const fb = document.querySelector('.free-banner');
    if (fb) {
      fb.innerHTML = '<div class="free-icon">\\U0001f512</div><h2>' + (lang==='zh'?'\\u5df2\\u4f53\\u9a8c\\u8fc7':'Already tried') + '</h2><p style="margin-bottom:0">' + (lang==='zh'?'\\u9009\\u4e2a\\u5957\\u9910\\u7ee7\\u7eed\\u89e3\\u9501\\u5427':'Choose a plan to continue') + '</p>';
      fb.onclick = null;
    }
  }
})();

function renderPricing(){"""

if old in c:
    c = c.replace(old, new)
    with open('/home/ubuntu/ziwei-api/shop.html', 'w') as f:
        f.write(c)
    print("Init calls added!")
else:
    print("Pattern not found!")
    # Show what's around that area
    idx = c.find("};")
    if idx > 0:
        print(f"Found '}};' at position {idx}, context:")
        print(c[idx:idx+150])
