import os
import sys
from pathlib import Path

import qlib
from qlib.utils import init_instance_by_config
from qlib.data import D
from qlib.contrib.model.gbdt import LGBModel
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord
import pandas as pd


def predict_stock_ror(experiment_name, recorder_id, end_date, mlflow_uri=None):
    """
    使用已训练的模型预测股票收益率

    Parameters
    ----------
    experiment_name : str
        MLflow experiment name/ID
    recorder_id : str
        MLflow recorder/run ID
    end_date : str
        预测日期 (格式: YYYY-MM-DD)
    mlflow_uri : str, optional
        MLflow tracking URI, 默认为 None (自动检测)
    """

    # 1. 初始化 Qlib
    qlib.init(
        provider_uri="C://Users//ywhki//.qlib//qlib_data//akshare_data", region="cn"
    )
    print(
        f"✅ Qlib 初始化成功，数据路径: C://Users//ywhki//.qlib//qlib_data//akshare_data"
    )

    # 2. 设置 MLflow URI（关键步骤）
    # 如果未提供，则使用脚本所在目录的 mlruns 文件夹
    if mlflow_uri is None:
        # 默认使用项目根目录下的 mlruns
        script_dir = Path(__file__).parent.parent  # scripts/../ = 项目根目录
        mlflow_path = script_dir / "mlruns"
        mlflow_uri = f"file:{mlflow_path.resolve()}"

    print(f"设置 MLflow URI: {mlflow_uri}")
    R.set_uri(mlflow_uri)

    # 3. 验证实验是否存在
    print(f"\n查找实验: {experiment_name}")
    try:
        experiments = R.list_experiments()
        available_exps = list(experiments.keys())
        print(f"可用实验: {experiments}")

        if experiment_name not in available_exps:
            print(f"\n⚠️ 警告: 实验 '{experiment_name}' 不在可用实验中!")
            print(f"前10个可用实验: {available_exps[:10]}")

            # 尝试查找匹配的实验（可能是数字ID）
            matching_exps = [e for e in available_exps if experiment_name in str(e)]
            if matching_exps:
                print(f"\n匹配的实验: {matching_exps}")

            raise ValueError(f"实验 '{experiment_name}' 不存在")
        else:
            print(f"✓ 找到实验: {experiment_name}")

            # 列出该实验下的 recorders
            exp = experiments[experiment_name]
            recorders = exp.list_recorders()
            print(f"  实验下的 recorders: {len(recorders)}")

            if recorder_id not in recorders:
                print(f"\n⚠️ 警告: Recorder '{recorder_id}' 不在该实验中!")
                print(f"可用 recorders: {list(recorders.keys())[:10]}")
                raise ValueError(f"Recorder '{recorder_id}' 不存在")
            else:
                print(f"✓ 找到 Recorder: {recorder_id}")

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print(f"当前 MLflow URI: {R.get_uri()}")
        print("\n可能的解决方案:")
        print("1. 检查 mlruns 文件夹路径是否正确")
        print("2. 确认训练脚本和预测脚本使用相同的工作目录")
        print("3. 手动指定 mlflow_uri 参数")
        raise

    # 4. 加载已训练好的模型
    print(f"\n加载模型...")
    try:
        recorder = R.get_recorder(
            recorder_id=recorder_id, experiment_name=experiment_name
        )

        # 首先列出所有可用的 artifacts，查看模型保存的名称
        print("\n查看可用的 artifacts:")
        artifacts = recorder.list_artifacts()
        print(f"Artifacts: {artifacts}")

        # 尝试加载模型
        model = recorder.load_object("model")  # 使用 load_object 加载模型
        print("✓ 模型加载成功")
    except Exception as e:
        print(f"\n❌ 加载模型失败: {e}")
        print("\n可能的原因:")
        print("- 模型文件未正确保存")
        print("- 模型保存时使用了不同的名称")
        print("- 可以尝试 recorder.list_artifacts() 查看可用 artifacts")

    # 5. 构建用于预测的数据集 (Dataset)
    print(f"\n构建预测数据集...")
    print(f"预测日期: {end_date}")

    predict_dataset_config = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "Alpha158",
                "module_path": "qlib.contrib.data.handler",
                "kwargs": {
                    "start_time": "2025-01-01",
                    "end_time": end_date,
                    "fit_start_time": "2015-01-01",
                    "fit_end_time": "2023-12-31",
                    "instruments": "all",
                },
            },
            "segments": {"prediction": [end_date, end_date]},
        },
    }

    try:
        dataset = init_instance_by_config(predict_dataset_config)
        print("✓ 数据集构建成功")
    except Exception as e:
        print(f"❌ 构建数据集失败: {e}")
        print("\n可能的原因:")
        print("- 数据路径不正确")
        print("- 预测日期范围内没有数据")
        print("- Alpha158 处理器配置错误")
        raise

    # 6. 执行预测
    print(f"\n执行预测...")
    try:
        pred_scores = model.predict(dataset, segment="prediction")
        print(f"✓ 预测完成，共 {len(pred_scores)} 只股票")
    except Exception as e:
        print(f"❌ 预测失败: {e}")
        raise

    # 7. 处理结果
    print(f"\n{'=' * 60}")
    print(f"预测日期：{end_date} (基于 {end_date} 的数据)")
    print(f"预测股票数量：{len(pred_scores)}")

    # 确保 pred_scores 是 DataFrame
    if isinstance(pred_scores, pd.Series):
        pred_scores = pred_scores.to_frame(name="score")

    # 重命名列为 'score'
    if pred_scores.shape[1] == 1:
        pred_scores.columns = ["score"]

    # 保存结果
    output_file = f"prediction_{end_date}.csv"
    top10_stocks = pred_scores.sort_values(by="score", ascending=False).head(10)
    top10_stocks.to_csv(output_file)
    print(f"\n结果已保存到: {output_file}")
    print(f"\nTop 10 预测收益率最高的股票:")
    print(top10_stocks)

    return


def main():
    # 配置信息
    EXPERIMENT_NAME = "workflow"
    RECORDER_ID = "ae459e4ae21d4fbbacaa1f57dc30ed51"  # 尝试第一个
    END_DATE = "2025-12-31"
    MLFLOW_URI = None  # 自动检测

    try:
        predict_stock_ror(EXPERIMENT_NAME, RECORDER_ID, END_DATE, MLFLOW_URI)
    except Exception as e:
        print(f"\n{'=' * 60}")
        print(f"程序执行失败: {e}")
        print(f"{'=' * 60}")
        sys.exit(1)


if __name__ == "__main__":
    main()
