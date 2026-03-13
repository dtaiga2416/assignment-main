# ETT PoC Implementation

この課題では、`data/ETTh1.csv` を使って `OT` の1時間先予測を行う PoC を実装しています。

初学者向けに言うと、`過去のデータを使って、1時間後の値を当てられるか試す` 課題です。

## 課題の目的

- 目的変数は `OT`
- 予測対象は `T+1` 時点の `OT`
- 時刻 `T` までに観測できる情報だけを使って予測する
- データ分割は時系列順に `train=70%`, `valid=15%`, `test=15%`

## 今回やったこと

1. EDA
   - データ件数、期間、欠損値を確認
   - `OT` の分布や時系列の動きを確認
   - `OT` と他列の相関を確認
2. 特徴量作成
   - カレンダー特徴量
   - `OT` のラグ特徴量
   - `OT` の移動平均、移動標準偏差
   - 他センサ列の1時点ラグ
3. モデル比較
   - 平均値ベースライン
   - 直前値ベースライン
   - LinearRegression
   - Ridge
   - RandomForestRegressor
   - ExtraTreesRegressor
   - HistGradientBoostingRegressor

## 実行方法

Python 3.13 を想定しています。

```powershell
py -3.13 -m pip install -r requirements.txt
py -3.13 run_poc.py
py -3.13 generate_client_report.py
```

## 出力ファイル

- `outputs/metrics.csv`
- `outputs/test_predictions.csv`
- `outputs/feature_importance.csv`
- `outputs/eda_summary.json`
- `outputs/assumptions.json`
- `outputs/target_correlations.csv`
- `outputs/plots/*.png`
- `deliverables/athena_ot_poc_report.pptx`
- `deliverables/athena_ot_poc_report.pdf`
- `deliverables/technical_validation_summary.md`

## 読み方

- `eda_summary.json` でデータの基本情報を確認する
- `metrics.csv` でモデルの性能を比較する
- `technical_validation_summary.md` で全体の説明を読む
- スライド資料で発表用の要点を確認する
