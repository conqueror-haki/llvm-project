#!/usr/bin/env python3
"""Build the LLVM Learning Docs into a static HTML site."""

import json
import os
from pathlib import Path
from markdown_it import MarkdownIt
from jinja2 import Template
import shutil

ROOT = Path(__file__).parent
SRC = ROOT / "src"
BUILD = ROOT / "book"

NAV_STRUCTURE = {
    "01-getting-started": {
        "title": "卷一：速通环境",
        "files": {
            "setup.md": "1.1 环境搭建",
            "build-options.md": "1.2 构建选项详解",
            "first-compile.md": "1.3 第一次编译",
        }
    },
    "02-usage": {
        "title": "卷二：使用工具链",
        "files": {
            "toolchain-overview.md": "2.1 工具链全景",
            "clang.md": "2.2 Clang 编译器",
            "llvm-ir.md": "2.3 LLVM IR 深入",
            "opt.md": "2.4 opt 优化器",
            "llc.md": "2.5 llc 代码生成",
            "lld.md": "2.6 LLD 链接器",
            "utility-tools.md": "2.7 辅助工具",
        }
    },
    "03-source-architecture": {
        "title": "卷三：源码架构",
        "files": {
            "directory-map.md": "3.1 代码目录地图",
            "core-datastructures.md": "3.2 核心数据结构",
            "pass-system.md": "3.3 Pass 体系",
            "clang-frontend.md": "3.4 Clang 前端",
            "middle-end-instcombine.md": "3.5 InstCombine 走读",
            "middle-end-gvn-inliner.md": "3.6 GVN 与 Inliner",
            "backend-selectiondag.md": "3.7 SelectionDAG",
            "backend-isel-regalloc.md": "3.8 指令选择与寄存器分配",
            "backend-scheduling-mc.md": "3.9 指令调度与 MC 层",
            "tablegen.md": "3.10 TableGen",
        }
    },
    "04-modification": {
        "title": "卷四：动手修改",
        "files": {
            "dev-workflow.md": "4.1 开发工作流",
            "write-a-pass.md": "4.2 编写一个 Pass",
            "add-instruction.md": "4.3 添加一条新指令",
            "modify-clang.md": "4.4 修改 Clang",
            "debugging.md": "4.5 调试技巧",
            "llvm-adt.md": "4.6 LLVM 容器与工具类",
            "testing-guide.md": "4.7 测试指南",
        }
    },
    "05-appendix": {
        "title": "卷五：附录",
        "files": {
            "glossary.md": "5.1 术语表",
            "further-reading.md": "5.2 扩展阅读",
        }
    },
}

