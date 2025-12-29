import re
import pandas as pd
from datetime import datetime
import os
import json

def parse_single_day_expi(acc_path, date_str):
    """
    [로그 파싱 버전 2.0]
    1. 단일 acc_log 파일에서 지표, 매수(bid), 매도(ask)를 모두 추출합니다.
    2. 매수 시점(BID PASS 7)의 지표를 보관했다가, 실제 주문(uuid bid)이 발생하면 매칭합니다.
    3. 최종 매도 결과(up/down/highest ask)가 나오면 데이터를 확정합니다.
    """
    
    clean_date_str = date_str[:10] # YYYY-MM-DD

    # 지표 추출용 정규식
    patterns = {
        'pass1_avg': re.compile(r'PASS 1 prevAccTradePrice12Avg\s+KRW.*\/ ([\d\.E\+\-]+)'),
        'pass1_cur': re.compile(r'PASS 1 targetVo\.getAccTradePrice1min\(\).*\/ ([\d\.E\+\-]+)'),
        'wideTrendAvg': re.compile(r'wideTrendAvg\s*:\s*([\d\.E\+\-]+)'),
        'wideTrendAvg2': re.compile(r'wideTrendAvg2\s*:\s*([\d\.E\+\-]+)'),
        'crossAvg': re.compile(r'BID crossAvg\s*:\s*([\d\.E\+\-]+)'),
        'trendAvg': re.compile(r'trendAvg\s*:\s*([\d\.E\+\-]+)'),
        'upRate': re.compile(r'BID upRate\s*:\s*([\d\.E\+\-]+)'),
        'fastRate': re.compile(r'fastRate\s*:\s*([\d\.E\+\-]+)'),
        'bid5_24h': re.compile(r'BID 5 targetVo\.getAccTradePrice24h\(\).*\/ ([\d\.E\+\-]+)'),
        'bid5_prev': re.compile(r'BID 5 prevAccTradePrice.*\/ ([\d\.E\+\-]+)'),
    }

    live_state = {}      # 각 마켓의 최신 지표 상태
    last_pass = {}       # 각 마켓의 마지막 PASS 7 스냅샷
    pending_trades = {}  # 매수 주문은 나갔으나 아직 매도되지 않은 거래 {market: data}
    final_data = []

    if not os.path.exists(acc_path): 
        return pd.DataFrame()

    with open(acc_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue

            # 1. 시간 추출
            time_match = re.search(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\]', line)
            if not time_match: continue
            
            try:
                current_dt = datetime.strptime(f"{clean_date_str} {time_match.group(1)}", "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                continue

            # 2. 마켓 추출 (거의 모든 중요 라인에 포함됨)
            market_match = re.search(r'(KRW-[A-Z0-9]+)', line)
            market = market_match.group(1) if market_match else None

            # 3. 지표 업데이트
            if market:
                if market not in live_state: live_state[market] = {}
                for key, pattern in patterns.items():
                    m = pattern.search(line)
                    if m:
                        try: live_state[market][key] = float(m.group(1))
                        except: pass

            # 4. PASS 7 시점 스냅샷 저장
            if 'BID PASS 7 minus 2 candles' in line and market:
                snapshot = live_state.get(market, {}).copy()
                snapshot['market'] = market
                snapshot['pass_time'] = current_dt
                
                # 비율 계산
                p1_c = snapshot.get('pass1_cur', 0)
                p1_a = snapshot.get('pass1_avg', 0)
                snapshot['PASS1_Ratio'] = p1_c / p1_a if p1_a != 0 else 0

                b5_p = snapshot.get('bid5_prev', 0)
                b5_24 = snapshot.get('bid5_24h', 0)
                snapshot['BID5_Ratio'] = b5_p / b5_24 if b5_24 != 0 else 0
                
                last_pass[market] = snapshot

            # 5. 매수 주문 (bid) 감지
            if '"side":"bid"' in line:
                try:
                    json_str = line.split(' - ')[-1]
                    order_data = json.loads(json_str)
                    mkt = order_data.get('market')
                    if mkt and mkt in last_pass:
                        trade_info = last_pass[mkt].copy()
                        trade_info['bid_time'] = current_dt
                        # JSON의 price는 설정값이므로, 나중에 나오는 실제 trade price를 선호함
                        trade_info['bid_price'] = float(order_data.get('price', 0))
                        pending_trades[mkt] = trade_info
                except: pass

            # 6. 실제 매수 가격 (bid trade price) 업데이트
            if 'bid trade price' in line and market:
                price_match = re.search(r'/\s*([\d\.]+)', line)
                if price_match and market in pending_trades:
                    pending_trades[market]['bid_price'] = float(price_match.group(1))

            # 7. 매도 결과 (up/down/highest ask) 감지
            ask_match = re.search(r'(up ask|down ask|highest ask)\s+(KRW-[A-Z0-9]+)', line)
            if ask_match:
                result_type = ask_match.group(1)
                mkt = ask_match.group(2)
                
                # 가격 추출 (가장 마지막 숫자)
                prices = re.findall(r'/\s*([\d\.]+)', line)
                ask_price = float(prices[-1]) if prices else 0
                
                if mkt in pending_trades:
                    trade = pending_trades.pop(mkt)
                    # ok, x, NB 형식 유지
                    if 'up' in result_type: trade['result'] = 'ok'
                    elif 'down' in result_type: trade['result'] = 'x'
                    else: trade['result'] = 'NB' # highest ask 등
                    
                    trade['ask_price'] = ask_price
                    trade['timestamp'] = current_dt
                    trade['date'] = clean_date_str
                    final_data.append(trade)

    if not final_data: return pd.DataFrame()

    result_df = pd.DataFrame(final_data)
    cols = ['date', 'timestamp', 'market', 'result', 'PASS1_Ratio', 'BID5_Ratio', 
            'wideTrendAvg', 'wideTrendAvg2', 'crossAvg', 'trendAvg', 'upRate', 'fastRate',
            'bid_price', 'ask_price']
    exist_cols = [c for c in cols if c in result_df.columns]
    return result_df[exist_cols]

def load_all_data(data_dir, date_list):
    all_dfs = []
    for date_str in date_list:
        # 다양한 로그 파일명 패턴 대응
        patterns = [
            f"acc_log.{date_str}.txt",
            f"acc_log.{date_str}.txt.log",
            f"acc_log.{date_str}.log"
        ]
        
        found = False
        for p in patterns:
            acc_path = os.path.join(data_dir, p)
            if os.path.exists(acc_path):
                df = parse_single_day_expi(acc_path, date_str)
                if not df.empty:
                    all_dfs.append(df)
                found = True
                break
    
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
