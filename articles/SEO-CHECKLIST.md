# 紫微斗數文章 SEO 標準清單

每篇新文章發布前，請逐項檢查。生成器（`generate_article.py`、`generate_cn_article.py`、`generate_en_article.py`）已自動覆蓋①②③④，手寫文章需人工確認。

## ✅ 強制項（少一項都不及格）

| # | 項目 | 檢查方法 | 備註 |
|---|------|---------|------|
| ① | **`<title>` 標題** | 瀏覽器標籤欄可讀 | 含核心關鍵詞，≤60字 |
| ② | **`<meta name="description">`** | 頁面源碼搜 "description" | 120-160字，含關鍵詞+CTA |
| ③ | **OG 標籤** | 源碼搜 `og:title`、`og:description`、`og:url`、`og:image` | Facebook/WeChat/LINE 分享卡片必備 |
| ④ | **Twitter Card** | 源碼搜 `twitter:card` | 要設 `summary_large_image` |
| ⑤ | **Canonical URL** | 源碼搜 `rel="canonical"` | 避免重複內容扣分 |
| ⑥ | **JSON-LD Article Schema** | 源碼搜 `application/ld+json` | Google 結構化數據可獲 rich snippet |

## ⭐ 推薦項（提升排名）

| # | 項目 | 說明 |
|---|------|------|
| ⑦ | **`<meta name="keywords">`** | 5-10個相關關鍵詞，逗號分隔 |
| ⑧ | **`<meta name="robots" content="index, follow">`** | 確保搜索引擎收錄 |
| ⑨ | **H1 標題** | 頁面只有一個 H1，與 title 內容一致 |
| ⑩ | **H2 分節** | 文章有 2-3 個 H2 小標題，含長尾關鍵詞 |
| ⑪ | **內鏈** | 文末引導至 `/index.html`（免費排盤）和 `/shop.html`（購買Key） |
| ⑫ | **多語言 hreflang** | 繁/簡/EN 三版互相 link |

## 🛠️ 快速驗證

發布後用 SEO 檢測工具驗證：
```bash
curl "https://ziweiapi.site/v1/seo-audit?url=https://ziweiapi.site/articles/你的文章.html"
```
目標：**綜合評分 ≥ 85/100**

## 📝 生成器狀態（已自動化的部分）

| 生成器 | ①②③④⑤⑥ | ⑦⑧ | ⑨⑩⑪⑫ |
|--------|---------|-----|--------|
| `generate_article.py` | ✅ 自動 | ✅ 自動 | 需人工 |
| `generate_cn_article.py` | ✅ 自動 | ✅ 自動 | 需人工 |
| `generate_en_article.py` | ✅ 自動 | ✅ 自動 | 需人工 |
| `template.html` | ✅ 含模板 | ✅ 含模板 | 需填變量 |
