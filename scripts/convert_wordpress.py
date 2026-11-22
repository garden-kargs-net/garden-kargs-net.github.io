#!/usr/bin/env python3
import os
import re
import html
import json
from datetime import datetime
from bs4 import BeautifulSoup, NavigableString, Tag

BACKUP_DIR = "/home/skarg/Documents/Websites/garden.kargs.net"
POSTS_DIR = "/home/skarg/Code/garden-kargs-net.github.io/_posts"

def clean_text(s):
    if not s:
        return ""
    s = s.replace("\u00c2\u00a0", " ")
    s = s.replace("\u00a0", " ")
    s = s.replace("Â ", " ")
    s = s.replace("Â", "")
    s = s.replace("&#8230;", "...")
    s = s.replace("&#8217;", "'")
    s = s.replace("&#8216;", "'")
    s = s.replace("&#8220;", '"')
    s = s.replace("&#8221;", '"')
    s = s.replace("&#8211;", "–")
    s = s.replace("&#8212;", "—")
    s = html.unescape(s)
    return s

def normalize_url(url):
    if not url:
        return ""
    url = re.sub(r"^(\.\./)+wp-content/", "http://garden.kargs.net/wp-content/", url)
    if url.startswith("/wp-content/"):
        url = "http://garden.kargs.net" + url
    url = url.replace(".thumbs/.", "thumbs/")
    url = url.replace("https://garden.kargs.net/", "http://garden.kargs.net/")
    return url

def elem_to_markdown(elem):
    if isinstance(elem, NavigableString):
        return clean_text(str(elem))

    if not isinstance(elem, Tag):
        return ""

    if elem.name in ["script", "style"]:
        return ""
    if elem.get("class") and any("ph_social_share" in c for c in elem.get("class", [])):
        return ""
    if elem.get("id") and "social_share" in elem.get("id", ""):
        return ""

    tag = elem.name

    if tag == "table":
        return f"\n\n{str(elem)}\n\n"

    if tag in ["object", "embed"]:
        src = elem.get("src", "")
        if not src and elem.find("embed"):
            src = elem.find("embed").get("src", "")
        if "youtube.com" in src:
            yt_id = re.search(r"/v/([a-zA-Z0-9_-]+)", src)
            if yt_id:
                return f"\n\n[YouTube Video](https://www.youtube.com/watch?v={yt_id.group(1)})\n\n"
        return f"\n\n{str(elem)}\n\n"

    if tag == "iframe":
        return f"\n\n{str(elem)}\n\n"

    # WordPress caption: <div class="wp-caption ..."><a ...><img ...></a><p class="wp-caption-text">...</p></div>
    if tag == "div" and elem.get("class") and any("wp-caption" in c for c in elem.get("class", [])):
        a_elem = elem.find("a")
        img_elem = elem.find("img")
        caption_elem = elem.find(class_=lambda c: c and "wp-caption-text" in c)
        
        cap_text = ""
        if caption_elem:
            cap_text = "".join(elem_to_markdown(c) for c in caption_elem.children).strip()
            caption_elem.decompose()
        
        md_img = ""
        if a_elem and a_elem.find("img"):
            md_img = elem_to_markdown(a_elem)
        elif img_elem:
            md_img = elem_to_markdown(img_elem)
        else:
            md_img = "".join(elem_to_markdown(c) for c in elem.children).strip()
            
        res = f"\n\n{md_img.strip()}"
        if cap_text:
            res += f"\n\n*{cap_text}*"
        return res + "\n\n"

    # Image inside link: <a href="..."><img ...></a>
    if tag == "a" and elem.find("img"):
        img = elem.find("img")
        alt = clean_text(img.get("alt", "") or img.get("title", ""))
        img_src = normalize_url(img.get("src", ""))
        href = normalize_url(elem.get("href", ""))
        
        link_md = f"[![{alt}]({img_src})]({href})"
        
        elem_clone = BeautifulSoup(str(elem), "html.parser").a
        if elem_clone and elem_clone.img:
            elem_clone.img.decompose()
            rem = "".join(elem_to_markdown(c) for c in elem_clone.children).strip()
            if rem:
                return f"\n\n{link_md}\n\n{rem}"
        return f"\n\n{link_md}\n\n"

    if tag == "img":
        alt = clean_text(elem.get("alt", "") or elem.get("title", ""))
        src = normalize_url(elem.get("src", ""))
        return f"\n\n![{alt}]({src})\n\n"

    if tag == "a":
        href = normalize_url(elem.get("href", ""))
        text = "".join(elem_to_markdown(c) for c in elem.children).strip()
        if not text:
            return ""
        return f"[{text}]({href})"

    if tag in ["strong", "b"]:
        text = "".join(elem_to_markdown(c) for c in elem.children)
        return f"**{text}**"

    if tag in ["em", "i"]:
        text = "".join(elem_to_markdown(c) for c in elem.children)
        return f"*{text}*"

    if tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
        level = int(tag[1])
        prefix = "#" * level
        text = "".join(elem_to_markdown(c) for c in elem.children).strip()
        return f"\n\n{prefix} {text}\n\n"

    if tag == "blockquote":
        inner = "".join(elem_to_markdown(c) for c in elem.children).strip()
        lines = inner.split("\n")
        quoted = "\n".join(f"> {l}" if l else ">" for l in lines)
        return f"\n\n{quoted}\n\n"

    if tag == "ul":
        items = []
        for li in elem.find_all("li", recursive=False):
            item_text = "".join(elem_to_markdown(c) for c in li.children).strip()
            items.append(f"- {item_text}")
        return "\n\n" + "\n".join(items) + "\n\n"

    if tag == "ol":
        items = []
        for idx, li in enumerate(elem.find_all("li", recursive=False), 1):
            item_text = "".join(elem_to_markdown(c) for c in li.children).strip()
            items.append(f"{idx}. {item_text}")
        return "\n\n" + "\n".join(items) + "\n\n"

    if tag == "br":
        return "  \n"

    if tag in ["p", "div"]:
        content = "".join(elem_to_markdown(c) for c in elem.children).strip()
        return f"\n\n{content}\n\n" if content else ""

    return "".join(elem_to_markdown(c) for c in elem.children)