PAGE_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }} — LLVM 学习文档</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css">
<style>
:root {
    --sidebar-width: 280px;
    --header-height: 60px;
    --bg: #ffffff;
    --sidebar-bg: #f6f8fa;
    --border: #d0d7de;
    --text: #1f2328;
    --text-muted: #656d76;
    --link: #0969da;
    --code-bg: #f6f8fa;
    --active-bg: #ddf4ff;
    --active-border: #0969da;
    --warning-bg: #fff8c5;
    --warning-border: #d4a72c;
}
@media (prefers-color-scheme: dark) {
    :root {
        --bg: #0d1117;
        --sidebar-bg: #161b22;
        --border: #30363d;
        --text: #e6edf3;
        --text-muted: #8b949e;
        --link: #58a6ff;
        --code-bg: #161b22;
        --active-bg: #1b365d;
        --active-border: #58a6ff;
        --warning-bg: #3d3200;
        --warning-border: #d4a72c;
    }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", Helvetica, Arial, sans-serif; background: var(--bg); color: var(--text); line-height: 1.7; display: flex; }
.sidebar { position: fixed; top: 0; left: 0; width: var(--sidebar-width); height: 100vh; background: var(--sidebar-bg); border-right: 1px solid var(--border); overflow-y: auto; padding: 20px 0; z-index: 10; }
.sidebar-title { padding: 0 20px 16px; font-size: 1.2em; font-weight: 700; border-bottom: 1px solid var(--border); margin-bottom: 8px; }
.sidebar-title a { color: var(--text); text-decoration: none; }
.sidebar-section { padding: 4px 0; }
.sidebar-section-title { padding: 8px 20px; font-size: 0.85em; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
.sidebar a { display: block; padding: 6px 20px; color: var(--text); text-decoration: none; font-size: 0.9em; border-left: 3px solid transparent; transition: all 0.15s; }
.sidebar a:hover { background: var(--active-bg); color: var(--link); }
.sidebar a.active { background: var(--active-bg); color: var(--link); border-left-color: var(--active-border); font-weight: 600; }
.content { margin-left: var(--sidebar-width); padding: 40px 60px; max-width: 900px; width: 100%; min-height: 100vh; }
.content h1 { font-size: 2em; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
.content h2 { font-size: 1.5em; margin: 32px 0 12px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }
.content h3 { font-size: 1.25em; margin: 24px 0 8px; }
.content h4 { font-size: 1.05em; margin: 16px 0 6px; }
.content p { margin: 0 0 16px; }
.content ul, .content ol { margin: 0 0 16px 24px; }
.content li { margin-bottom: 4px; }
.content a { color: var(--link); text-decoration: none; }
.content a:hover { text-decoration: underline; }
.content code { background: var(--code-bg); padding: 2px 6px; border-radius: 4px; font-family: "SF Mono", "Fira Code", "Consolas", monospace; font-size: 0.88em; }
.content pre { background: var(--code-bg); border: 1px solid var(--border); border-radius: 6px; padding: 16px; overflow-x: auto; margin: 0 0 16px; line-height: 1.5; }
.content pre code { background: none; padding: 0; font-size: 0.85em; }
.content blockquote { border-left: 4px solid var(--warning-border); background: var(--warning-bg); margin: 0 0 16px; padding: 12px 16px; border-radius: 0 4px 4px 0; }
.content blockquote p { margin: 0; }
.content table { border-collapse: collapse; width: 100%; margin: 0 0 16px; }
.content th, .content td { border: 1px solid var(--border); padding: 8px 12px; text-align: left; }
.content th { background: var(--sidebar-bg); font-weight: 600; }
.content img { max-width: 100%; }
.content hr { border: none; border-top: 1px solid var(--border); margin: 24px 0; }
.content .file-path { color: var(--text-muted); font-size: 0.85em; margin: -8px 0 16px; }
.content .exercise { border: 1px solid #0969da; border-radius: 6px; padding: 16px; margin: 16px 0; background: #ddf4ff15; }
.content .exercise h4 { color: #0969da; margin-top: 0; }
.mobile-toggle { display: none; position: fixed; top: 12px; left: 12px; z-index: 20; background: var(--sidebar-bg); border: 1px solid var(--border); border-radius: 6px; padding: 8px 12px; cursor: pointer; font-size: 1.2em; }
@media (max-width: 768px) {
    .sidebar { transform: translateX(-100%); transition: transform 0.2s; }
    .sidebar.open { transform: translateX(0); }
    .content { margin-left: 0; padding: 20px 16px; }
    .mobile-toggle { display: block; }
}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
</head>
<body>
<button class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('open')">☰</button>
<nav class="sidebar">
<div class="sidebar-title"><a href="/">📘 LLVM 学习文档</a></div>
{% for section in sections %}
<div class="sidebar-section">
<div class="sidebar-section-title">{{ section.title }}</div>
{% for item in section.links %}
<a href="/{{ item.link }}" class="{{ 'active' if item.active else '' }}">{{ item.label }}</a>
{% endfor %}
</div>
{% endfor %}
</nav>
<main class="content">
{{ content }}
</main>
<script>hljs.highlightAll();</script>
</body>
</html>
""")


def render_markdown(text: str) -> str:
    md = MarkdownIt("default", {"html": True, "typographer": True})
    return md.render(text)


def build():
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir()

    # Copy CSS
    css_dir = BUILD / "css"
    css_dir.mkdir()

    # Build navigation flat list
    sections = []
    all_pages = {}

    for section_dir, section_info in NAV_STRUCTURE.items():
        items = []
        for filename, label in section_info["files"].items():
            link = f"{section_dir}/{filename.replace('.md', '.html')}"
            items.append({"label": label, "link": link, "active": False})
            all_pages[link] = {"title": label, "section": section_info["title"]}
        sections.append({"title": section_info["title"], "links": items})

    index_html = """<h1>LLVM 编译器项目学习文档</h1>
<p>欢迎阅读 LLVM 编译器项目的系统学习文档。本文档覆盖从环境搭建、工具链使用、源码架构分析到动手修改的全流程。</p>
<h2>如何使用</h2>
<ul>
<li><strong>新手</strong>：建议从<a href="/01-getting-started/setup.html">卷一：速通环境</a>开始，搭建开发环境后跟着卷二的工具链使用练习。</li>
<li><strong>有一定基础</strong>：可以直接跳转到<a href="/03-source-architecture/directory-map.html">卷三：源码架构</a>，按目录地图逐模块阅读。</li>
<li><strong>想动手实践</strong>：参考<a href="/04-modification/dev-workflow.html">卷四：动手修改</a>，从写一个 Pass 开始。</li>
</ul>
<h2>目录</h2>
"""
    for section in sections:
        index_html += f"<h3>{section['title']}</h3>\n<ul>\n"
        for item in section["links"]:
            index_html += f"<li><a href=\"{item['link']}\">{item['label']}</a></li>\n"
        index_html += "</ul>\n"

    # Write index page
    idx_sections = [dict(s) for s in sections]
    with open(BUILD / "index.html", "w") as f:
        f.write(PAGE_TEMPLATE.render(title="目录", sections=idx_sections, content=index_html))

    # Build all pages
    for section_dir, section_info in NAV_STRUCTURE.items():
        out_dir = BUILD / section_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        for filename, label in section_info["files"].items():
            src_path = SRC / section_dir / filename
            if not src_path.exists():
                print(f"  Warning: {src_path} does not exist, skipping.")
                continue

            with open(src_path) as f:
                md_content = f.read()

            html_content = render_markdown(md_content)

            # Build navigation with active state
            active_sections = []
            for s in sections:
                items = []
                for item_ in s["links"]:
                    link = f"{section_dir}/{filename.replace('.md', '.html')}"
                    active = (item_["link"] == link)
                    items.append({"label": item_["label"], "link": item_["link"], "active": active})
                active_sections.append({"title": s["title"], "links": items})

            page = PAGE_TEMPLATE.render(
                title=label,
                sections=active_sections,
                content=html_content,
            )

            out_path = out_dir / filename.replace(".md", ".html")
            with open(out_path, "w") as f:
                f.write(page)

            print(f"  Built: {section_dir}/{filename.replace('.md', '.html')}")

    print(f"\nDone! Open {BUILD / 'index.html'} in your browser.")


if __name__ == "__main__":
    build()
