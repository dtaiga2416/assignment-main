from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "ETTh1.csv"
OUTPUT_DIR = ROOT / "outputs"
PLOTS_DIR = OUTPUT_DIR / "plots"

TARGET_COLUMN = "OT"
TIMESTAMP_COLUMN = "date"
HORIZON = 1
TRAIN_RATIO = 0.7
VALID_RATIO = 0.15


@dataclass
class SplitData:
    train: pd.DataFrame
    valid: pd.DataFrame
    test: pd.DataFrame


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    PLOTS_DIR.mkdir(exist_ok=True)


def load_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=[TIMESTAMP_COLUMN])
    df = df.sort_values(TIMESTAMP_COLUMN).reset_index(drop=True)
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    feature_df = df.copy()
    feature_df["target"] = feature_df[TARGET_COLUMN].shift(-HORIZON)

    feature_df["hour"] = feature_df[TIMESTAMP_COLUMN].dt.hour
    feature_df["dayofweek"] = feature_df[TIMESTAMP_COLUMN].dt.dayofweek
    feature_df["month"] = feature_df[TIMESTAMP_COLUMN].dt.month
    feature_df["is_weekend"] = feature_df["dayofweek"].isin([5, 6]).astype(int)

    for lag in [1, 2, 3, 6, 12, 24, 48]:
        feature_df[f"{TARGET_COLUMN}_lag_{lag}"] = feature_df[TARGET_COLUMN].shift(lag)

    for window in [3, 6, 12, 24]:
        rolled = feature_df[TARGET_COLUMN].rolling(window=window)
        feature_df[f"{TARGET_COLUMN}_rolling_mean_{window}"] = rolled.mean()
        feature_df[f"{TARGET_COLUMN}_rolling_std_{window}"] = rolled.std()

    sensor_columns = [
        column
        for column in feature_df.columns
        if column not in {TIMESTAMP_COLUMN, TARGET_COLUMN, "target"}
    ]
    for column in sensor_columns:
        feature_df[f"{column}_lag_1"] = feature_df[column].shift(1)

    feature_df = feature_df.dropna().reset_index(drop=True)
    return feature_df


def split_time_series(df: pd.DataFrame) -> SplitData:
    train_end = int(len(df) * TRAIN_RATIO)
    valid_end = int(len(df) * (TRAIN_RATIO + VALID_RATIO))
    return SplitData(
        train=df.iloc[:train_end].copy(),
        valid=df.iloc[train_end:valid_end].copy(),
        test=df.iloc[valid_end:].copy(),
    )


def rmse(y_true: pd.Series, y_pred: np.ndarray) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def smape(y_true: pd.Series, y_pred: np.ndarray) -> float:
    denominator = np.abs(y_true) + np.abs(y_pred)
    ratio = np.where(denominator == 0, 0.0, 2.0 * np.abs(y_pred - y_true) / denominator)
    return float(np.mean(ratio) * 100)


def evaluate_predictions(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": rmse(y_true, y_pred),
        "r2": float(r2_score(y_true, y_pred)),
        "smape": smape(y_true, y_pred),
    }


def extract_feature_importance(model_name: str, model: object, feature_columns: list[str]) -> pd.DataFrame:
    if hasattr(model, "feature_importances_"):
        scores = getattr(model, "feature_importances_")
        importance_type = "feature_importance"
    elif hasattr(model, "coef_"):
        scores = np.abs(np.ravel(getattr(model, "coef_")))
        importance_type = "abs_coefficient"
    else:
        return pd.DataFrame(columns=["model", "feature", "importance", "importance_type"])

    importance_df = pd.DataFrame(
        {
            "model": model_name,
            "feature": feature_columns,
            "importance": scores,
            "importance_type": importance_type,
        }
    )
    return importance_df.sort_values("importance", ascending=False).reset_index(drop=True)