def parse_comments(post_data):
    link = post_data.get("link", "")
    rel_path = link.replace("https://garden.kargs.net/", "").replace("http://garden.kargs.net/", "").strip("/")
    html_file = os.path.join(BACKUP_DIR, rel_path, "index.html")
    
    if not os.path.exists(html_file):
        post_id = post_data["id"]
        alt = os.path.join(BACKUP_DIR, f"index.html?p={post_id}.html")
        if os.path.exists(alt):
            html_file = alt
        else:
            return ""

    with open(html_file, "r", encoding="utf-8", errors="replace") as fp:
        soup = BeautifulSoup(fp.read(), "html.parser")

    comments_div = soup.find("div", id="comments")
    if not comments_div:
        return ""

    comment_lis = comments_div.find_all("li", class_="comment")
    if not comment_lis:
        return ""

    title = soup.find("h3", id="comments-title")
    if title:
        raw_title_str = title.get_text(separator=" ")
        title_text = re.sub(r"\s+", " ", clean_text(raw_title_str)).strip()
    else:
        title_text = f"{len(comment_lis)} Responses"

    out = [f"\n\n### {title_text}\n"]

    for idx, li in enumerate(comment_lis, 1):
        author_elem = li.find(class_="comment-author")
        cite = author_elem.find("cite") if author_elem else None
        author_name = clean_text(cite.get_text(strip=True) if cite else "Anonymous")
        author_url = cite.find("a")["href"] if (cite and cite.find("a")) else None
        if author_url and ("index.html" in author_url or "garden.kargs.net" in author_url):
            author_url = None

        meta_elem = li.find(class_="comment-meta")
        date_text = clean_text(meta_elem.get_text(strip=True) if meta_elem else "")

        body_elem = li.find(class_="comment-body")
        if not body_elem:
            body_elem = li.find(lambda t: t.name == "div" and "comment-" in t.get("id", ""))
        
        body_md = ""
        if body_elem:
            body_md = elem_to_markdown(body_elem).strip()
            body_md = re.sub(r"\n{3,}", "\n\n", body_md)

        if author_url:
            author_str = f"[{author_name}]({author_url})"
        else:
            author_str = author_name

        comment_header = f"{idx}.  {author_str} says on {date_text}:"
        indented_body = "\n".join(f"    {l}" if l else "" for l in body_md.split("\n"))
        out.append(f"{comment_header}\n\n{indented_body}\n")

    return "\n".join(out)

