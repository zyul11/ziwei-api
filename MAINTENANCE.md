# 紫微斗数站 (ziweiapi.site) 维护文档

## 基本信息
- 服务端口：8119
- 启动方式：`python3 run.py`（uvicorn）
- 根目录：`/home/ubuntu/ziwei-api/`
- 管理后台：`/yuxiaolan.html`（密码：ziweisanniu）

## 常见操作

### 1. 添加文章到列表页
编辑 `articles/data.json`，在末尾追加一条：
```json
{
  "date": "2026-05-20",
  "file": "20260520-01",
  "zhHant": "繁體標題",
  "zhHans": "简体标题",
  "en": "English Title",
  "descZh": "繁體描述",
  "descEn": "English description"
}
```
⚠️ 不要编辑 `articles/index.html` 里的 JS 代码！数据已经分离到 JSON。

### 2. 重启服务
```bash
ps aux | grep uvicorn | grep -v grep | awk '{print $2}' | xargs kill
python3 /home/ubuntu/ziwei-api/run.py &
```

### 3. 生成城市命盘页面
```bash
python3 /home/ubuntu/ziwei-api/scripts/save_chart_page.py
```
生成后记得更新 sitemap：`python3 scripts/generate_sitemap_cn.py`

### 4. 生成SEO软文
- **英文软文**：cron 周一三五 06:00 自动生成，交付到微信
- **中文软文（命盘版）**：cron 周一三五 12:00 自动生成，交付到微信
- **热点文章**：cron 每天 02:00 自动生成（脚本：`ziwei_hotnews.py`）
- 手动跑：`python3 scripts/generate_en_article.py` 或 `python3 scripts/generate_cn_article.py`

### 5. 更新Sitemap
```bash
# 英文
python3 scripts/generate_sitemap_en.py
# 中文
python3 scripts/generate_sitemap_cn.py
# 全部（含工具站）
python3 scripts/generate_sitemap_all.py
```

### 6. 添加新工具到工具区
`articles/tools/` 目录下添加 html 文件，然后在 `articles/index.html` 的工具区添加链接。

### 7. 修改CSS样式
所有样式都在 `css/main.css`，不要写 inline style。改完后刷新即可（无需重启服务）。

### 8. 固定Cron任务清单
| 名称 | 时间 | 说明 |
|------|------|------|
| 热点文章 | 每天 02:00 | ziwei_hotnews.py |
| 英文软文 | 周一三五 06:00 | 生成+质量审核 |
| 中文软文 | 周一三五 12:00 | 命盘版 |
| 工具站文章 | 周二四 04:00 | textools.site |

## ⚠️ 切记
- **不要**在 `index.html` 或 `articles/index.html` 里硬编码数据
- **不要**写 inline CSS，统一改 `css/main.css`
- 重启服务后检查 `curl http://127.0.0.1:8119` 是否正常
- 文章内容中的单引号/撇号直接写，不需要转义——JSON 和反引号都天然支持
