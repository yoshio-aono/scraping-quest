import requests
from bs4 import BeautifulSoup
import csv

def get_page(url):
    """指定したURLのHTMLを取得する"""
    response = requests.get(url)
    response.encoding = "utf-8"  # 文字化け修正
    print(f"ステータスコード: {response.status_code}")
    return response.text

def extract_books(html):
    """HTMLから書籍データを抽出する"""
    soup = BeautifulSoup(html, "html.parser")
    books = []

    for article in soup.select("article.product_pod"):
        # タイトル
        title = article.select_one("h3 a")["title"]
        # 価格（£記号と数字だけ取り出す）
        price_text = article.select_one("p.price_color").text.strip()
        price = float(price_text.replace("£", "").replace("Â", "").strip())
        # 星評価
        rating_map = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
        rating_word = article.select_one("p.star-rating")["class"][1]
        rating = rating_map[rating_word]

        books.append({
            "title": title,
            "price": price,
            "rating": rating
        })

    return books

def save_to_csv(books, filename="books.csv"):
    """書籍データをCSVファイルに保存する"""
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "price", "rating"])
        writer.writeheader()
        writer.writerows(books)
    print(f"\n{len(books)}冊のデータを {filename} に保存しました！")

def main():
    url = "http://books.toscrape.com"
    html = get_page(url)
    books = extract_books(html)

    print(f"\n取得件数: {len(books)}冊\n")
    for book in books:
        print(f"タイトル: {book['title']}")
        print(f"価格:     £{book['price']}")
        print(f"評価:     {book['rating']}星")
        print("---")

    save_to_csv(books)

if __name__ == "__main__":
    main()