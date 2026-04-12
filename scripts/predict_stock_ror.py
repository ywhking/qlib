import argparse
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import qlib
from qlib.log import get_module_logger
from qlib.utils import init_instance_by_config
from qlib.workflow import R

logger = get_module_logger("predict_stock_ror")


def predict_stock_ror(
    experiment_name: str,
    recorder_id: str,
    end_date: str,
    mlflow_uri: Optional[str] = None,
    provider_uri: Optional[str] = None,
    start_time: str = "2020-01-01",
    fit_start_time: str = "2020-01-01",
    fit_end_time: str = "2024-12-31",
    output_dir: str = ".",
) -> pd.DataFrame:
    """
    Use a trained model to predict stock returns.

    Parameters
    ----------
    experiment_name : str
        MLflow experiment name/ID.
    recorder_id : str
        MLflow recorder/run ID.
    end_date : str
        Prediction date (format: YYYY-MM-DD).
    mlflow_uri : str, optional
        MLflow tracking URI. Auto-detected if None.
    provider_uri : str, optional
        Qlib data provider URI. Defaults to ~/.qlib/qlib_data/akshare_data.
    start_time : str
        Start time for the prediction dataset handler.
    fit_start_time : str
        Fit start time for processor calibration.
    fit_end_time : str
        Fit end time for processor calibration.
    output_dir : str
        Directory to save prediction CSV files.

    Returns
    -------
    pd.DataFrame
        Prediction scores for all stocks.
    """

    if provider_uri is None:
        provider_uri = str(Path.home() / ".qlib" / "qlib_data" / "akshare_data")
    qlib.init(provider_uri=provider_uri, region="cn")
    logger.info(f"Qlib initialized, data path: {provider_uri}")

    if mlflow_uri is None:
        script_dir = Path(__file__).parent.parent
        mlflow_path = script_dir / "mlruns"
        mlflow_uri = f"file:{mlflow_path.resolve()}"

    logger.info(f"MLflow URI: {mlflow_uri}")
    R.set_uri(mlflow_uri)

    logger.info(f"Looking up experiment: {experiment_name}")
    try:
        experiments = R.list_experiments()
        available_exps = list(experiments.keys())

        if experiment_name not in available_exps:
            matching_exps = [e for e in available_exps if experiment_name in str(e)]
            if matching_exps:
                logger.warning(f"Matching experiments: {matching_exps}")
            raise ValueError(f"Experiment '{experiment_name}' not found. Available: {available_exps[:10]}")

        logger.info(f"Found experiment: {experiment_name}")

        exp = experiments[experiment_name]
        recorders = exp.list_recorders()
        logger.info(f"Recorders in experiment: {len(recorders)}")

        recorder_ids = set(recorders.keys())
        if recorder_id not in recorder_ids:
            raise ValueError(f"Recorder '{recorder_id}' not found. Available: {list(recorder_ids)[:10]}")

        logger.info(f"Found recorder: {recorder_id}")

    except Exception as e:
        logger.error(f"Error accessing experiment/recorder: {e}")
        logger.error(f"Current MLflow URI: {R.get_uri()}")
        raise

    logger.info("Loading model...")
    try:
        recorder = R.get_recorder(recorder_id=recorder_id, experiment_name=experiment_name)

        artifacts = recorder.list_artifacts()
        logger.info(f"Available artifacts: {artifacts}")

        model = recorder.load_object("model")
        logger.info("Model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise

    logger.info(f"Building prediction dataset for date: {end_date}")

    predict_dataset_config = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "Alpha158",
                "module_path": "qlib.contrib.data.handler",
                "kwargs": {
                    "start_time": start_time,
                    "end_time": end_date,
                    "fit_start_time": fit_start_time,
                    "fit_end_time": fit_end_time,
                    "instruments": "all",
                },
            },
            "segments": {"test": [end_date, end_date]},
        },
    }

    try:
        dataset = init_instance_by_config(predict_dataset_config)
        logger.info("Dataset built successfully")
    except Exception as e:
        logger.error(f"Failed to build dataset: {e}")
        raise

    logger.info("Running prediction...")
    try:
        pred_scores = model.predict(dataset, segment="test")
        logger.info(f"Prediction complete, {len(pred_scores)} stocks")
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise

    if isinstance(pred_scores, pd.Series):
        pred_scores = pred_scores.to_frame(name="score")

    if pred_scores.shape[1] == 1:
        pred_scores.columns = ["score"]

    pred_scores = pred_scores.dropna(subset=["score"])

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    full_output = output_path / f"prediction_{end_date}_full.csv"
    pred_scores.sort_values(by="score", ascending=False).to_csv(full_output, encoding="utf-8-sig")
    logger.info(f"Full results saved to: {full_output}")

    top10_stocks = pred_scores.sort_values(by="score", ascending=False).head(10)
    top10_output = output_path / f"prediction_{end_date}_top10.csv"
    top10_stocks.to_csv(top10_output, encoding="utf-8-sig")

    logger.info(f"Prediction date: {end_date}, stocks predicted: {len(pred_scores)}")
    logger.info(f"Top 10 stocks:\n{top10_stocks}")

    return pred_scores


def main():
    parser = argparse.ArgumentParser(description="Predict stock returns using a trained Qlib model")
    parser.add_argument("--experiment", default="workflow", help="MLflow experiment name/ID")
    parser.add_argument("--recorder-id", required=True, help="MLflow recorder/run ID")
    parser.add_argument("--end-date", required=True, help="Prediction date (YYYY-MM-DD)")
    parser.add_argument("--mlflow-uri", default=None, help="MLflow tracking URI")
    parser.add_argument("--provider-uri", default=None, help="Qlib data provider URI")
    parser.add_argument("--start-time", default="2020-01-01", help="Dataset start time")
    parser.add_argument("--fit-start-time", default="2020-01-01", help="Fit start time")
    parser.add_argument("--fit-end-time", default="2024-12-31", help="Fit end time")
    parser.add_argument("--output-dir", default=".", help="Output directory for CSV files")
    args = parser.parse_args()

    try:
        predict_stock_ror(
            experiment_name=args.experiment,
            recorder_id=args.recorder_id,
            end_date=args.end_date,
            mlflow_uri=args.mlflow_uri,
            provider_uri=args.provider_uri,
            start_time=args.start_time,
            fit_start_time=args.fit_start_time,
            fit_end_time=args.fit_end_time,
            output_dir=args.output_dir,
        )
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
