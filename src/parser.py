import re
import pandas as pd
from datetime import datetime
import os

def parse_single_day_expi(acc_path, expi_path, date_str):
    """
    [결과 파싱 강화 버전]
    1. Expi Log: 마켓명 뒤에 숨어있는 ok, x, NB를 강력하게 찾아냅니다.
    2. Acc Log: PASS 7 시점의 지표 스냅샷을 뜹니다.
    3. Matching: 시간 순서대로 짝을 짓습니다.
    """
    
    clean_date_str = date_str[:10] # YYYY-MM-DD

    # --- 1. Expi 결과 파일 파싱 (여기가 수정됨) ---
    expi_events = []
    
    # 파일 경로 찾기
    real_expi_path = expi_path
    if not os.path.exists(real_expi_path):
        dir_name = os.path.dirname(acc_path)
        alt_path = os.path.join(dir_name, "Expi.txt")
        if os.path.exists(alt_path):
            real_expi_path = alt_path
    
    if os.path.exists(real_expi_path):
        with open(real_expi_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                
                # 시간 파싱
                time_match = re.search(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\]', line)
                # 마켓 파싱
                market_match = re.search(r'(KRW-[A-Z0-9]+)', line)
                
                if time_match and market_match:
                    time_str = time_match.group(1)
                    market = market_match.group(1)
                    
                    # [핵심 수정] 마켓명 뒤의 텍스트에서 결과 찾기
                    # 기존 정규식보다 훨씬 단순하고 강력하게 처리
                    result = "unknown"
                    
                    # 라인을 소문자로 바꿔서 ok, x, nb 찾기 (대소문자 무시)
                    lower_line = line.lower()
                    
                    # 마켓명 뒷부분만 잘라서 확인 (마켓명이 오탐되는 것 방지)
                    parts = lower_line.split(market.lower())
                    if len(parts) > 1:
                        suffix = parts[-1] # 마켓명 뒤에 있는 모든 글자
                        
                        # 우선순위: 명확한 단어부터 체크
                        if "ok" in suffix: result = "ok"
                        elif "nb" in suffix: result = "NB"
                        # x는 단어 단위로 체크 (ex라는 단어에 포함될 수 있으므로)
                        elif re.search(r'\bx\b', suffix): result = "x" 
                        elif "x" in suffix and len(suffix.strip()) < 5: result = "x" # 짧은 문장에 x 있으면 x로 간주

                    try:
                        dt = datetime.strptime(f"{clean_date_str} {time_str}", "%Y-%m-%d %H:%M:%S.%f")
                        expi_events.append({'expi_time': dt, 'market': market, 'result': result})
                    except ValueError:
                        continue

    # --- 2. Acc 로그 파싱 (PASS 7 스냅샷) ---
    if not os.path.exists(acc_path): return pd.DataFrame()

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

    live_state = {}
    entry_events = []

    with open(acc_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue

            time_match = re.search(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\]', line)
            if not time_match: continue
            
            try:
                current_dt = datetime.strptime(f"{clean_date_str} {time_match.group(1)}", "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                continue

            market_match = re.search(r'(KRW-[A-Z0-9]+)', line)
            if not market_match: continue
            market = market_match.group(1)

            if market not in live_state: live_state[market] = {}

            # 지표 업데이트
            for key, pattern in patterns.items():
                m = pattern.search(line)
                if m:
                    try: live_state[market][key] = float(m.group(1))
                    except: pass

            # 진입 트리거
            if 'BID PASS 7 minus 2 candles' in line:
                snapshot = live_state.get(market, {}).copy()
                snapshot['market'] = market
                snapshot['entry_time'] = current_dt
                
                # 비율 계산
                p1_c = snapshot.get('pass1_cur', 0)
                p1_a = snapshot.get('pass1_avg', 0)
                snapshot['PASS1_Ratio'] = p1_c / p1_a if p1_a != 0 else 0

                b5_p = snapshot.get('bid5_prev', 0)
                b5_24 = snapshot.get('bid5_24h', 0)
                snapshot['BID5_Ratio'] = b5_p / b5_24 if b5_24 != 0 else 0
                
                entry_events.append(snapshot)

    # --- 3. 매칭 로직 ---
    if not entry_events: return pd.DataFrame()
        
    df_entry = pd.DataFrame(entry_events)
    df_entry = df_entry.sort_values('entry_time')
    
    final_data = []

    for expi in expi_events:
        expi_t = expi['expi_time']
        mkt = expi['market']
        res = expi['result']
        
        # Expi 시간 이전에 발생한 해당 마켓의 PASS 찾기
        candidates = df_entry[
            (df_entry['market'] == mkt) & 
            (df_entry['entry_time'] < expi_t)
        ]
        
        if not candidates.empty:
            # 가장 최근의 PASS를 가져옴
            match = candidates.iloc[-1].to_dict()
            
            match['result'] = res
            match['timestamp'] = expi_t
            match['date'] = clean_date_str
            
            final_data.append(match)
            
    if not final_data: return pd.DataFrame()

    result_df = pd.DataFrame(final_data)
    
    # 보기 좋게 컬럼 정렬
    cols = ['date', 'timestamp', 'market', 'result', 'PASS1_Ratio', 'BID5_Ratio', 
            'wideTrendAvg', 'wideTrendAvg2', 'crossAvg', 'trendAvg', 'upRate', 'fastRate']
    exist_cols = [c for c in cols if c in result_df.columns]
    
    return result_df[exist_cols]

def load_all_data(data_dir, date_list):
    all_dfs = []
    for date_str in date_list:
        acc_file = os.path.join(data_dir, f"acc_log.{date_str}.txt")
        expi_file = os.path.join(data_dir, f"Expi.{date_str}.txt")
        
        if os.path.exists(acc_file):
            df = parse_single_day_expi(acc_file, expi_file, date_str)
            if not df.empty: all_dfs.append(df)
            
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()