import re

with open('/home/ubuntu/ziwei-api/index.html', 'r') as f:
    text = f.read()

changes = 0

# 1. switchStyle: add formatReading()
old1 = """ac.innerHTML='<div class="rbox">'+d.data.reading+'</div>'+(isFree?'':stylePillsHTML(s,'paipan','switchStyle'));"""
new1 = """ac.innerHTML='<div class="rbox">'+formatReading(d.data.reading)+'</div>'+(isFree?'':stylePillsHTML(s,'paipan','switchStyle'));"""
if old1 in text:
    text = text.replace(old1, new1)
    changes += 1
    print("1. switchStyle: OK")
else:
    print("1. switchStyle: NOT FOUND")
    # try escaped
    if old1.replace('"', '\\"') in text:
        text = text.replace(old1.replace('"', '\\"'), new1.replace('"', '\\"'))
        changes += 1
        print("   (with escaped quotes)")

# 2. switchDailyStyle: add formatReading()
old2 = """dc.innerHTML=d.data.reading+stylePillsHTML(s,'daily','switchDailyStyle');"""
new2 = """dc.innerHTML=formatReading(d.data.reading)+stylePillsHTML(s,'daily','switchDailyStyle');"""
if old2 in text:
    text = text.replace(old2, new2)
    changes += 1
    print("2. switchDailyStyle: OK")
else:
    print("2. switchDailyStyle: NOT FOUND")

# 3. paipan mode: add formatReading()
old3 = """ac.innerHTML='<div class="rbox">'+dt.data.reading+'</div>'+(isFree?renderPremiumUnlock():stylePillsHTML(selStyle,'paipan','switchStyle'))"""
new3 = """ac.innerHTML='<div class="rbox">'+formatReading(dt.data.reading)+'</div>'+(isFree?renderPremiumUnlock():stylePillsHTML(selStyle,'paipan','switchStyle'))"""
if old3 in text:
    text = text.replace(old3, new3)
    changes += 1
    print("3. paipan mode: OK")
else:
    old3e = old3.replace('"', '\\"')
    new3e = new3.replace('"', '\\"')
    if old3e in text:
        text = text.replace(old3e, new3e)
        changes += 1
        print("3. paipan mode: OK (escaped)")
    else:
        print("3. paipan mode: NOT FOUND")

# 4. daxian mode: add formatReading()
old4 = """<div class="rbox">'+dt.data.reading+'</div></div>';"""
new4 = """<div class="rbox">'+formatReading(dt.data.reading)+'</div></div>';"""
if old4 in text:
    text = text.replace(old4, new4)
    changes += 1
    print("4. daxian mode: OK")
else:
    old4e = old4.replace('"', '\\"')
    new4e = new4.replace('"', '\\"')
    if old4e in text:
        text = text.replace(old4e, new4e)
        changes += 1
        print("4. daxian mode: OK (escaped)")
    else:
        print("4. daxian mode: NOT FOUND")

# 5. daily mode: add formatReading()
old5 = """let dc=d2.reading||'暂无解读';"""
new5 = """let dc=formatReading(d2.reading||'暂无解读');"""
if old5 in text:
    text = text.replace(old5, new5)
    changes += 1
    print("5. daily mode: OK")
else:
    print("5. daily mode: NOT FOUND")

with open('/home/ubuntu/ziwei-api/index.html', 'w') as f:
    f.write(text)
print(f"\nTotal changes: {changes}")
