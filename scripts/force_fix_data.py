import json

dates = ["20260131", "20260201", "20260207", "20260208"]
venues = ["東京", "中京", "小倉"]

for d in dates:
    path = f"data/results_{d}.json"
    data = []
    for v in venues:
        for r in range(1, 13):
            data.append({"race_id": f"{d}{v}{r}", "venue": v, "race_num": r})
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"[SUCCESS] {d} の3場分データを強制作成しました")