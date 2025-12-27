# --- 4. EDINETから自動でPDFを探す関数 (クラウド対応・強化版) ---
def get_kessan_pdf(ticker_code):
    raw_code = str(ticker_code).strip()
    target_code = raw_code + "0" if len(raw_code) == 4 else raw_code
    
    # ブラウザからのアクセスに、より似せるための設定
    SECURE_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://disclosure.edinet-fsa.go.jp/"
    }

    # 検索範囲を直近30日に絞って負荷を減らす（ブロックされにくくする）
    for i in range(30):
        date = (datetime.date.today() - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"https://disclosure.edinet-fsa.go.jp/api/v1/documents.json?date={date}&type=2"
        try:
            # 1回ごとに少し待機（お役所サーバーを怒らせないため）
            time.sleep(0.5) 
            res = requests.get(url, headers=SECURE_HEADERS, timeout=15)
            
            if res.status_code == 200:
                data = res.json()
                for doc in data.get("results", []):
                    if target_code in str(doc.get("secCode", "")) and "決算短信" in str(doc.get("docDescription", "")):
                        doc_id = doc["docID"]
                        pdf_url = f"https://disclosure.edinet-fsa.go.jp/api/v1/documents/{doc_id}"
                        # PDF取得時も丁寧に待機
                        time.sleep(0.5)
                        pdf_res = requests.get(pdf_url, params={"type": 2}, headers=SECURE_HEADERS)
                        return pdf_res.content, doc["docDescription"]
            elif res.status_code == 403:
                return "BLOCKED", None
        except:
            continue
    return None, None
