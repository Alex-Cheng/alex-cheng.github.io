#!/usr/bin/env python3
"""
跨平台博客同步工具 v2
- 一次登录，长期复用（登录态保存到本地）
- 四个平台全在一个浏览器窗口里，按标签页依次填好
"""

import sys
import re
import json
import platform
from pathlib import Path
from playwright.sync_api import sync_playwright

# ============ 配置区 ============
POSTS_DIR = Path("/Users/alexcheng/depot/alex-cheng.github.io/_posts")
STATE_FILE = Path.home() / ".cross_post_state.json"

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# ================================


def extract_title_and_body(md_text: str):
    """解析 Jekyll frontmatter，返回 (title, body)"""
    title = None
    body = md_text

    fm = re.match(r'^---\s*\n(.*?)\n---\s*\n', md_text, re.DOTALL)
    if fm:
        body = md_text[fm.end():]
        for line in fm.group(1).split('\n'):
            m = re.match(r"^title:\s*['\"]?(.*?)['\"]?\s*$", line.strip())
            if m:
                title = m.group(1).strip()

    if not title:
        m = re.match(r'^#\s+(.+)\s*$', body.strip())
        if m:
            title = m.group(1).strip()
        else:
            title = Path(sys.argv[1]).stem

    return title, body.strip()


def md_to_text(md: str) -> str:
    """Markdown -> 纯文本"""
    text = md
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]+`', lambda m: m.group(0).strip('`'), text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}(.+?)_{1,3}', r'\1', text)
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[(.+?)\]\(.*?\)', r'\1', text)
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[-*+]\s+', '- ', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+\.\s+', '- ', text, flags=re.MULTILINE)
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def fill_csdn(page, title, content):
    """CSDN"""
    try:
        page.goto("https://mp.csdn.net/", wait_until="domcontentloaded", timeout=15000)
    except Exception:
        page.goto("https://www.csdn.net/", wait_until="domcontentloaded", timeout=15000)

    page.wait_for_timeout(3000)

    if "passport.csdn.net" in page.url or "login" in page.url:
        print("⚠️  CSDN 未登录，请在浏览器中完成登录，完成后切换回本窗口按回车继续...")
        input()

    # 打开写文章页
    try:
        page.goto("https://mp.csdn.net/editor/html?spm=1001.2014.3001.5352", timeout=15000)
        page.wait_for_timeout(2000)
    except Exception:
        pass

    # 填标题
    title_sel = "#txtTitle, [data-type='title'], .article-title input, input[placeholder*='标题']"
    for sel in title_sel.split(", "):
        try:
            page.fill(sel, title, timeout=3000)
            print("✅ CSDN 标题填好")
            break
        except Exception:
            pass

    # 填正文（多种方式轮询）
    content_sel = (
        "[data-placeholder='开始创作'], "
        ".editor__content-area, "
        ".textarea-container textarea, "
        "#content, "
        "[contenteditable='true']"
    )
    filled = False
    for sel in content_sel.split(", "):
        try:
            page.fill(sel, content, timeout=3000)
            print("✅ CSDN 正文填好")
            filled = True
            break
        except Exception:
            pass

    if not filled:
        print("⚠️  CSDN 正文框未识别，请在浏览器中手动粘贴正文")


def fill_cnblogs(page, title, content):
    """博客园"""
    try:
        page.goto("https://i.cnblogs.com/posts/edit", wait_until="domcontentloaded", timeout=15000)
    except Exception:
        page.goto("https://www.cnblogs.com/", wait_until="domcontentloaded", timeout=15000)

    page.wait_for_timeout(3000)

    if "login" in page.url:
        print("⚠️  博客园未登录，请在浏览器中完成登录，完成后切换回本窗口按回车继续...")
        input()

    # 填标题
    for sel in ["#postTitle", "input[data-attr*='title']", ".post-title input"]:
        try:
            page.fill(sel, title, timeout=3000)
            print("✅ 博客园标题填好")
            break
        except Exception:
            pass

    # 填正文
    for sel in ["#MDEditor", "#editor", ".md-editor textarea", "[contenteditable='true']"]:
        try:
            page.fill(sel, content, timeout=3000)
            print("✅ 博客园正文填好")
            return
        except Exception:
            pass
    print("⚠️  博客园正文框未识别，请在浏览器中手动粘贴正文")


