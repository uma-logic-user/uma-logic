import json
from pathlib import Path

def inspect():
    pred_file = Path("data/predictions_20260221.json")
    if not pred_file.exists():
        print("File not found")
        return
    with open(pred_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "races" not in data or not data["races"]:
        print("No races found")
        return
    race = data["races"][0]
    horses = race.get("horses") or race.get("predictions", [])
    if not horses:
        print("No horses found")
        return
    h = horses[0]
    print(f"Race ID: {race.get('race_id')}")
    print(f"Odds: {h.get('odds')}")
    print(f"オッズ: {h.get('オッズ')}")
    print(f"WinProb: {h.get('win_probability')}")
    print(f"EV: {h.get('expected_value')}")

if __name__ == '__main__':
    inspect()