def convert_post(post_data):
    post_id = post_data["id"]
    date_raw = post_data["date"]
    date_gmt = post_data.get("date_gmt", date_raw)
    slug = post_data["slug"]
    
    try:
        dt_local = datetime.fromisoformat(date_raw)
        dt_gmt = datetime.fromisoformat(date_gmt)
        diff_hours = int(round((dt_gmt - dt_local).total_seconds() / 3600))
        tz_offset = f"-{abs(diff_hours):02d}:00" if diff_hours >= 0 else f"+{abs(diff_hours):02d}:00"
    except Exception:
        tz_offset = "-05:00"

    iso_date = f"{date_raw}{tz_offset}"
    raw_title = clean_text(post_data["title"]["rendered"]).strip()
    
    if not raw_title:
        fallbacks = {
            94: "For Today...",
            600: "Dawn at Home",
            743: "Start by Doing What Is Necessary",
            756: "First Day of School",
            1006: "Deschool Yourself"
        }
        raw_title = fallbacks.get(post_id, "Untitled")

    title_escaped = raw_title.replace("'", "''")

    year = date_raw[:4]
    month = date_raw[5:7]
    day = date_raw[8:10]

    category = "homeschooling" if 2 in post_data.get("categories", []) else "Uncategorized"

    fm = f"""---
id: {post_id}
title: '{title_escaped}'
date: '{iso_date}'
author: Patricia Karg
layout: post
permalink: /{year}/{month}/{day}/{slug}
categories:
    - {category}
---"""

    banner = "![Azalea](http://garden.kargs.net/wp-content/uploads/2013/04/cropped-IMAG8993.jpg)"

    soup = BeautifulSoup(post_data["content"]["rendered"], "html.parser")
    body_md = elem_to_markdown(soup).strip()
    
    comments_md = parse_comments(post_data)

    full_content = f"{fm}\n{banner}\n\n{body_md}"
    if comments_md:
        full_content += f"\n\n{comments_md.strip()}"
    
    full_content = re.sub(r"\n{3,}", "\n\n", full_content).strip() + "\n"
    
    filename = f"{year}-{month}-{day}-{slug}.md"
    return filename, full_content

def run_all(dry_run=True):
    posts = []
    for p in os.listdir(f"{BACKUP_DIR}/wp-json/wp/v2/posts"):
        with open(f"{BACKUP_DIR}/wp-json/wp/v2/posts/{p}") as fp:
            posts.append(json.load(fp))

    posts.sort(key=lambda x: x["date"])

    existing_files = set(os.listdir(POSTS_DIR))
    
    converted = 0
    skipped = 0
    
    for p in posts:
        fname, content = convert_post(p)
        
        # Check if already exists (by exact filename, or date match in existing files)
        date_prefix = p["date"][:10]
        # Only skip if a post from that date already exists in the original 28 posts
        already_there = any(f.startswith(date_prefix) for f in existing_files)
        
        if already_there:
            # Special case: check if it's one of the 2006-2007 posts already committed
            # Note: 2006-07-10 had two posts (hello-world and happy-birthday-to-me)
            # Check exact filename
            if fname in existing_files:
                skipped += 1
                continue
            # For 2007-03-20, pansy-parade was used instead of spring-is-officially-here
            if fname == "2007-03-20-spring-is-officially-here.md" and "2007-03-20-pansy-parade.md" in existing_files:
                skipped += 1
                continue
            if p["id"] in [1, 3, 4, 5, 7, 9, 10, 12, 13, 14, 15, 16, 17, 19, 20, 23, 24, 25, 26, 27, 29, 30, 31, 32, 33, 35, 36, 37]:
                skipped += 1
                continue
            
        converted += 1
        out_path = os.path.join(POSTS_DIR, fname)
        if not dry_run:
            with open(out_path, "w", encoding="utf-8") as fp:
                fp.write(content)
        else:
            if converted <= 3:
                print(f"[DRY-RUN] Would write: {fname}")
                print(content[:300])
                print("-" * 40)

    print(f"Total posts: {len(posts)}, Converted (new): {converted}, Skipped (existing): {skipped}")

if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv
    run_all(dry_run=dry)
