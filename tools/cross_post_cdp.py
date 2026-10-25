#!/usr/bin/env python3
"""
跨平台博客发布工具 — CDP 直连 Edge（复用你的登录态）
用法: python3 cross_post_cdp.py 2025-11-16-3d-modeling.md
"""

import sys
import re
from pathlib import Path

sys.path.insert(0, '/Users/alexcheng/Library/Application Support/QClaw/openclaw/config/skills/browser-cdp/scripts')
from browser_launcher import BrowserLauncher
from cdp_client import CDPClient
from page_snapshot import PageSnapshot
from browser_actions import BrowserActions


POSTS_DIR = Path("/Users/alexcheng/depot/alex-cheng.github.io/_posts")


def extract_title_and_body(md_text: str):
    """解析 Jekyll frontmatter"""
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
        title = m.group(1).strip() if m else Path(sys.argv[1]).stem

    return title, body.strip()


def md_to_text(md: str) -> str:
    """Markdown → 纯文本"""
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


def wait_for_input(prompt: str):
    """等待用户按回车"""
    input(prompt)


def publish_platform(client: CDPClient, actions: BrowserActions, snapshot: PageSnapshot,
                     name: str, url: str, title: str, body: str):
    """发布到单个平台"""
    print(f"\n{'='*50}")
    print(f"  >>> {name}")
    print(f"{'='*50}")

    # 查找是否已有该平台的标签页
    tabs = client.list_tabs()
    tab = None
    for t in tabs:
        if name.lower() in t.get('url', '').lower() or name in t.get('title', ''):
            tab = t
            break

    if tab:
        print(f"  发现已有标签页，切换过去")
        client.switch_tab(tab['id'])
    else:
        print(f"  新建标签页 → {url}")
        tab = client.create_tab(url)
        client.attach(tab['id'])

    actions.wait_for_load()

    # 检查是否被重定向到登录页
    current_url = actions.get_url()
    if any(k in current_url.lower() for k in ['login', 'signin', 'passport', 'auth']):
        print(f"\n  ⚠️  检测到登录页面")
        print(f"  请在 Edge 浏览器中手动完成登录，然后回到本窗口按回车继续...")
        wait_for_input("  按回车继续 >>>")
        actions.wait_for_load()

    print(f"  正在获取页面结构...")
    snapshot_data = snapshot.accessibility_tree()
    print(f"\n  页面快照（部分）:\n  {snapshot_data[:2000]}")
    print(f"\n  ⚠️  请在 Edge 浏览器中：")
    print(f"  1. 找到标题输入框，填入: {title[:50]}...")
    print(f"  2. 找到正文输入框，粘贴以下内容（已复制到剪贴板）:")
    print(f"  ────── 粘贴内容开头 ──────")
    print(f"  {body[:200]}...")
    print(f"  ────── 粘贴内容结尾 ──────")
    print(f"\n  完成后在浏览器中点【发布/投稿】，然后回到这里按回车继续下一个平台")
    wait_for_input("  按回车继续下一个平台 >>>")


def main():
    if len(sys.argv) < 2:
        print("用法: python3 cross_post_cdp.py <_posts/下的文件名>")
        print("示例: python3 cross_post_cdp.py 2025-11-16-3d-modeling.md")
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
    print(f"   字数: {len(plain_text)} 字\n")

    # 连接 Edge
    launcher = BrowserLauncher()
    cdp_url = launcher.launch(browser='edge')
    client = CDPClient(cdp_url)
    client.connect()

    snapshot = PageSnapshot(client)
    actions = BrowserActions(client, snapshot)

    print(f"✅ 已连接到 Edge（登录态已保留）\n")

    platforms = [
        ("CSDN",    "https://mp.csdn.net/editor/html",       title, plain_text),
        ("博客园",  "https://i.cnblogs.com/posts/edit",       title, plain_text),
        ("简书",    "https://www.jianshu.com/writer",          title, plain_text),
        ("知乎",    "https://www.zhihu.com/write",             title, plain_text),
    ]

    for name, url, t, b in platforms:
        try:
            publish_platform(client, actions, snapshot, name, url, t, b)
        except Exception as e:
            print(f"\n  ❌ 出错了: {e}")
            wait_for_input("  按回车继续下一个平台 >>>")

    print(f"\n{'='*50}")
    print(f"  全部平台处理完毕！")
    print(f"  你可以回到各标签页检查发布结果")
    print(f"{'='*50}")
    print(f"\n  注意：后续运行不需要重新登录，Edge 窗口保持打开即可")


if __name__ == "__main__":
    main()