def run_models(split_data: SplitData) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    feature_columns = [
        column
        for column in split_data.train.columns
        if column not in {TIMESTAMP_COLUMN, "target"}
    ]

    datasets = {
        "train": split_data.train,
        "valid": split_data.valid,
        "test": split_data.test,
    }

    x_train = split_data.train[feature_columns]
    y_train = split_data.train["target"]
    x_valid = split_data.valid[feature_columns]
    y_valid = split_data.valid["target"]
    x_test = split_data.test[feature_columns]
    y_test = split_data.test["target"]

    train_mean = float(y_train.mean())
    model_specs = {
        "mean_baseline": DummyRegressor(strategy="mean"),
        "last_value_baseline": DummyRegressor(strategy="constant", constant=train_mean),
        "linear_regression": LinearRegression(),
        "ridge": Ridge(alpha=1.0),
        "random_forest": RandomForestRegressor(
            n_estimators=200,
            max_depth=10,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        ),
        "extra_trees": ExtraTreesRegressor(
            n_estimators=300,
            max_depth=12,
            min_samples_leaf=3,
            random_state=42,
            n_jobs=-1,
        ),
        "hist_gradient_boosting": HistGradientBoostingRegressor(
            max_depth=8,
            learning_rate=0.05,
            max_iter=300,
            min_samples_leaf=30,
            random_state=42,
        ),
    }

    results: list[dict[str, float | str]] = []
    prediction_rows: list[pd.DataFrame] = []
    importance_rows: list[pd.DataFrame] = []

    for model_name, model in model_specs.items():
        if model_name == "last_value_baseline":
            valid_pred = split_data.valid[f"{TARGET_COLUMN}_lag_1"].to_numpy()
            test_pred = split_data.test[f"{TARGET_COLUMN}_lag_1"].to_numpy()
        else:
            model.fit(x_train, y_train)
            valid_pred = model.predict(x_valid)
            test_pred = model.predict(x_test)
            importance = extract_feature_importance(model_name, model, feature_columns)
            if not importance.empty:
                importance_rows.append(importance.head(15))

        for split_name, actual, pred in [
            ("valid", y_valid, valid_pred),
            ("test", y_test, test_pred),
        ]:
            metrics = evaluate_predictions(actual, pred)
            metrics["model"] = model_name
            metrics["split"] = split_name
            results.append(metrics)

        prediction_rows.append(
            pd.DataFrame(
                {
                    TIMESTAMP_COLUMN: split_data.test[TIMESTAMP_COLUMN].to_numpy(),
                    "actual": y_test.to_numpy(),
                    "prediction": test_pred,
                    "model": model_name,
                }
            )
        )

    return (
        pd.DataFrame(results),
        pd.concat(prediction_rows, ignore_index=True),
        pd.concat(importance_rows, ignore_index=True) if importance_rows else pd.DataFrame(),
    )


def save_eda_outputs(raw_df: pd.DataFrame, feature_df: pd.DataFrame) -> None:
    summary = {
        "rows": int(len(raw_df)),
        "columns": raw_df.columns.tolist(),
        "date_min": raw_df[TIMESTAMP_COLUMN].min().isoformat(),
        "date_max": raw_df[TIMESTAMP_COLUMN].max().isoformat(),
        "missing_values": raw_df.isna().sum().to_dict(),
        "target_mean": float(raw_df[TARGET_COLUMN].mean()),
        "target_std": float(raw_df[TARGET_COLUMN].std()),
        "target_min": float(raw_df[TARGET_COLUMN].min()),
        "target_max": float(raw_df[TARGET_COLUMN].max()),
    }
    (OUTPUT_DIR / "eda_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    corr = raw_df.drop(columns=[TIMESTAMP_COLUMN]).corr(numeric_only=True)
    corr[TARGET_COLUMN].sort_values(ascending=False).to_csv(
        OUTPUT_DIR / "target_correlations.csv",
        encoding="utf-8-sig",
    )

    sns.set_theme(style="whitegrid")

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(raw_df[TIMESTAMP_COLUMN], raw_df[TARGET_COLUMN], linewidth=0.8)
    ax.set_title("OT Time Series")
    ax.set_xlabel("Date")
    ax.set_ylabel("OT")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "ot_timeseries.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.histplot(raw_df[TARGET_COLUMN], kde=True, ax=ax)
    ax.set_title("OT Distribution")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "ot_distribution.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(corr, cmap="coolwarm", center=0, ax=ax)
    ax.set_title("Feature Correlation Heatmap")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "correlation_heatmap.png", dpi=150)
    plt.close(fig)

    hour_profile = raw_df.groupby(raw_df[TIMESTAMP_COLUMN].dt.hour)[TARGET_COLUMN].mean()
    fig, ax = plt.subplots(figsize=(8, 5))
    hour_profile.plot(kind="bar", ax=ax)
    ax.set_title("Average OT by Hour")
    ax.set_xlabel("Hour")
    ax.set_ylabel("Average OT")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "ot_by_hour.png", dpi=150)
    plt.close(fig)

    feature_df.head(200).to_csv(OUTPUT_DIR / "feature_preview.csv", index=False, encoding="utf-8-sig")


