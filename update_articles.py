"""批量更新文章页样式"""
import re, os, glob

ARTICLES_DIR = '/home/ubuntu/ziwei-api/articles'
ALREADY_DONE = {'20260519-01.html'}

# 新样式（压缩最小化）
NEW_STYLE = """
body{font-family:'Noto Sans SC','PingFang TC','Microsoft JhengHei',sans-serif;background:#0a0a14;color:#c8c0d8;min-height:100vh;line-height:1.8;overflow-x:hidden}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(1px 1px at 10%20%,rgba(255,255,255,.3),transparent),radial-gradient(1px 1px at 30%60%,rgba(255,255,255,.2),transparent),radial-gradient(1px 1px at 50%10%,rgba(255,255,255,.25),transparent),radial-gradient(1.5px 1.5px at 85%65%,rgba(255,215,0,.2),transparent),radial-gradient(1.5px 1.5px at 25%55%,rgba(255,215,0,.2),transparent);pointer-events:none;z-index:0}
body::after{content:'';position:fixed;top:50%;left:50%;width:700px;height:700px;margin:-350px 0 0 -350px;border-radius:50%;background:conic-gradient(from 0deg,transparent,rgba(255,215,0,.04),transparent 30%,rgba(255,215,0,.02),transparent 60%,rgba(255,215,0,.03),transparent);pointer-events:none;z-index:0;animation:bgSpin 40s linear infinite}
@keyframes bgSpin{from{transform:translate(-50%,-50%) rotate(0deg)}to{transform:translate(-50%,-50%) rotate(360deg)}}
.top-nav{position:sticky;top:0;z-index:100;display:flex;align-items:center;justify-content:space-between;padding:10px 20px;background:rgba(10,10,20,.92);backdrop-filter:blur(12px);border-bottom:1px solid rgba(232,160,64,.1)}
.top-nav .logo{font-size:14px;font-weight:700;color:#e8b860;text-decoration:none;letter-spacing:1px}
.top-nav .logo span{color:#9a7850;font-weight:400}
.top-nav .nav-links{display:flex;gap:10px}
.top-nav .nav-links a{padding:4px 12px;font-size:11px;color:#8a7050;text-decoration:none;border:1px solid #3a2a1e;border-radius:6px;transition:all .2s}
.top-nav .nav-links a:hover{color:#e8b860;border-color:#e8a040}
.container{max-width:800px;margin:0 auto;padding:20px;position:relative;z-index:1}
.article-header{text-align:center;padding:24px 0 16px}
.article-header .meta{font-size:10px;color:#5a4a6a;letter-spacing:1px;margin-bottom:6px}
.article-header .meta .tag{display:inline-block;background:rgba(255,215,0,.1);border:1px solid rgba(255,215,0,.12);border-radius:4px;padding:1px 8px;font-size:9px;color:#d4a030;margin-left:4px}
.article-header h1{font-size:24px;font-weight:800;letter-spacing:2px;line-height:1.4;background:linear-gradient(135deg,#ffe066,#ffd700,#b8860b);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.article-body{font-size:15px;color:#c8c0d8;padding:0 4px}
.article-body h2{font-size:18px;font-weight:700;color:#ffd700;margin:28px 0 12px;padding-bottom:8px;border-bottom:1px solid rgba(255,215,0,.08);letter-spacing:1.5px}
.article-body h3{font-size:16px;font-weight:600;color:#ffe066;margin:20px 0 10px;letter-spacing:1px}
.article-body p{margin-bottom:16px}
.article-body a{color:#ffd700;text-decoration:none;border-bottom:1px solid rgba(255,215,0,.2);transition:all .2s}
.article-body a:hover{color:#ffe066;border-color:#ffd700}
.lang-switcher{display:flex;gap:6px;justify-content:center;margin-bottom:14px}
.lang-btn{background:transparent;border:1px solid #3a2a1e;color:#7a6a9a;padding:4px 12px;border-radius:6px;font-size:11px;cursor:pointer;letter-spacing:1px;transition:all .2s;text-decoration:none;font-family:inherit}
.lang-btn:hover{border-color:#e8a040;color:#e8a040}
.lang-btn.active{background:rgba(232,160,64,.12);border-color:#e8a040;color:#e8b860;font-weight:600}
.cta-section{margin-top:32px;padding:28px 24px;border-radius:16px;background:linear-gradient(135deg,rgba(26,26,46,.95),rgba(16,16,30,.95));border:1px solid rgba(255,215,0,.15);text-align:center}
.cta-section .cta-title{font-size:18px;font-weight:700;color:#ffe066;margin-bottom:10px;letter-spacing:1.5px}
.cta-section p{font-size:13px;color:#8a7a9a;margin-bottom:14px!important}
.cta-section .cta-btn{display:inline-block;padding:10px 26px;margin:4px 6px;border-radius:10px;text-decoration:none;font-size:13px;font-weight:600;letter-spacing:1px;transition:all .3s}
.cta-section .cta-btn.primary{background:linear-gradient(135deg,#e8a040,#d08020);color:#0a0a14;box-shadow:0 4px 16px rgba(232,160,64,.25)}
.cta-section .cta-btn.primary:hover{transform:translateY(-2px);box-shadow:0 6px 24px rgba(232,160,64,.4)}
.cta-section .cta-btn.secondary{background:transparent;color:#e8b860;border:1px solid rgba(232,160,64,.25)}
.cta-section .cta-btn.secondary:hover{border-color:#e8a040;background:rgba(232,160,64,.08)}
.footer{text-align:center;padding:30px 0;color:#3a2a3a;font-size:11px;letter-spacing:.5px;line-height:1.8}
.footer a{color:#5a4a5a;text-decoration:none}
.footer a:hover{color:#8a7050}
.progress-bar{position:fixed;top:0;left:0;height:2px;z-index:200;background:linear-gradient(90deg,#e8a040,#ffd700);transition:width .1s linear;width:0}
@media(max-width:600px){.article-header h1{font-size:20px}.article-body{font-size:14px}.top-nav{padding:8px 14px}.top-nav .nav-links a{font-size:10px;padding:3px 8px}}
"""

