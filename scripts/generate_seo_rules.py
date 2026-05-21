#!/usr/bin/env python3
"""
从哥飞知识库提取SEO规则 → 生成 seo-rules.json

工作方式：
1. 读取 gefei-seo-deep-kb.md
2. 按章节提取关键规则建议
3. 与现有 seo-rules.json 合并（保留置信度等级）
4. 输出更新后的 JSON
5. 标记新发现的规则为 experimental，等确认后提升 confidence

用法：
  python scripts/generate_seo_rules.py
  输出：seo-rules.json
"""
import re
import json
from pathlib import Path
from datetime import date

BASE_DIR = Path(__file__).resolve().parent.parent
KB_PATH = Path("/home/ubuntu/knowledge/seo/gefei-seo-deep-kb.md")
RULES_PATH = BASE_DIR / "seo-rules.json"

# ── 章节关键词 → 规则映射（用于知识库变更检测） ──
SECTION_MAP = {
    "Title（最重要）": "title",
    "Description": "meta_desc",
    "H标签层级": "h1_unique,heading_hierarchy",
    "内链建设": "internal_links",
    "图片SEO": "image_alt,large_image",
    "Canonical标签": "canonical",
    "robots.txt": "robots_txt",
    "Schema结构化数据": "jsonld,faq_schema",
    "OG/Twitter Card": "og_tags,twitter_card",
    "完整技术SEO检查清单": "all_technical",
    "单页内容标准": "content_length",
    "首页膨胀降权": "homepage_not_bloated",
}

def extract_sections(md_text: str) -> dict:
    """按 ## 章节提取知识库内容"""
    sections = {}
    current_section = "_header"
    current_lines = []
    
    for line in md_text.splitlines():
        if line.startswith("## "):
            if current_lines:
                sections[current_section] = "\n".join(current_lines)
            current_section = line.strip("# ").strip()
            current_lines = []
        else:
            current_lines.append(line)
    
    if current_lines:
        sections[current_section] = "\n".join(current_lines)
    
    return sections

def check_kb_changes(kb_path: Path, sections: dict) -> list:
    """
    检查知识库是否有新章节或内容变更
    返回需要关注的规则ID列表
    """
    # Simple check: compare with last run's section hash
    hash_file = Path("/tmp/seo_rules_kb_hash.txt")
    content_hash = str(len(str(sections)))
    
    if hash_file.exists():
        prev_hash = hash_file.read_text().strip()
        if prev_hash == content_hash:
            return []  # No changes
    
    # Content changed — find affected rules
    affected = []
    for section_name, section_content in sections.items():
        for keyword, rule_ids in SECTION_MAP.items():
            if keyword in section_name or keyword in section_content:
                affected.extend(rule_ids.split(","))
    
    # Save current hash
    hash_file.write_text(content_hash)
    
    return list(set(affected))

def generate_rules():
    print("📖 读取知识库...")
    
    if not KB_PATH.exists():
        print(f"⚠️  知识库未找到: {KB_PATH}")
        print("使用现有 seo-rules.json（无更新）")
        return
    
    md_text = KB_PATH.read_text(encoding="utf-8")
    sections = extract_sections(md_text)
    
    print(f"📚 发现 {len(sections)} 个章节")
    
    # Check for changes
    changed_rules = check_kb_changes(KB_PATH, sections)
    if changed_rules:
        print(f"🔄 知识库有更新，影响规则: {', '.join(changed_rules)}")
    else:
        print("✅ 知识库无变化")
    
    # Load existing rules
    if RULES_PATH.exists():
        existing = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        print(f"📋 加载现有规则: {existing['meta']['total_rules']} 条")
    else:
        existing = {"meta": {"total_rules": 0}, "core": [], "knowledge_high": [], "knowledge_medium": [], "experimental": []}
        print("📋 新建规则文件")
    
    # Update metadata
    existing["meta"]["generated_at"] = date.today().isoformat()
    existing["meta"]["source"] = f"gefei-seo-deep-kb.md (v2.3)"
    existing["meta"]["total_rules"] = (
        len(existing.get("core", [])) +
        len(existing.get("knowledge_high", [])) +
        len(existing.get("knowledge_medium", [])) +
        len(existing.get("experimental", []))
    )
    
    # Mark affected rules as needing review
    for category in ["core", "knowledge_high", "knowledge_medium", "experimental"]:
        for rule in existing.get(category, []):
            if rule["id"] in changed_rules:
                rule["needs_review"] = True
    
    # Write rules
    RULES_PATH.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ 规则已更新: {RULES_PATH}")
    print(f"   Core: {len(existing.get('core', []))} 条")
    print(f"   High confidence: {len(existing.get('knowledge_high', []))} 条")
    print(f"   Medium confidence: {len(existing.get('knowledge_medium', []))} 条")
    print(f"   Experimental: {len(existing.get('experimental', []))} 条")
    
    if changed_rules:
        print(f"\n⚠️  以下规则标记为待审核: {', '.join(changed_rules)}")
        print("   请手动检查后移除 needs_review 标记")

if __name__ == "__main__":
    generate_rules()