def save_prediction_plot(predictions: pd.DataFrame) -> None:
    best_model = (
        predictions.merge(
            pd.read_csv(OUTPUT_DIR / "metrics.csv"),
            on="model",
            how="left",
        )
        .query("split == 'test'")
        .sort_values("mae")
        .iloc[0]["model"]
    )
    plot_df = predictions[predictions["model"] == best_model].head(200)

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(plot_df[TIMESTAMP_COLUMN], plot_df["actual"], label="actual", linewidth=1.2)
    ax.plot(plot_df[TIMESTAMP_COLUMN], plot_df["prediction"], label="prediction", linewidth=1.2)
    ax.set_title(f"Test Predictions ({best_model})")
    ax.set_xlabel("Date")
    ax.set_ylabel("OT")
    ax.legend()
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "test_predictions.png", dpi=150)
    plt.close(fig)


def save_feature_importance_plot(importance_df: pd.DataFrame) -> None:
    if importance_df.empty:
        return

    model_priority = ["ridge", "linear_regression", "hist_gradient_boosting", "random_forest", "extra_trees"]
    selected_model = next(
        (model for model in model_priority if model in set(importance_df["model"])),
        importance_df.iloc[0]["model"],
    )
    plot_df = importance_df[importance_df["model"] == selected_model].head(10).iloc[::-1]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(plot_df["feature"], plot_df["importance"], color="#2F6BFF")
    ax.set_title(f"Top Features ({selected_model})")
    ax.set_xlabel("Importance")
    ax.set_ylabel("Feature")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "feature_importance.png", dpi=150)
    plt.close(fig)


def main() -> None:
    ensure_dirs()
    raw_df = load_dataset(DATA_PATH)
    feature_df = build_features(raw_df)
    split_data = split_time_series(feature_df)

    save_eda_outputs(raw_df, feature_df)

    metrics_df, predictions_df, importance_df = run_models(split_data)
    metrics_df = metrics_df.sort_values(["split", "mae"]).reset_index(drop=True)
    metrics_df.to_csv(OUTPUT_DIR / "metrics.csv", index=False, encoding="utf-8-sig")
    predictions_df.to_csv(OUTPUT_DIR / "test_predictions.csv", index=False, encoding="utf-8-sig")
    importance_df.to_csv(OUTPUT_DIR / "feature_importance.csv", index=False, encoding="utf-8-sig")

    save_prediction_plot(predictions_df)
    save_feature_importance_plot(importance_df)

    assumptions = {
        "dataset": "ETTh1",
        "target": TARGET_COLUMN,
        "forecast_horizon_hours": HORIZON,
        "train_ratio": TRAIN_RATIO,
        "valid_ratio": VALID_RATIO,
        "test_ratio": 1.0 - TRAIN_RATIO - VALID_RATIO,
        "note": "Features observed at time T are allowed when predicting OT at T+1.",
    }
    (OUTPUT_DIR / "assumptions.json").write_text(
        json.dumps(assumptions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("PoC run complete.")
    print(metrics_df.to_string(index=False))


if __name__ == "__main__":
    main()
