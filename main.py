import os, requests, json, pandas as pd, time
import yfinance as yf
from datetime import datetime, timedelta

def fetch_data():
    token = os.getenv('FINMIND_TOKEN')
    stock_list = ["3030", "2330", "3443", "1815", "8358", "3661", "3529", "6643", "2395", "6526", "7734"]
    stocks = list(set(stock_list))
    results = {}

    for sid in stocks:
        print(f"📡 處理中: {sid}")
        try:
            # --- 1. Yahoo Finance 抓取 K 線 (穩定保證) ---
            ticker_id = f"{sid}.TW"
            df_yf = yf.download(ticker_id, period="1mo", interval="60m", progress=False)
            if df_yf.empty:
                ticker_id = f"{sid}.TWO"
                df_yf = yf.download(ticker_id, period="1mo", interval="60m", progress=False)

            k60_list = []
            if not df_yf.empty:
                df_yf = df_yf.reset_index()
                for _, row in df_yf.iterrows():
                    k60_list.append({
                        "time": int(row.iloc[0].timestamp()), # 修正 yfinance index 取值
                        "open": round(float(row['Open']), 2),
                        "high": round(float(row['High']), 2),
                        "low": round(float(row['Low']), 2),
                        "close": round(float(row['Close']), 2)
                    })

            df_daily = yf.download(ticker_id, period="1y", interval="1d", progress=False).reset_index()
            daily_list = []
            for _, row in df_daily.iterrows():
                daily_list.append({
                    "date": row['Date'].strftime('%Y-%m-%d'),
                    "open": round(float(row['Open']), 2),
                    "max": round(float(row['High']), 2),
                    "min": round(float(row['Low']), 2),
                    "close": round(float(row['Close']), 2)
                })

            # --- 2. FinMind 抓取籌碼 (增加防錯) ---
            chip_list = []
            # 這裡把日期拉長到 180 天，確保能抓到足夠的週五
            chip_start = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
            h_url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockHoldingSharesPer&data_id={sid}&start_date={chip_start}&token={token}"
            h_res = requests.get(h_url).json()
            
            df_h = pd.DataFrame(h_res.get('data', []))
            if not df_h.empty:
                for date, group in df_h.groupby('date'):
                    p1000 = group[group['HoldingSharesLevel'] == '1,000,001以上']['percent'].sum()
                    p400 = group[group['HoldingSharesLevel'].isin(['400,001-600,000','600,001-800,000','800,001-1,000,000','1,000,001以上'])]['percent'].sum()
                    chip_list.append({"time": date, "p1000": round(float(p1000), 2), "p400": round(float(p400), 2)})

            # --- 3. 籌碼斷路器：如果 API 沒資料，補一個最後已知的數值 (防止網頁報錯) ---
            if not chip_list:
                print(f"⚠️ {sid} 籌碼 API 無回傳")
                chip_list = [{"time": datetime.now().strftime('%Y-%m-%d'), "p1000": 0, "p400": 0}]

            results[sid] = {
                "daily": daily_list,
                "k60": k60_list[-50:], 
                "chips": chip_list
            }
            time.sleep(1.5) # 增加延遲，確保 API 安全
            
        except Exception as e:
            print(f"❌ {sid} 錯誤: {e}")

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    fetch_data()
