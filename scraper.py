import requests
from bs4 import BeautifulSoup

def get_page(url):
    """指定したURLのHTMLを取得する"""
    response = requests.get(url)
    print(f"ステータスコード: {response.status_code}")
    return response.text

def main():
    url = "http://books.toscrape.com"
    html = get_page(url)
    print(html[:500])  # 最初の500文字だけ表示

if __name__ == "__main__":
    main()