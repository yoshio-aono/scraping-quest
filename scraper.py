import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import requests
from bs4 import BeautifulSoup
import csv
import time
import re
from urllib.parse import urljoin

def get_page(url):
    """指定したURLのHTMLを取得する"""
    response = requests.get(url)
    response.encoding = "utf-8"
    print(f"ステータスコード: {response.status_code} → {url}")
    return response.text

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

def get_book_detail(url):
    """詳細ページからUPC・説明文・在庫数を取得する"""
    html = get_page(url)
    soup = BeautifulSoup(html, "html.parser")

    # UPC・在庫数はproduct informationテーブルから取得
    upc = ""
    stock = 0
    for row in soup.select("table tr"):
        header = row.select_one("th")
        value = row.select_one("td")
        if not header or not value:
            continue
        if header.text.strip() == "UPC":
            upc = value.text.strip()
        elif header.text.strip() == "Availability":
            match = re.search(r"\d+", value.text)
            stock = int(match.group()) if match else 0

    # 説明文は #product_description の直後の<p>
    desc_heading = soup.select_one("#product_description")
    description = ""
    if desc_heading:
        p = desc_heading.find_next_sibling("p")
        if p:
            description = p.text.strip()

    return {"upc": upc, "stock": stock, "description": description}

def get_next_url(html, base_url):
    """次のページのURLを取得する。なければNoneを返す"""
    soup = BeautifulSoup(html, "html.parser")
    next_btn = soup.select_one("li.next a")
    if next_btn:
        return urljoin(base_url, next_btn["href"])
    return None

def get_all_books():
    """全ページをループして全書籍を取得する（詳細ページも含む）"""
    url = "http://books.toscrape.com/"
    all_books = []
    page = 1

    while url:
        print(f"\n--- ページ {page} を取得中 ---")
        html = get_page(url)
        books = extract_books(html, url)
        all_books.extend(books)
        print(f"このページ: {len(books)}冊 / 累計: {len(all_books)}冊")

        url = get_next_url(html, url)
        page += 1
        time.sleep(1)

    # 各書籍の詳細ページを取得
    print(f"\n--- 詳細ページを取得中（合計{len(all_books)}冊）---")
    for i, book in enumerate(all_books, 1):
        print(f"[{i}/{len(all_books)}] {book['title'][:50]}")
        detail = get_book_detail(book["detail_url"])
        book.update(detail)
        del book["detail_url"]
        time.sleep(0.5)

    return all_books

def save_to_csv(books, filename="books.csv"):
    """書籍データをCSVファイルに保存する"""
    fieldnames = ["title", "price", "rating", "upc", "stock", "description"]
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(books)
    print(f"\n{len(books)}冊のデータを {filename} に保存しました！")

def main():
    print("全ページのスクレイピングを開始します...")
    all_books = get_all_books()
    save_to_csv(all_books)
    print(f"\n完了！合計 {len(all_books)} 冊取得しました。")

if __name__ == "__main__":
    main()