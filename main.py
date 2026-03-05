import os, requests, json, pandas as pd, time
from datetime import datetime, timedelta

def fetch_data():
    token = os.getenv('FINMIND_TOKEN')
    # 核心股票清單
    stocks = ["3030", "2330", "3443", "1815", "8358", "3661", "3529", "6643", "2395", "6526", "7734"]
    results = {}
    
    # 1. 調整日期：Tick 抓最近 5 天即可 (避開單次筆數上限)，籌碼抓半年 (確保抓到週五)
    tick_start = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
    daily_start = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    chip_start = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')

    for sid in set(stocks):
        print(f"📡 正在強力抓取: {sid}...")
        try:
            # --- 抓取日 K ---
            d_res = requests.get(f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id={sid}&start_date={daily_start}&token={token}").json()
            daily_data = d_res.get('data', [])

            # --- 抓取逐筆並合成 60分 K (解決空值) ---
            t_res = requests.get(f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPriceTick&data_id={sid}&start_date={tick_start}&token={token}").json()
            df_tick = pd.DataFrame(t_res.get('data', []))
            
            k60_list = []
            if not df_tick.empty:
                df_tick['time'] = pd.to_datetime(df_tick['date'] + ' ' + df_tick['time'])
                df_tick.set_index('time', inplace=True)
                # 分 K 合成
                k60 = df_tick['deal_price'].resample('60T', closed='right', label='right').ohlc()
                k60_vol = df_tick['volume'].resample('60T', closed='right', label='right').sum()
                df_k = pd.concat([k60, k60_vol], axis=1).dropna().reset_index()
                df_k['time'] = df_k['time'].view('int64') // 10**9
                k60_list = df_k.to_dict('records')

            # --- 抓取籌碼 (解決空值) ---
            h_res = requests.get(f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockHoldingSharesPer&data_id={sid}&start_date={chip_start}&token={token}").json()
            df_h = pd.DataFrame(h_res.get('data', []))
            
            chip_list = []
            if not df_h.empty:
                # 只取每週最後一天的匯總
                for date, group in df_h.groupby('date'):
                    p1000 = group[group['HoldingSharesLevel'] == '1,000,001以上']['percent'].sum()
                    p400 = group[group['HoldingSharesLevel'].isin(['400,001-600,000', '600,001-800,000', '800,001-1,000,000', '1,000,001以上'])]['percent'].sum()
                    if p1000 > 0: # 確保不是無效數據
                        chip_list.append({"time": date, "p1000": round(float(p1000), 2), "p400": round(float(p400), 2)})

            # 存檔
            results[sid] = {
                "daily": daily_data[-200:], # 保留 200 天日 K
                "k60": k60_list[-30:],      # 保留 30 根分 K
                "chips": chip_list         # 完整的籌碼序列
            }
            time.sleep(1.2) # 為了穩定性，稍微延長間隔
            
        except Exception as e:
            print(f"❌ {sid} 失敗: {e}")

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    print("✅ 數據更新成功，請檢查 JSON!")

if __name__ == "__main__":
    fetch_data()
