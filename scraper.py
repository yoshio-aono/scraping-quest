import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import requests
from bs4 import BeautifulSoup
import csv
import time
import re
import logging
from urllib.parse import urljoin
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client

# ─── ロギング設定（コンソール＋ファイル） ───────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("scraper.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ─── ページ取得 ────────────────────────────────────────────────────
def get_page(url, retries=5, wait=10):
    """指定したURLのHTMLを取得する（失敗時はリトライ）"""
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=30)
            response.encoding = "utf-8"
            logger.info(f"HTTP {response.status_code} → {url}")
            return response.text
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            logger.warning(f"接続エラー（{attempt}/{retries}回目）: {e}")
            if attempt < retries:
                logger.info(f"{wait}秒後にリトライします...")
                time.sleep(wait)
            else:
                logger.error(f"リトライ上限に達しました: {url}")
                raise

# ─── 一覧ページ解析 ───────────────────────────────────────────────
def extract_books(html, base_url):
    """HTMLから書籍データと詳細ページURLを抽出する"""
    soup = BeautifulSoup(html, "html.parser")
    books = []

    for article in soup.select("article.product_pod"):
        title = article.select_one("h3 a")["title"]
        price_text = article.select_one("p.price_color").text.strip()
        price = float(price_text.replace("£", "").replace("Â", "").strip())
        rating_map = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
        rating_word = article.select_one("p.star-rating")["class"][1]
        rating = rating_map[rating_word]
        detail_url = urljoin(base_url, article.select_one("h3 a")["href"])

        books.append({
            "title": title,
            "price": price,
            "rating": rating,
            "detail_url": detail_url,
        })

    return books

# ─── 詳細ページ解析 ───────────────────────────────────────────────
def get_book_detail(url):
    """詳細ページからUPC・説明文・在庫数を取得する"""
    html = get_page(url)
    soup = BeautifulSoup(html, "html.parser")

    upc = ""
    stock = 0
    for row in soup.select("table tr"):
        header = row.select_one("th")
        value  = row.select_one("td")
        if not header or not value:
            continue
        if header.text.strip() == "UPC":
            upc = value.text.strip()
        elif header.text.strip() == "Availability":
            match = re.search(r"\d+", value.text)
            stock = int(match.group()) if match else 0

    desc_heading = soup.select_one("#product_description")
    description = ""
    if desc_heading:
        p = desc_heading.find_next_sibling("p")
        if p:
            description = p.text.strip()

    return {"upc": upc, "stock": stock, "description": description}

# ─── ページネーション ─────────────────────────────────────────────
def get_next_url(html, base_url):
    """次のページのURLを取得する。なければNoneを返す"""
    soup = BeautifulSoup(html, "html.parser")
    next_btn = soup.select_one("li.next a")
    if next_btn:
        return urljoin(base_url, next_btn["href"])
    return None

# ─── カテゴリ一覧取得 ─────────────────────────────────────────────
def get_categories(html):
    """サイドバーからサブカテゴリ一覧を取得する（ルートのBooksは除外）"""
    soup = BeautifulSoup(html, "html.parser")
    categories = []
    for a in soup.select("ul.nav-list ul a"):
        name = a.text.strip()
        url  = urljoin("http://books.toscrape.com/", a["href"])
        categories.append({"name": name, "url": url})
    return categories

# ─── 全書籍取得 ───────────────────────────────────────────────────
def get_all_books():
    """カテゴリ別に全書籍を取得する（詳細ページも含む）"""
    top_url  = "http://books.toscrape.com/"
    top_html = get_page(top_url)
    categories = get_categories(top_html)
    logger.info(f"取得カテゴリ数: {len(categories)}件")

    all_books = []

    for cat_i, cat in enumerate(categories, 1):
        logger.info(f"[{cat_i}/{len(categories)}] カテゴリ: {cat['name']}")
        url  = cat["url"]
        page = 1

        while url:
            html  = get_page(url)
            books = extract_books(html, url)
            for book in books:
                book["category"] = cat["name"]
            all_books.extend(books)
            logger.info(f"  ページ{page}: {len(books)}冊 / 累計: {len(all_books)}冊")
            url = get_next_url(html, url)
            page += 1
            time.sleep(1)

    # 各書籍の詳細ページを取得（エラーが出ても1冊ずつスキップして継続）
    logger.info(f"詳細ページを取得中（合計{len(all_books)}冊）")
    errors = 0
    for i, book in enumerate(all_books, 1):
        try:
            logger.info(f"[{i}/{len(all_books)}] [{book['category']}] {book['title'][:40]}")
            detail = get_book_detail(book["detail_url"])
            book.update(detail)
        except Exception as e:
            logger.error(f"詳細取得失敗（スキップ）: {book['title']} → {e}")
            book.update({"upc": "", "stock": 0, "description": ""})
            errors += 1
        finally:
            del book["detail_url"]
        time.sleep(0.5)

    if errors:
        logger.warning(f"詳細取得エラー: {errors}件")

    return all_books

