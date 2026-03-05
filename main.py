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
            # --- 1. Yahoo Finance 抓取 K 線 ---
            ticker_id = f"{sid}.TW"
            # 60分K：下載最近 1 個月的資料
            df_yf = yf.download(ticker_id, period="1mo", interval="60m", progress=False)
            if df_yf.empty:
                ticker_id = f"{sid}.TWO"
                df_yf = yf.download(ticker_id, period="1mo", interval="60m", progress=False)

            k60_list = []
            if not df_yf.empty:
                # 關鍵修正：yfinance 的 Datetime 通常在 index
                for dt, row in df_yf.iterrows():
                    k60_list.append({
                        "time": int(dt.timestamp()), # 這裡 dt 就是 index 的時間物件
                        "open": round(float(row['Open']), 2),
                        "high": round(float(row['High']), 2),
                        "low": round(float(row['Low']), 2),
                        "close": round(float(row['Close']), 2)
                    })

            # 日K：下載最近 1 年的資料
            df_daily = yf.download(ticker_id, period="1y", interval="1d", progress=False)
            daily_list = []
            if not df_daily.empty:
                for dt, row in df_daily.iterrows():
                    daily_list.append({
                        "date": dt.strftime('%Y-%m-%d'),
                        "open": round(float(row['Open']), 2),
                        "max": round(float(row['High']), 2),
                        "min": round(float(row['Low']), 2),
                        "close": round(float(row['Close']), 2)
                    })

            # --- 2. FinMind 抓取籌碼 ---
            chip_list = []
            chip_start = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
            h_url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockHoldingSharesPer&data_id={sid}&start_date={chip_start}&token={token}"
            h_res = requests.get(h_url).json()
            
            df_h = pd.DataFrame(h_res.get('data', []))
            if not df_h.empty:
                for date, group in df_h.groupby('date'):
                    p1000 = group[group['HoldingSharesLevel'] == '1,000,001以上']['percent'].sum()
                    p400 = group[group['HoldingSharesLevel'].isin(['400,001-600,000','600,001-800,000','800,001-1,000,000','1,000,001以上'])]['percent'].sum()
                    chip_list.append({"time": date, "p1000": round(float(p1000), 2), "p400": round(float(p400), 2)})

            # --- 3. 籌碼斷路器 ---
            if not chip_list:
                chip_list = [{"time": datetime.now().strftime('%Y-%m-%d'), "p1000": 0, "p400": 0}]

            results[sid] = {
                "daily": daily_list,
                "k60": k60_list[-50:], # 取最近 50 根分K
                "chips": chip_list
            }
            time.sleep(1.2) # 穩定 API 請求頻率
            
        except Exception as e:
            print(f"❌ {sid} 錯誤: {e}")

    # 儲存檔案
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    print("✅ data.json 更新完成")

if __name__ == "__main__":
    fetch_data()
