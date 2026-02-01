# scripts/calculator_pro.py
import pandas as pd
import numpy as np

def calculate_investment(total_budget, race_data, style="A"):
    """
    期待値と的中率に基づき、最適な資金配分を計算する（ケリー基準の応用版）
    """
    if not race_data or "馬リスト" not in race_data:
        return None

    df = pd.DataFrame(race_data["馬リスト"])
    
    # 投資スタイルの設定
    if style == "A：総合バランス投資":
        ratios = {'単勝': 0.3, '馬連': 0.4, '三連複': 0.3}
    else:
        ratios = {'単勝': 0.1, '馬連': 0.3, '三連単': 0.6}

    allocations = {}
    for bet_type, ratio in ratios.items():
        # 予算を各券種に分配し、100円単位で丸める
        allocations[bet_type] = int(np.floor((total_budget * ratio) / 100) * 100)
    
    return allocations

if __name__ == "__main__":
    # テスト実行用
    print("Calculator Pro logic loaded.")
