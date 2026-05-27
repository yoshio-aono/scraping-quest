import requests
from bs4 import BeautifulSoup
import csv
import time

def get_page(url):
    """指定したURLのHTMLを取得する"""
    response = requests.get(url)
    response.encoding = "utf-8"
    print(f"ステータスコード: {response.status_code} → {url}")
    return response.text

def extract_books(html):
    """HTMLから書籍データを抽出する"""
    soup = BeautifulSoup(html, "html.parser")
    books = []

    for article in soup.select("article.product_pod"):
        title = article.select_one("h3 a")["title"]
        price_text = article.select_one("p.price_color").text.strip()
        price = float(price_text.replace("£", "").replace("Â", "").strip())
        rating_map = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
        rating_word = article.select_one("p.star-rating")["class"][1]
        rating = rating_map[rating_word]

        books.append({
            "title": title,
            "price": price,
            "rating": rating
        })

    return books

def get_next_url(html):
    """次のページのURLを取得する。なければNoneを返す"""
    soup = BeautifulSoup(html, "html.parser")
    next_btn = soup.select_one("li.next a")
    if next_btn:
        next_href = next_btn["href"]
        # catalogue/page-X.html と page-X.html の両方に対応
        if next_href.startswith("catalogue/"):
            return "http://books.toscrape.com/" + next_href
        else:
            return "http://books.toscrape.com/catalogue/" + next_href
    return None

def get_all_books():
    """全ページをループして全書籍を取得する"""
    url = "http://books.toscrape.com"
    all_books = []
    page = 1

    while url:
        print(f"\n--- ページ {page} を取得中 ---")
        html = get_page(url)
        books = extract_books(html)
        all_books.extend(books)
        print(f"このページ: {len(books)}冊 / 累計: {len(all_books)}冊")

        url = get_next_url(html)
        page += 1
        time.sleep(1)

    return all_books

def save_to_csv(books, filename="books.csv"):
    """書籍データをCSVファイルに保存する"""
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "price", "rating"])
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