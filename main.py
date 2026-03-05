import os, requests, json, pandas as pd
from datetime import datetime, timedelta
import time

def fetch_data():
    token = os.getenv('FINMIND_TOKEN')
    # 確保所有你要的代號都在這裡
    stocks = ["3030", "2330", "3443", "1815", "8358", "3661", "3529", "6643", "2395", "6526", "7734"]
    results = {}
    
    # 設定時間點：確保 start_date 涵蓋足夠的天數（例如 10 天前）以避免假日導致 k60 空白
    today = datetime.now().strftime('%Y-%m-%d')
    start_date_tick = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    start_date_chip = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')

    for sid in set(stocks): # 使用 set 避免重複抓取 2330
        try:
            # 1. 抓取日 K
            d_res = requests.get(f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id={sid}&start_date={start_date_chip}&token={token}").json()
            
            # 2. 抓取逐筆並合成 60分 K (解決 k60 空白問題)
            t_res = requests.get(f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPriceTick&data_id={sid}&start_date={start_date_tick}&token={token}").json()
            
            # 3. 抓取大戶比例 (解決 chips 空白問題)
            h_res = requests.get(f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockHoldingSharesPer&data_id={sid}&start_date={start_date_chip}&token={token}").json()

            # --- 合成 60分 K ---
            df_tick = pd.DataFrame(t_res.get('data', []))
            k60_list = []
            if not df_tick.empty:
                df_tick['time'] = pd.to_datetime(df_tick['date'] + ' ' + df_tick['time'])
                df_tick.set_index('time', inplace=True)
                # 每 60 分鐘重新取樣
                k60 = df_tick['deal_price'].resample('60T', closed='right', label='right').ohlc()
                k60_vol = df_tick['volume'].resample('60T', closed='right', label='right').sum()
                df_k60 = pd.concat([k60, k60_vol], axis=1).dropna().reset_index()
                # 轉換為 Unix Timestamp 給網頁讀取
                df_k60['time'] = df_k60['time'].view('int64') // 10**9
                k60_list = df_k60.to_dict('records')

            # --- 處理籌碼 (千張大戶與 400 張) ---
            df_h = pd.DataFrame(h_res.get('data', []))
            chip_list = []
            if not df_h.empty:
                for date, group in df_h.groupby('date'):
                    p1000 = group[group['HoldingSharesLevel'] == '1,000,001以上']['percent'].sum()
                    p400 = group[group['HoldingSharesLevel'].isin(['400,001-600,000', '600,001-800,000', '800,001-1,000,000', '1,000,001以上'])]['percent'].sum()
                    chip_list.append({"time": date, "p1000": round(p1000, 2), "p400": round(p400, 2)})

            results[sid] = {
                "daily": d_res.get('data', [])[-200:], # 取最近 200 天日K
                "k60": k60_list[-20:],                  # 取最近 20 根 60分K
                "chips": chip_list                     # 完整的籌碼序列
            }
            time.sleep(0.5) # 避開 API 頻率限制
        except Exception as e:
            print(f"{sid} 抓取發生錯誤: {e}")

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False)

if __name__ == "__main__":
    fetch_data()