# HTML to inject after </head>
NAV_HTML = '''<div class="progress-bar" id="progressBar"></div>
<div class="top-nav">
  <a href="/" class="logo">✦ 紫微斗數 <span>| 文章</span></a>
  <div class="nav-links">
    <a href="/articles/">📚 全部文章</a>
    <a href="/">🏠 首頁</a>
  </div>
</div>'''

# Progress JS to add before </html>
PROGRESS_JS = '''<script>
window.addEventListener('scroll', function(){
  var h = document.documentElement.scrollHeight - window.innerHeight;
  var p = (window.scrollY / h) * 100;
  document.getElementById('progressBar').style.width = p + '%';
});
</script>'''

files = sorted(glob.glob(os.path.join(ARTICLES_DIR, '*.html')))
count = 0

for fpath in files:
    fname = os.path.basename(fpath)
    if fname == 'index.html' or fname in ALREADY_DONE:
        continue
    
    with open(fpath, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # 1. Replace the <style> block
    html = re.sub(
        r'<style>\*\{margin:0;padding:0;box-sizing:border-box\}.*?</style>',
        f'<style>\n{NEW_STYLE.strip()}\n</style>',
        html,
        flags=re.DOTALL
    )
    
    # 2. Add nav + progress bar after </head>
    html = html.replace('</head>\n<body>', f'</head>\n<body>\n{NAV_HTML}')
    
    # 3. Add progress JS before </html>
    html = html.replace('</body>\n</html>', f'</body>\n{PROGRESS_JS}\n</html>')
    
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(html)
    
    count += 1
    print(f'✅ {fname}')

print(f'\n总共更新 {count} 篇文章')
