import os, requests, json, pandas as pd, time
from datetime import datetime, timedelta

def fetch_data():
    token = os.getenv('FINMIND_TOKEN')
    stocks = list(set(["3030", "2330", "3443", "1815", "8358", "3661", "3529", "6643", "2395", "6526", "7734"]))
    results = {}
    
    # 日期策略：縮短 Tick 天數以保證 API 成功回傳
    tick_start = (datetime.now() - timedelta(days=4)).strftime('%Y-%m-%d')
    daily_start = (datetime.now() - timedelta(days=200)).strftime('%Y-%m-%d')
    chip_start = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')

    for sid in stocks:
        try:
            # 1. 日K (最穩定的資料集)
            d_res = requests.get(f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id={sid}&start_date={daily_start}&token={token}").json()
            
            # 2. 逐筆 (合成60分K) - 若失敗則留空不中斷程式
            t_res = requests.get(f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPriceTick&data_id={sid}&start_date={tick_start}&token={token}").json()
            
            # 3. 籌碼 - 獲取歷史大戶比例
            h_res = requests.get(f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockHoldingSharesPer&data_id={sid}&start_date={chip_start}&token={token}").json()

            # --- 合成邏輯 (簡化以降低出錯率) ---
            df_tick = pd.DataFrame(t_res.get('data', []))
            k60_list = []
            if not df_tick.empty:
                df_tick['time'] = pd.to_datetime(df_tick['date'] + ' ' + df_tick['time'])
                df_tick.set_index('time', inplace=True)
                k = df_tick['deal_price'].resample('60T', closed='right', label='right').ohlc()
                v = df_tick['volume'].resample('60T', closed='right', label='right').sum()
                df_k = pd.concat([k, v], axis=1).dropna().reset_index()
                df_k['time'] = df_k['time'].view('int64') // 10**9
                k60_list = df_k.to_dict('records')

            # --- 籌碼處理 ---
            df_h = pd.DataFrame(h_res.get('data', []))
            chip_list = []
            if not df_h.empty:
                for date, group in df_h.groupby('date'):
                    p1000 = group[group['HoldingSharesLevel'] == '1,000,001以上']['percent'].sum()
                    p400 = group[group['HoldingSharesLevel'].isin(['400,001-600,000', '600,001-800,000', '800,001-1,000,000', '1,000,001以上'])]['percent'].sum()
                    chip_list.append({"time": date, "p1000": round(float(p1000), 2), "p400": round(float(p400), 2)})

            results[sid] = {
                "daily": d_res.get('data', []),
                "k60": k60_list,
                "chips": chip_list
            }
            time.sleep(1.5) # 強制休息，避免 403 報錯
        except:
            continue

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    fetch_data()