# ─── Supabase保存（差分upsert） ───────────────────────────────────
def save_to_supabase(books):
    """差分比較してSupabaseのbooksテーブルを差分upsertする"""
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        logger.error("SUPABASE_URL / SUPABASE_KEY が未設定です。.envを確認してください。")
        return

    client = create_client(url, key)

    # 既存データを全件取得
    logger.info("Supabaseから既存データを取得中...")
    existing = {}
    LIMIT = 1000
    offset = 0
    while True:
        res = (client.table("books")
               .select("upc,title,price,rating,stock,description,category")
               .range(offset, offset + LIMIT - 1)
               .execute())
        for row in res.data:
            existing[row["upc"]] = row
        if len(res.data) < LIMIT:
            break
        offset += LIMIT
    logger.info(f"既存データ: {len(existing)}件")

    # 差分分類
    now = datetime.now(timezone.utc).isoformat()
    new_books     = []
    updated_books = []
    unchanged     = 0

    for b in books:
        record = {
            "title":       b["title"],
            "price":       b["price"],
            "rating":      b["rating"],
            "upc":         b["upc"],
            "stock":       b["stock"],
            "description": b["description"],
            "category":    b["category"],
            "scraped_at":  now,
        }
        if b["upc"] not in existing:
            new_books.append(record)
        else:
            ex = existing[b["upc"]]
            changed = (
                b["title"]        != ex["title"]                 or
                float(b["price"]) != float(ex["price"])          or
                int(b["rating"])  != int(ex["rating"])           or
                int(b["stock"])   != int(ex["stock"])            or
                b["description"]  != ex["description"]           or
                b["category"]     != ex.get("category", "")
            )
            if changed:
                updated_books.append(record)
            else:
                unchanged += 1

    # 新規・更新分だけupsert
    to_upsert = new_books + updated_books
    if to_upsert:
        BATCH = 100
        for i in range(0, len(to_upsert), BATCH):
            batch = to_upsert[i : i + BATCH]
            client.table("books").upsert(batch, on_conflict="upc").execute()
            logger.info(f"  upsert完了: {min(i + BATCH, len(to_upsert))}/{len(to_upsert)}件")
    else:
        logger.info("差分なし。Supabaseの更新はスキップしました。")

    logger.info(f"新規{len(new_books)}件・更新{len(updated_books)}件・変更なし{unchanged}件")

# ─── CSV保存 ──────────────────────────────────────────────────────
def save_to_csv(books, filename="books.csv"):
    """書籍データをCSVファイルに保存する"""
    fieldnames = ["title", "price", "rating", "upc", "stock", "description", "category"]
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(books)
    logger.info(f"{len(books)}冊のデータを {filename} に保存しました")

# ─── メイン ───────────────────────────────────────────────────────
def main():
    start = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info("スクレイピング開始")
    logger.info("=" * 60)

    try:
        all_books = get_all_books()
        save_to_csv(all_books)
        save_to_supabase(all_books)

        elapsed = (datetime.now(timezone.utc) - start).seconds
        logger.info("=" * 60)
        logger.info(f"✅ 完了 | 取得: {len(all_books)}冊 | 所要時間: {elapsed//60}分{elapsed%60}秒")
        logger.info("=" * 60)

    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ 異常終了: {e}")
        logger.error("=" * 60)
        raise

if __name__ == "__main__":
    main()
