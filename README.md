# 課題提出物

本リポジトリは、課題として実施した `ETTh1` データを用いた `OT` の1時間先予測 PoC の提出物です。  
提出先のご担当者様に確認いただくことを想定し、実装コード、分析結果、報告スライド PDF を含めています。

## 実施内容

今回の PoC では、時刻 `T` までに利用可能な情報を用いて、`T+1` の `OT` を予測できるかを検証しました。

- 使用データ: `data/ETTh1.csv`
- 目的変数: `OT`
- 予測対象: 1時間先の `OT`
- データ分割: `train 70% / valid 15% / test 15%`
- 比較モデル:
  - 平均値ベースライン
  - 直前値ベースライン
  - 線形回帰
  - Ridge
  - Random Forest
  - Extra Trees
  - HistGradientBoosting

## 主な提出物

- 実装コード: `run_poc.py`
- 実行に必要な依存関係: `requirements.txt`
- 分析結果:
  - `outputs/metrics.csv`
  - `outputs/test_predictions.csv`
  - `outputs/feature_importance.csv`
  - `outputs/eda_summary.json`
  - `outputs/target_correlations.csv`
  - `outputs/plots/*.png`
- クライアント向け報告スライド PDF: `報告スライド.pdf`

## 実行方法

Python 3.13 を想定しています。

```powershell
py -3.13 -m pip install -r requirements.txt
py -3.13 run_poc.py
```

上記を実行すると、`outputs/` 配下に評価結果と可視化ファイルが出力されます。

## 確認いただきたいポイント

- `run_poc.py`
  - データ読込、EDA、特徴量作成、モデル比較、評価までの一連の処理を実装しています。
- `outputs/metrics.csv`
  - モデルごとの性能比較結果です。
- `outputs/plots/test_predictions.png`
  - テストデータにおける実測値と予測値の比較です。
- `報告スライド.pdf`
  - クライアント向けに整理した PoC 報告資料です。

## 補足

本リポジトリでは、提出対象を明確にするため、作業途中で生成した補助資料や中間生成物は除外しています。  
必要な提出物は、上記の実装コード、分析出力、および報告スライド PDF です。
