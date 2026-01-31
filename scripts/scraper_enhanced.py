#!/usr/bin/env python3
"""
netkeiba.com 強化版スクレイパー
回収率重視のため、過去成績・血統・調教データを徹底取得
"""

import re
import time
from datetime import datetime, timedelta, timezone
import requests
from bs4 import BeautifulSoup

JST = timezone(timedelta(hours=9))
NETKEIBA_BASE = "https://race.netkeiba.com"
DB_BASE = "https://db.netkeiba.com"


class EnhancedNetkeibaScraper:
    """強化版スクレイパー"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_today_race_list(self):
        """本日のレース一覧を取得"""
        today = datetime.now(JST)
        
        # netkeibaのカレンダーページ
        calendar_url = f"{NETKEIBA_BASE}/top/race_list.html"
        
        try:
            response = self.session.get(calendar_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            race_list = []
            race_links = soup.select('a[href*="/race/"]')
            
            for link in race_links:
                href = link.get('href', '')
                match = re.search(r'/race/(\d{12})', href)
                
                if match:
                    race_id = match.group(1)
                    venue_elem = link.find_previous('td', class_='venue')
                    venue = venue_elem.get_text(strip=True) if venue_elem else "不明"
                    race_num = int(race_id[-2:])
                    
                    race_list.append({
                        "race_id": race_id,
                        "venue": venue,
                        "race_num": race_num
                    })
            
            return race_list
            
        except Exception as e:
            print(f"⚠️ レース一覧取得エラー: {e}")
            return []
    
    def get_race_detail(self, race_id):
        """
        個別レースの詳細情報を取得（強化版）
        - 基本情報
        - 各馬の過去成績
        - 血統情報
        - 調教データ
        """
        race_url = f"{NETKEIBA_BASE}/race/shutuba.html?race_id={race_id}"
        
        try:
            response = self.session.get(race_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # レース基本情報
            race_name = self._extract_race_name(soup, race_id)
            distance = self._extract_distance(soup)
            surface = self._extract_surface(soup)
            weather = self._extract_weather(soup)
            track_condition = self._extract_track_condition(soup)
            grade = self._extract_grade(soup)
            
            # 出馬表
            horses = []
            horse_rows = soup.select('.HorseList tbody tr')
            
            for row in horse_rows:
                try:
                    horse_data = self._extract_horse_basic(row)
                    
                    if horse_data:
                        # 馬IDを取得
                        horse_id = self._extract_horse_id(row)
                        
                        # 過去成績を取得
                        past_records = self.get_horse_past_records(horse_id)
                        horse_data["past_records"] = past_records
                        
                        # 血統情報を取得
                        pedigree = self.get_horse_pedigree(horse_id)
                        horse_data["pedigree"] = pedigree
                        
                        # 調教データを取得
                        training = self.get_training_data(race_id, horse_data["umaban"])
                        horse_data["training"] = training
                        
                        horses.append(horse_data)
                        
                        time.sleep(0.5)  # サーバー負荷軽減
                    
                except Exception as e:
                    print(f"  ⚠️ 馬データ取得エラー: {e}")
                    continue
            
            return {
                "race_id": race_id,
                "race_name": race_name,
                "distance": distance,
                "surface": surface,
                "weather": weather,
                "track_condition": track_condition,
                "grade": grade,
                "horses": horses
            }
            
        except Exception as e:
            print(f"⚠️ レース詳細取得エラー ({race_id}): {e}")
            return None
    
    def _extract_horse_basic(self, row):
        """馬の基本情報を抽出"""
        try:
            # 馬番
            umaban_elem = row.select_one('.Umaban')
            umaban = int(umaban_elem.get_text(strip=True)) if umaban_elem else 0
            
            # 枠番
            wakuban_elem = row.select_one('.Waku')
            wakuban = int(wakuban_elem.get_text(strip=True)) if wakuban_elem else 0
            
            # 馬名
            horse_name_elem = row.select_one('.HorseName a')
            horse_name = horse_name_elem.get_text(strip=True) if horse_name_elem else "不明"
            
            # 性齢
            sei_elem = row.select_one('.Barei')
            sei_age = sei_elem.get_text(strip=True) if sei_elem else "不明"
            
            # 斤量
            kinryo_elem = row.select_one('.Kinryo')
            kinryo = float(kinryo_elem.get_text(strip=True)) if kinryo_elem else 0.0
            
            # 騎手
            jockey_elem = row.select_one('.Jockey a')
            jockey = jockey_elem.get_text(strip=True) if jockey_elem else "不明"
            
            # 調教師
            trainer_elem = row.select_one('.Trainer a')
            trainer = trainer_elem.get_text(strip=True) if trainer_elem else "不明"
            
            # 馬体重
            weight_elem = row.select_one('.Weight')
            weight_text = weight_elem.get_text(strip=True) if weight_elem else "0(0)"
            weight, weight_diff = self._parse_weight(weight_text)
            
            # オッズ
            odds_elem = row.select_one('.Popular')
            odds = self._extract_odds(odds_elem.get_text(strip=True) if odds_elem else "0.0")
            
            return {
                "umaban": umaban,
                "wakuban": wakuban,
                "horse_name": horse_name,
                "sei_age": sei_age,
                "kinryo": kinryo,
                "jockey": jockey,
                "trainer": trainer,
                "weight": weight,
                "weight_diff": weight_diff,
                "odds": odds
            }
            
        except Exception as e:
            print(f"    ⚠️ 基本情報抽出エラー: {e}")
            return None
    
    def _extract_horse_id(self, row):
        """馬IDを抽出"""
        try:
            horse_link = row.select_one('.HorseName a')
            if horse_link:
                href = horse_link.get('href', '')
                match = re.search(r'/horse/(\d+)', href)
                if match:
                    return match.group(1)
        except:
            pass
        return None
    
    def get_horse_past_records(self, horse_id, limit=5):
        """
        馬の過去成績を取得（直近5走）
        """
        if not horse_id:
            return []
        
        try:
            url = f"{DB_BASE}/horse/{horse_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            records = []
            result_rows = soup.select('.db_h_race_results tbody tr')[:limit]
            
            for row in result_rows:
                try:
                    # 日付
                    date_elem = row.select_one('td:nth-child(1)')
                    date = date_elem.get_text(strip=True) if date_elem else ""
                    
                    # 着順
                    chakujun_elem = row.select_one('.Result')
                    chakujun_text = chakujun_elem.get_text(strip=True) if chakujun_elem else "0"
                    chakujun = int(re.sub(r'\D', '', chakujun_text)) if chakujun_text else 0
                    
                    # レース名
                    race_elem = row.select_one('td:nth-child(5) a')
                    race_name = race_elem.get_text(strip=True) if race_elem else ""
                    
                    # 距離
                    distance_elem = row.select_one('td:nth-child(15)')
                    distance_text = distance_elem.get_text(strip=True) if distance_elem else ""
                    
                    # 馬場
                    baba_elem = row.select_one('td:nth-child(14)')
                    baba = baba_elem.get_text(strip=True) if baba_elem else ""
                    
                    # タイム
                    time_elem = row.select_one('td:nth-child(18)')
                    race_time = time_elem.get_text(strip=True) if time_elem else ""
                    
                    records.append({
                        "date": date,
                        "chakujun": chakujun,
                        "race_name": race_name,
                        "distance": distance_text,
                        "baba": baba,
                        "time": race_time
                    })
                    
                except Exception as e:
                    continue
            
            return records
            
        except Exception as e:
            print(f"    ⚠️ 過去成績取得エラー: {e}")
            return []
    
    def get_horse_pedigree(self, horse_id):
        """
        血統情報を取得
        """
        if not horse_id:
            return {"father": "不明", "mother_father": "不明"}
        
        try:
            url = f"{DB_BASE}/horse/{horse_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 父
            father_elem = soup.select_one('.blood_table td:nth-child(1) a')
            father = father_elem.get_text(strip=True) if father_elem else "不明"
            
            # 母父
            mother_father_elem = soup.select_one('.blood_table td:nth-child(3) a')
            mother_father = mother_father_elem.get_text(strip=True) if mother_father_elem else "不明"
            
            return {
                "father": father,
                "mother_father": mother_father
            }
            
        except Exception as e:
            print(f"    ⚠️ 血統情報取得エラー: {e}")
            return {"father": "不明", "mother_father": "不明"}
    
    def get_training_data(self, race_id, umaban):
        """
        調教データを取得
        """
        try:
            url = f"{NETKEIBA_BASE}/race/oikiri.html?race_id={race_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 該当馬番の行を探す
            training_rows = soup.select('table tbody tr')
            
            for row in training_rows:
                umaban_elem = row.select_one('td:nth-child(2)')
                if umaban_elem and int(umaban_elem.get_text(strip=True)) == umaban:
                    # 調教タイム
                    time_elem = row.select_one('td:nth-child(7)')
                    training_time = time_elem.get_text(strip=True) if time_elem else "不明"
                    
                    # 調教評価
                    hyoka_elem = row.select_one('td:nth-child(8)')
                    hyoka = hyoka_elem.get_text(strip=True) if hyoka_elem else "不明"
                    
                    return {
                        "time": training_time,
                        "evaluation": hyoka
                    }
            
            return {"time": "不明", "evaluation": "不明"}
            
        except Exception as e:
            print(f"    ⚠️ 調教データ取得エラー: {e}")
            return {"time": "不明", "evaluation": "不明"}
    
    def get_race_result(self, race_id):
        """レース結果を取得"""
        result_url = f"{NETKEIBA_BASE}/race/result.html?race_id={race_id}"
        
        try:
            response = self.session.get(result_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 着順（1〜3着）
            results = {}
            result_rows = soup.select('.ResultList tbody tr')[:3]
            
            for i, row in enumerate(result_rows, 1):
                umaban_elem = row.select_one('.Umaban')
                wakuban_elem = row.select_one('.Waku')
                
                if umaban_elem:
                    results[f"result_{i}st" if i == 1 else f"result_{i}{'nd' if i == 2 else 'rd'}"] = int(umaban_elem.get_text(strip=True))
                    results[f"waku_{i}st" if i == 1 else f"waku_{i}{'nd' if i == 2 else 'rd'}"] = int(wakuban_elem.get_text(strip=True)) if wakuban_elem else 0
            
            # 払戻金
            payouts = self._extract_payouts(soup)
            
            return {
                **results,
                "payouts": payouts
            }
            
        except Exception as e:
            print(f"⚠️ 結果取得エラー ({race_id}): {e}")
            return None
    
    # ヘルパーメソッド
    def _extract_race_name(self, soup, race_id):
        elem = soup.select_one('.RaceName')
        return elem.get_text(strip=True) if elem else f"第{race_id[-2:]}レース"
    
    def _extract_distance(self, soup):
        elem = soup.select_one('.RaceData01')
        if elem:
            text = elem.get_text()
            match = re.search(r'(\d{4})m', text)
            return match.group(1) + "m" if match else "不明"
        return "不明"
    
    def _extract_surface(self, soup):
        elem = soup.select_one('.RaceData01')
        if elem:
            text = elem.get_text()
            if "芝" in text:
                return "芝"
            elif "ダート" in text or "ダ" in text:
                return "ダート"
        return "不明"
    
    def _extract_weather(self, soup):
        elem = soup.select_one('.Weather')
        if elem:
            text = elem.get_text(strip=True)
            if "晴" in text:
                return "晴"
            elif "曇" in text:
                return "曇"
            elif "雨" in text:
                return "雨"
        return "晴"
    
    def _extract_track_condition(self, soup):
        elem = soup.select_one('.TrackCondition')
        if elem:
            text = elem.get_text(strip=True)
            if "良" in text:
                return "良"
            elif "稍" in text:
                return "稍重"
            elif "重" in text:
                return "重"
            elif "不" in text:
                return "不良"
        return "良"
    
    def _extract_grade(self, soup):
        """グレード（G1/G2/G3/重賞）を抽出"""
        elem = soup.select_one('.RaceData01')
        if elem:
            text = elem.get_text()
            if "G1" in text or "GI" in text:
                return "G1"
            elif "G2" in text or "GII" in text:
                return "G2"
            elif "G3" in text or "GIII" in text:
                return "G3"
            elif "重賞" in text or "OP" in text:
                return "OP"
        return "一般"
    
    def _parse_weight(self, text):
        """馬体重をパース（例: 476(+4) → (476, 4)）"""
        match = re.search(r'(\d{3})\(([+-]?\d+)\)', text)
        if match:
            return int(match.group(1)), int(match.group(2))
        return 0, 0
    
    def _extract_odds(self, text):
        try:
            return float(text)
        except:
            return 0.0
    
    def _extract_payouts(self, soup):
        """払戻金を取得（全券種対応）"""
        payouts = {}
        payout_table = soup.select('.PayoutList tbody tr')
        
        for row in payout_table:
            ticket_elem = row.select_one('.Txt_C')
            payout_elem = row.select_one('.Payout')
            
            if ticket_elem and payout_elem:
                ticket_type = ticket_elem.get_text(strip=True)
                payout_text = payout_elem.get_text(strip=True).replace(',', '').replace('円', '')
                
                try:
                    payout = int(payout_text)
                    payouts[ticket_type] = payout
                except:
                    pass
        
        return payouts
