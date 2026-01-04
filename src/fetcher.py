import requests
import pandas as pd
import time
from datetime import datetime, timedelta

def get_ohlcv(market, to_datetime, interval_min=5, count=200):
    """
    업비트 캔들 조회
    :param interval_min: 1, 3, 5, 10, 15, 30, 60, 240
    :param to_datetime: 기준 시간 (UTC 기준)
    """
    url = f"https://api.upbit.com/v1/candles/minutes/{interval_min}"
    
    # [최종 수정] T와 Z를 포함한 ISO 8601 포맷 사용
    # 이렇게 해야 업비트가 UTC 시간임을 정확히 인식합니다.
    if to_datetime is not None:
        to_str = to_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        to_str = ""
    
    headers = {"accept": "application/json"}
    params = {
        "market": market,
        "to": to_str,
        "count": count
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        
        if isinstance(data, list):
            df = pd.DataFrame(data)
            # candle_date_time_utc를 기준으로 정렬
            df = df.sort_values('candle_date_time_utc').reset_index(drop=True)
            
            # 숫자형 변환
            cols = ['opening_price', 'high_price', 'low_price', 'trade_price', 'candle_acc_trade_price']
            for c in cols:
                df[c] = df[c].astype(float)
                
            # 컬럼명 통일 (open, high, low, close, volume)
            # candle_date_time_utc를 'time' 컬럼으로 사용
            df.rename(columns={
                'opening_price': 'open',
                'high_price': 'high',
                'low_price': 'low',
                'trade_price': 'close',
                'candle_acc_trade_price': 'volume',
                'candle_date_time_utc': 'time'
            }, inplace=True)
            
            # 시간 컬럼 변환
            df['time'] = pd.to_datetime(df['time'])
            
            return df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        print(f"API Error: {e}")
        return pd.DataFrame()