def fill_jianshu(page, title, content):
    """简书"""
    try:
        page.goto("https://www.jianshu.com/writer", wait_until="domcontentloaded", timeout=15000)
    except Exception:
        page.goto("https://www.jianshu.com/", wait_until="domcontentloaded", timeout=15000)

    page.wait_for_timeout(3000)

    if "login" in page.url.lower():
        print("⚠️  简书未登录，请在浏览器中完成登录，完成后切换回本窗口按回车继续...")
        input()

    for sel in [".title-input", ".title input", "input[placeholder*='标题']"]:
        try:
            page.fill(sel, title, timeout=3000)
            print("✅ 简书标题填好")
            break
        except Exception:
            pass

    for sel in ["._18-d3", ".first-meta-editor", "[contenteditable='true']", ".textarea"]:
        try:
            page.click(sel, timeout=3000)
            page.keyboard.type(content, delay=8)
            print("✅ 简书正文填好")
            return
        except Exception:
            pass
    print("⚠️  简书正文框未识别，请在浏览器中手动粘贴正文")


def fill_zhihu(page, title, content):
    """知乎"""
    try:
        page.goto("https://www.zhihu.com/write", wait_until="domcontentloaded", timeout=15000)
    except Exception:
        page.goto("https://www.zhihu.com/", wait_until="domcontentloaded", timeout=15000)

    page.wait_for_timeout(3000)

    if "login" in page.url:
        print("⚠️  知乎未登录，请在浏览器中完成登录，完成后切换回本窗口按回车继续...")
        input()

    for sel in ["input[data-maxlength='100']", ".input[data-maxlength='100']", "input[placeholder*='标题']"]:
        try:
            page.fill(sel, title, timeout=3000)
            print("✅ 知乎标题填好")
            break
        except Exception:
            pass

    # 知乎正文是 contenteditable
    for sel in ["[data-tab-id='origin']", "[role='textbox']", "[contenteditable='true']"]:
        try:
            page.click(sel, timeout=3000)
            page.wait_for_timeout(500)
            page.keyboard.type(content, delay=5)
            print("✅ 知乎正文填好")
            return
        except Exception:
            pass
    print("⚠️  知乎正文框未识别，请在浏览器中手动粘贴正文")


def main():
    if len(sys.argv) < 2:
        print("用法: python3 cross_post.py <_posts/下的文件名>")
        print("示例: python3 cross_post.py 2025-11-16-3d-modeling.md")
        sys.exit(1)

    filename = sys.argv[1]
    post_path = POSTS_DIR / filename

    if not post_path.exists():
        print(f"❌ 文件不存在: {post_path}")
        sys.exit(1)

    md_text = post_path.read_text(encoding="utf-8")
    title, body = extract_title_and_body(md_text)
    plain_text = md_to_text(body)

    print(f"📄 文章: {title}")
    print(f"   纯文本字数: {len(plain_text)} 字\n")

    # 读取保存的登录态
    storage_state = str(STATE_FILE) if STATE_FILE.exists() else None

    with sync_playwright() as p:
        # 尝试复用已保存的浏览器上下文（保持登录态）
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=False,
            args=["--start-maximized"]
        )

        context_args = {"viewport": {"width": 1400, "height": 900}}
        if storage_state:
            context_args["storage_state"] = storage_state

        context = browser.new_context(**context_args)
        page = context.new_page()

        print("=" * 55)
        print("  博客跨平台发布工具 v2")
        print("  首次使用：各平台依次弹出，请登录一次")
        print("  之后使用：直接复用登录态，无需再登录")
        print("=" * 55 + "\n")

        # ── CSDN ──
        print(">>> CSDN")
        fill_csdn(page, title, plain_text)
        page.wait_for_timeout(1000)

        # ── 博客园 ──
        print("\n>>> 博客园")
        fill_cnblogs(page, title, plain_text)
        page.wait_for_timeout(1000)

        # ── 简书 ──
        print("\n>>> 简书")
        fill_jianshu(page, title, plain_text)
        page.wait_for_timeout(1000)

        # ── 知乎 ──
        print("\n>>> 知乎")
        fill_zhihu(page, title, plain_text)

        print("\n" + "=" * 55)
        print("  全部平台填写完毕！")
        print("  请逐个标签页检查内容 → 点发布")
        print("  登录态会在本窗口关闭时自动保存")
        print("=" * 55)

        # 保存登录态到文件，下次运行直接复用
        context.storage_state(path=str(STATE_FILE))
        print(f"\n💾 登录态已保存到 {STATE_FILE}")

        page.wait_for_timeout(120000)


if __name__ == "__main__":
    main()
