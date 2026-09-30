"""Build reviewed Markdown articles. Review previews never enter the production output."""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
from html import escape
import json
from pathlib import Path
import re
import shutil
import sys
import tomllib
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

import markdown

ROOT = Path(__file__).resolve().parents[1]


def read_post(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("+++\n"):
        raise ValueError(f"TOML front matter missing: {path.name}")
    header, body = text[4:].split("\n+++\n", 1)
    post = tomllib.loads(header)
    for key in ("title", "description", "slug", "topic", "date", "status"):
        if not isinstance(post.get(key), str) or not post[key].strip():
            raise ValueError(f"{path.name}: missing {key}")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", post["slug"]):
        raise ValueError(f"Invalid slug: {post['slug']}")
    date.fromisoformat(post["date"])
    if post["status"] not in ("review", "published"):
        raise ValueError(f"Unknown status: {post['status']}")
    post["body"] = body
    post["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return post


def load_posts(directory, review=None):
    posts = []
    for path in sorted(directory.glob("*.md")):
        post = read_post(path)
        if post["status"] != "published":
            raise ValueError("Keep unreviewed sources outside the public repository")
        receipt = json.loads(path.with_suffix(".approval.json").read_text())
        if receipt.get("sha256") != post["sha256"] or receipt.get("reviewer") != "user":
            raise ValueError(f"Final user review missing or content changed: {path.name}")
        date.fromisoformat(receipt["reviewed_on"])
        posts.append(post)
    if review:
        post = read_post(review)
        post["preview"] = True
        posts = [p for p in posts if p["slug"] != post["slug"]] + [post]
    slugs = [p["slug"] for p in posts]
    if len(slugs) != len(set(slugs)):
        raise ValueError("Duplicate article slug")
    return sorted(posts, key=lambda p: (p["date"], p["slug"]), reverse=True)


def build(output="dist", review=None, url=None):
    config = tomllib.loads((ROOT / "site.toml").read_text())
    base = (url or config["url"]).rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("Site URL must be an absolute HTTP(S) URL without query or fragment")
    out = ROOT / output
    if output not in ("dist", "preview"):
        raise ValueError("Output must be dist or preview")
    if review and output != "preview":
        raise ValueError("Review builds may only write to preview/")
    posts = load_posts(ROOT / "posts", review)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    shutil.copytree(ROOT / "assets", out / "assets")
    prefix = parsed.path.rstrip("/")
    href = lambda path="": escape(prefix + "/" + path, quote=True)
    canonical = lambda path="": base + "/" + path

    def page(path, title, description, body, article=None):
        is_preview = bool(review)
        robots = '<meta name="robots" content="noindex,nofollow">' if is_preview or path == "404.html" else ""
        ribbon = '<div class="review-banner" lang="ja">確認用プレビュー · 記事は未公開です</div>' if is_preview else ""
        schema = ""
        if article and not is_preview:
            schema = '<script type="application/ld+json">' + json.dumps({
                "@context": "https://schema.org", "@type": "Article", "headline": title,
                "description": description, "datePublished": article["date"],
                "inLanguage": config["language"], "mainEntityOfPage": canonical(path),
            }, ensure_ascii=False).replace("<", "\\u003c") + "</script>"
        html = f'''<!doctype html>
<html lang="{config['language']}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} · {escape(config['title'])}</title>
<meta name="description" content="{escape(description, quote=True)}">{robots}
<link rel="canonical" href="{escape(canonical(path), quote=True)}">
<meta property="og:type" content="{'article' if article else 'website'}">
<meta property="og:title" content="{escape(title, quote=True)}">
<meta property="og:description" content="{escape(description, quote=True)}">
<meta property="og:url" content="{escape(canonical(path), quote=True)}">
<meta property="og:locale" content="zh_TW">
<link rel="icon" href="{href('assets/favicon.svg')}" type="image/svg+xml">
<link rel="stylesheet" href="{href('assets/style.css')}">
<link rel="alternate" type="application/atom+xml" title="{escape(config['title'])}" href="{href('feed.xml')}">
{schema}</head><body>{ribbon}
<a class="skip" href="#main">跳到主要內容</a>
<header class="header"><a class="brand" href="{href()}"><span class="brand-icon" lang="ja" aria-hidden="true">あ</span><span>{escape(config['title'])}<small>JAPANESE PRONUNCIATION NOTES</small></span></a>
<nav aria-label="主要導覽"><a href="{href('#articles')}">文章</a><a href="{href('about/')}">關於</a></nav></header>
<main id="main">{body}</main>
<footer><span>{escape(config['title'])}<small>用繁體中文，一次理解一個發音重點。</small></span><div><a href="{href('feed.xml')}">訂閱 RSS</a><a href="{href('about/')}">關於本站</a></div></footer>
</body></html>'''
        dest = out / (path + "index.html" if not path or path.endswith("/") else path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")

    def heading(text):
        return re.sub(r"「([ぁ-ゖァ-ヺー]+)」", r'<span lang="ja" class="keep">「\1」</span>', escape(text))

    cards = "".join(f'''<a class="article-card" href="{href('articles/' + p['slug'] + '/')}">
<div class="card-meta"><span>{escape(p['topic'])}</span><span>{'確認用' if p.get('preview') else escape(p['date'])}</span></div>
<h3>{heading(p['title'])}</h3><p>{escape(p['description'])}</p><span class="read">閱讀文章 <span aria-hidden="true">↗</span></span></a>''' for p in posts)
    if not cards:
        cards = '<div class="empty"><h3>第一篇筆記，正在整理中。</h3><p>我們從長音開始，拆解日語裡容易混淆的聲音。文章確認後會在這裡公開。</p></div>'
    page("", "用繁體中文理解日語發音", config["description"], f'''
<section class="hero"><div><p class="eyebrow">給使用繁體中文的日語學習者</p><h1>從一個詞，<br>讀懂日語發音。</h1><p class="lead">長音多一拍，意思就可能不同。<br>從熟悉的詞語出發，慢慢看懂聲音裡的細節。</p><a class="button" href="#articles">開始閱讀 <span aria-hidden="true">↓</span></a></div>
<div class="sound-note" aria-label="長音的例子：おばさん四拍，おばあさん五拍"><span class="note-label">發音觀察 01 <span>長音</span></span><div class="word" lang="ja">おばさん</div><div class="mora-line"><i></i><i></i><i></i><i></i><span>4 拍</span></div><div class="word" lang="ja">おば<span>あ</span>さん</div><div class="mora-line"><i></i><i></i><i class="long"></i><i></i><i></i><span>5 拍</span></div><p>多一拍，母音連續延長。<br><small>方格表示結構，並非實際聲音的時間比例。</small></p></div></section>
<section class="articles" id="articles"><div class="section-heading"><div><p class="eyebrow">閱讀筆記</p><h2>一次，一個發音重點。</h2></div><span class="count">{len(posts):02d} 篇</span></div><div class="cards">{cards}</div></section>
<section class="approach"><p class="eyebrow">這裡的學習方式</p><div><h2>先看懂，再慢慢練習。</h2><p>用日語例子和繁體中文說明，理解詞語的聲音結構。文章附上參考資料，方便你接著查閱；文字理解與聽辨、發音練習，會清楚區分。</p><a class="text-link" href="{href('about/')}">認識這份筆記 <span aria-hidden="true">→</span></a></div></section>''')
    about = f'''<div class="page-heading"><p class="eyebrow">關於本站</p><h1>把日語發音，<br>說得更清楚一點。</h1></div><div class="prose narrow"><p>「日語發音筆記」是給使用繁體中文的日語學習者閱讀的發音解說網站。從長音、促音等主題開始，每篇集中說明一個重點。</p><h2>你可以怎麼使用</h2><p>先閱讀例子與說明，再完成文章中的小練習。有提供音檔的文章會標示練習方式；只有文字的文章，重點是理解結構，不用它判定自己的聽辨或發音能力。</p><h2>內容與修訂</h2><p>文章會附上可查閱的參考資料。本站由 latent-bridge 維護，使用 AI 協助整理與製作，並由站方確認後發布。本站不代表參考資料的原作者或機構。</p><p>若發現內容有誤，可透過 <a href="{escape(config['repository'])}/issues">GitHub Issues</a> 提出更正建議。請提供文章連結及需要修正的段落，勿附上個人資料或私人錄音。留言需要 GitHub 帳號，內容會公開。</p><h2>更新與隱私</h2><p>文章逐篇整理，不承諾固定更新日期。你可以加入書籤，或用 <a href="{href('feed.xml')}">RSS 閱讀器</a> 訂閱。</p><p>本站未加入廣告、第三方流量分析、追蹤 Cookie 或收集錄音的表單。網站託管服務仍可能處理連線紀錄；相關方式請參閱 <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement">GitHub 隱私聲明</a>。</p></div>'''
    page("about/", "關於日語發音筆記", "本站的閱讀方式、內容修訂、更新與隱私說明。", about)
    for p in posts:
        body = markdown.markdown(p["body"], extensions=["tables", "attr_list", "md_in_html", "toc"], output_format="html")
        article = f'''<article><header class="article-heading"><a class="back" href="{href('#articles')}">← 所有文章</a><p class="eyebrow">{escape(p['topic'])} · 文字解說</p><h1>{heading(p['title'])}</h1><p class="article-description">{escape(p['description'])}</p><div class="byline">日語發音筆記 <span>·</span> {'確認用預覽' if p.get('preview') else escape(p['date'])}</div></header><div class="prose narrow">{body}</div><div class="article-end narrow"><p>一次理解一個重點，再回來複習。</p><a href="{href('#articles')}">← 回到文章列表</a><a href="{href('feed.xml')}">訂閱後續文章 →</a></div></article>'''
        page(f"articles/{p['slug']}/", p["title"], p["description"], article, p)
    page("404.html", "找不到這個頁面", "這個連結可能已變更。", f'<div class="page-heading"><p class="eyebrow">404</p><h1>這一頁不在這裡。</h1><p>文章連結可能已經變更。</p><a class="button" href="{href()}">回到首頁 →</a></div>')

    # Review previews are local only, with no article discovery metadata.
    visible = [] if review else posts
    ns = "http://www.w3.org/2005/Atom"
    ET.register_namespace("", ns)
    feed = ET.Element(f"{{{ns}}}feed")
    def atom(parent, tag, text=None, **attrs):
        node = ET.SubElement(parent, f"{{{ns}}}{tag}", attrs)
        node.text = text
        return node
    atom(feed, "title", config["title"])
    atom(feed, "id", base + "/")
    atom(feed, "link", href=base + "/feed.xml", rel="self")
    atom(feed, "link", href=base + "/")
    atom(feed, "updated", (visible[0]["date"] if visible else "2026-09-30") + "T00:00:00Z")
    atom(atom(feed, "author"), "name", config["title"])
    for p in visible:
        entry = atom(feed, "entry")
        atom(entry, "title", p["title"])
        atom(entry, "id", canonical(f"articles/{p['slug']}/"))
        atom(entry, "link", href=canonical(f"articles/{p['slug']}/"))
        atom(entry, "updated", p["date"] + "T00:00:00Z")
        atom(entry, "summary", p["description"])
    ET.ElementTree(feed).write(out / "feed.xml", encoding="utf-8", xml_declaration=True)
    sitemap = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    if not review:
        for path in ["", "about/"] + [f"articles/{p['slug']}/" for p in visible]:
            ET.SubElement(ET.SubElement(sitemap, "url"), "loc").text = canonical(path)
    ET.ElementTree(sitemap).write(out / "sitemap.xml", encoding="utf-8", xml_declaration=True)
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n" if review else f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
    (out / ".nojekyll").touch()
    (out / "build.json").write_text(json.dumps({"preview": bool(review), "articles": [p["slug"] for p in posts]}, ensure_ascii=False))
    print(f"Built {len(posts)} articles → {out}")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", type=Path)
    parser.add_argument("--url")
    args = parser.parse_args()
    try:
        build("preview" if args.review else "dist", args.review, args.url)
    except (ValueError, KeyError, OSError) as exc:
        sys.exit(str(exc))
