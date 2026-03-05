import os, requests, json, pandas as pd
from datetime import datetime, timedelta
import time

def fetch_data():
    token = os.getenv('FINMIND_TOKEN')
    # 去重後的股票清單
    stocks = list(set(["3030", "2330", "3443", "1815", "8358", "3661", "3529", "6643", "2395", "6526", "7734"]))
    results = {}
    
    today = datetime.now().strftime('%Y-%m-%d')
    daily_start = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    tick_start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    chip_start = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')

    for sid in stocks:
        print(f"正在抓取: {sid}...")
        try:
            # 1. 日 K
            d_res = requests.get(f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id={sid}&start_date={daily_start}&token={token}").json()
            # 2. 60分 K (由 Tick 合成)
            t_res = requests.get(f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPriceTick&data_id={sid}&start_date={tick_start}&token={token}").json()
            # 3. 籌碼
            h_res = requests.get(f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockHoldingSharesPer&data_id={sid}&start_date={chip_start}&token={token}").json()

            # 合成 60分 K
            df_tick = pd.DataFrame(t_res.get('data', []))
            k60_list = []
            if not df_tick.empty:
                df_tick['time'] = pd.to_datetime(df_tick['date'] + ' ' + df_tick['time'])
                df_tick.set_index('time', inplace=True)
                k60 = df_tick['deal_price'].resample('60T', closed='right', label='right').ohlc()
                k60_vol = df_tick['volume'].resample('60T', closed='right', label='right').sum()
                df_k60 = pd.concat([k60, k60_vol], axis=1).dropna().reset_index()
                df_k60['time'] = df_k60['time'].view('int64') // 10**9
                k60_list = df_k60.to_dict('records')

            # 處理籌碼
            df_h = pd.DataFrame(h_res.get('data', []))
            chip_list = []
            if not df_h.empty:
                for d, g in df_h.groupby('date'):
                    c1000 = g[g['HoldingSharesLevel'] == '1,000,001以上']['percent'].sum()
                    c400 = g[g['HoldingSharesLevel'].isin(['400,001-600,000','600,001-800,000','800,001-1,000,000','1,000,001以上'])]['percent'].sum()
                    chip_list.append({"time": d, "p1000": round(c1000, 2), "p400": round(c400, 2)})

            results[sid] = {
                "daily": d_res.get('data', [])[-200:], # 取最近200天
                "k60": k60_list,
                "chips": chip_list
            }
            # 稍微停頓避免請求過快
            time.sleep(0.5)
        except Exception as e:
            print(f"抓取 {sid} 失敗: {e}")

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False)

if __name__ == "__main__":
    fetch_data()
