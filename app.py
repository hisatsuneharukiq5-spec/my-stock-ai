import streamlit as st
import google.generativeai as genai
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- 1. 初期設定 (エラー回避設定) ---
# モデル名を修正（404エラー対策）
MODEL_NAME = "gemini-1.5-flash"

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("APIキーが設定されていません。")

# --- 2. データ取得関数 ---
def get_stock_data(ticker_code):
    ticker_symbol = f"{ticker_code}.T"
    stock = yf.Ticker(ticker_symbol)
    
    try:
        info = stock.info
        hist = stock.history(period="6mo")
    except:
        info, hist = {}, pd.DataFrame()
        
    # ニュースが取れない場合は、空のリストを返す
    news_list = []
    try:
        raw_news = stock.news
        if raw_news:
            for n in raw_news:
                title = n.get('title') or n.get('description')
                if title:
                    news_list.append({"title": title, "link": n.get('link', '#')})
    except:
        pass
        
    return info, hist, news_list

# --- 3. AI掲示板・まとめサイト風分析 ---
def analyze_with_ai(info, news):
    try:
        # 404エラー対策：モデルの取得方法を変更
        model = genai.GenerativeModel(model_name=MODEL_NAME)
        
        # ニュースがない場合のプロンプト調整
        news_context = ""
        if news:
            for n in news[:3]:
                news_context += f"・{n['title']}\n"
        else:
            news_context = "（現在、速報ニュースは入っていません。株価推移と指標から推測してください）"

        prompt = f"""
        あなたは、株のまとめサイト「株速報アンテナ」の管理人、および掲示板のベテラン住民です。
        以下のデータを元に、ネット上の投資家たちが今どのような雰囲気でこの株を語っているか、
        「リアルな書き込み」をシミュレーションして分析してください。
        
        【銘柄】: {info.get('longName', '不明')} ({info.get('symbol', '---')})
        【現在値】: {info.get('currentPrice', '---')}円 (PER: {info.get('trailingPE', '---')}倍)
        【最新情報】: {news_context}
        
        以下の形式で「掲示板の熱量」を出力してください：
        
        ■ 掲示板での主な書き込み（再現）
        「期待派の書き込み（例：〇〇だから買い！）」
        「慎重派の書き込み（例：〇〇が不安…）」
        
        ■ まとめサイト的要約
        1. 【期待】住民が盛り上がっている好材料
        2. 【懸念】今、一番警戒されているリスク
        3. 【管理人結論】ズバリ、明日の投資スタンスは？
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI分析エラー: モデル名を変更して再試行してください。({e})"

# --- 4. メイン画面 (UI) ---
st.set_page_config(page_title="AI株価・世論アナライザー", layout="wide")
st.title("📈 AI株価・世論アナライザー")

ticker = st.text_input("証券コードを入力 (例: 7203)", max_chars=4)

if ticker:
    with st.spinner("データを取得中..."):
        info, hist, news = get_stock_data(ticker)
        
    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric("現在株価", f"{info.get('currentPrice', '---')} 円")
        st.write(f"**PER:** {info.get('trailingPE', '---')} 倍 / **利回り:** {info.get('dividendYield', 0)*100:.2f} %")
        st.write(f"**時価総額:** {info.get('marketCap', 0)//10**8:,} 億円")
        
    with col2:
        if not hist.empty:
            fig = go.Figure(data=[go.Scatter(x=hist.index, y=hist['Close'], mode='lines', line=dict(color='#00d1b2'))])
            fig.update_layout(height=250, margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- ニュース・掲示板エリア ---
    left, right = st.columns(2)
    
    with left:
        st.subheader("📢 最新トピック")
        if news:
            for n in news[:5]:
                st.markdown(f"🔗 [{n['title']}]({n['link']})")
        else:
            # ニュースが取れない時のための、まとめサイトへのリンクボタン
            st.info("Yahooニュース等から直接取得できませんでした。")
            st.write("▼ 外部のまとめ・掲示板で直接確認：")
            st.markdown(f"👉 [Yahoo掲示板で「{ticker}」を見る](https://finance.yahoo.co.jp/quote/{ticker}.T/bbs)")
            st.markdown(f"👉 [みんかぶで「{ticker}」のニュースを見る](https://minkabu.jp/stock/{ticker})")

    with right:
        st.subheader("💬 AI投資家掲示板（世論分析）")
        if st.button("掲示板の声を読み込む"):
            with st.spinner("スレッドを解析中..."):
                analysis = analyze_with_ai(info, news)
                st.markdown(analysis)
