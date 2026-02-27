---
description: 修正→保存→実行をワンフローで完了する自動適用ルール
---
# Auto-Apply & Auto-Run ワークフロー

// turbo-all

## ルール
1. コード修正は**直接ファイルに書き込み**、承認を待たない
2. 修正後は**即座にバックグラウンドで実行**（streamlit再起動、スクリプト実行等）
3. 「適用していいですか？」等の確認は**一切不要**
4. 完了後に「完了しました」とだけ報告する

## 実行フロー
1. ファイルを直接上書き保存
// turbo
2. 構文チェック: `python -c "import py_compile; py_compile.compile('対象ファイル', doraise=True)"`
// turbo
3. 必要に応じてStreamlit再起動: `Start-Process -FilePath "python" -ArgumentList "-m streamlit run app.py --server.port 8501" -WorkingDirectory "c:\Users\sayaka\OneDrive\Desktop\uma-logic-new" -WindowStyle Minimized`
// turbo
4. 「完了しました」と報告
