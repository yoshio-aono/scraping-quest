import requests
from bs4 import BeautifulSoup

def get_page(url):
    """指定したURLのHTMLを取得する"""
    response = requests.get(url)
    print(f"ステータスコード: {response.status_code}")
    return response.text

def extract_books(html):
    """HTMLから書籍データを抽出する"""
    soup = BeautifulSoup(html, "html.parser")
    books = []

    for article in soup.select("article.product_pod"):
        # タイトル
        title = article.select_one("h3 a")["title"]
        # 価格
        price = article.select_one("p.price_color").text.strip()
        # 星評価（Oneなど英語→数字に変換）
        rating_map = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
        rating_word = article.select_one("p.star-rating")["class"][1]
        rating = rating_map[rating_word]

        books.append({
            "title": title,
            "price": price,
            "rating": rating
        })

    return books

def main():
    url = "http://books.toscrape.com"
    html = get_page(url)
    books = extract_books(html)

    print(f"\n取得件数: {len(books)}冊\n")
    for book in books:
        print(f"タイトル: {book['title']}")
        print(f"価格:     {book['price']}")
        print(f"評価:     {book['rating']}星")
        print("---")

if __name__ == "__main__":
    main()