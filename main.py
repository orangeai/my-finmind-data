import os, requests, json, math, pandas as pd, time
import yfinance as yf
from datetime import datetime, timedelta
import pytz

def safe_float(v):
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else round(f, 2)
    except (TypeError, ValueError):
        return None

def get_ticker_id(sid):
    """找出正確的 exchange 後綴（.TW 或 .TWO）"""
    for suffix in ['.TW', '.TWO']:
        ticker_id = f"{sid}{suffix}"
        df = yf.download(ticker_id, period="5d", interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        if not df.empty:
            return ticker_id
    return f"{sid}.TW"  # fallback

def fetch_data():
    token = os.getenv('FINMIND_TOKEN')
    if not token:
        raise EnvironmentError("❌ 請設定環境變數 FINMIND_TOKEN")

    stock_list = ["3030", "2330", "3443", "1815", "8358", "3661", "3529", "6643", "2395", "6526", "7734"]
    stocks = list(dict.fromkeys(stock_list))  # 去重並保持順序

    results = {}
    failed = []
    utc = pytz.utc

    for sid in stocks:
        print(f"📡 處理中: {sid}")
        try:
            # --- 1. 確認正確的交易所後綴 ---
            ticker_id = get_ticker_id(sid)
            print(f"   → 使用: {ticker_id}")

            # --- 2. Yahoo Finance 抓取 60 分K（最近 1 個月）---
            df_yf = yf.download(ticker_id, period="1mo", interval="60m", progress=False)
            if isinstance(df_yf.columns, pd.MultiIndex):
                df_yf.columns = df_yf.columns.droplevel(1)

            k60_list = []
            if not df_yf.empty:
                for dt, row in df_yf.iterrows():
                    o = safe_float(row['Open'])
                    h = safe_float(row['High'])
                    l = safe_float(row['Low'])
                    c = safe_float(row['Close'])
                    if None in (o, h, l, c):
                        continue  # 跳過含 NaN 的 K 棒
                    # 統一轉為 UTC timestamp
                    if dt.tzinfo is None:
                        dt = pytz.timezone('Asia/Taipei').localize(dt)
                    k60_list.append({
                        "time": int(dt.astimezone(utc).timestamp()),
                        "open": o, "high": h, "low": l, "close": c
                    })

            # --- 3. Yahoo Finance 抓取日K（最近 1 年）---
            df_daily = yf.download(ticker_id, period="1y", interval="1d", progress=False)
            if isinstance(df_daily.columns, pd.MultiIndex):
                df_daily.columns = df_daily.columns.droplevel(1)

            daily_list = []
            if not df_daily.empty:
                for dt, row in df_daily.iterrows():
                    o = safe_float(row['Open'])
                    h = safe_float(row['High'])
                    l = safe_float(row['Low'])
                    c = safe_float(row['Close'])
                    if None in (o, h, l, c):
                        continue
                    daily_list.append({
                        "date": dt.strftime('%Y-%m-%d'),
                        "open": o, "max": h, "min": l, "close": c
                    })

            # --- 4. FinMind 抓取籌碼（最近 180 天）---
            chip_list = []
            chip_start = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
            h_url = (
                f"https://api.finmindtrade.com/api/v4/data"
                f"?dataset=TaiwanStockHoldingSharesPer"
                f"&data_id={sid}&start_date={chip_start}&token={token}"
            )

            h_res = requests.get(h_url, timeout=10)
            h_res.raise_for_status()
            h_data = h_res.json()

            if h_data.get('msg') != 'success':
                print(f"⚠️ FinMind {sid}: {h_data.get('msg')}")
            else:
                df_h = pd.DataFrame(h_data.get('data', []))
                if not df_h.empty:
                    LEVELS_1000 = {'1,000,001以上'}
                    LEVELS_400  = {
                        '400,001-600,000', '600,001-800,000',
                        '800,001-1,000,000', '1,000,001以上'
                    }
                    for date, group in df_h.groupby('date'):
                        p1000 = group[group['HoldingSharesLevel'].isin(LEVELS_1000)]['percent'].sum()
                        p400  = group[group['HoldingSharesLevel'].isin(LEVELS_400)]['percent'].sum()
                        chip_list.append({
                            "time": date,
                            "p1000": round(float(p1000), 2),
                            "p400":  round(float(p400), 2)
                        })

            # --- 5. 籌碼斷路器 ---
            if not chip_list:
                chip_list = [{"time": datetime.now().strftime('%Y-%m-%d'), "p1000": 0, "p400": 0}]

            results[sid] = {
                "daily": daily_list,
                "k60":   k60_list[-50:],  # 取最近 50 根
                "chips": chip_list
            }

            time.sleep(0.8)  # 僅針對 FinMind API 限速

        except Exception as e:
            print(f"❌ {sid} 錯誤: {e}")
            failed.append(sid)

    # --- 6. 原子替換，避免寫入到一半時舊檔被破壞 ---
    tmp_path = 'data.json.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    os.replace(tmp_path, 'data.json')

    print(f"\n✅ data.json 更新完成")
    print(f"   成功: {len(results)} 支 | 失敗: {failed if failed else '無'}")

if __name__ == "__main__":
    fetch_data()
