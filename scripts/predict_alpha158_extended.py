#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用扩展版 Alpha158 进行预测
"""

import sys
from pathlib import Path

import qlib
from qlib.utils import init_instance_by_config
from qlib.workflow import R
import pandas as pd


def predict_with_extended_alpha158(experiment_name, recorder_id, end_date):
    """
    使用 Alpha158 Extended 模型预测
    """

    # 1. 初始化
    print("=" * 70)
    print("Alpha158 Extended 预测")
    print("=" * 70)

    qlib.init(provider_uri="~/.qlib/qlib_data/akshare_data", region="cn")

    # 2. 设置 MLflow
    R.set_uri(f"file:{Path(__file__).parent.parent / 'mlruns'}")

    # 3. 加载模型
    print("\n加载模型...")
    recorder = R.get_recorder(recorder_id=recorder_id, experiment_name=experiment_name)
    model = recorder.load_object("model")
    print(f"✓ 模型加载成功 (Recorder: {recorder_id})")

    # 4. 构建预测数据集（使用相同的 Alpha158Extended）
    print(f"\n构建预测数据集 (预测日期: {end_date})...")

    # 关键：需要导入 Alpha158Extended 类
    from alpha158_extended import Alpha158Extended

    predict_dataset_config = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "Alpha158Extended",
                "module_path": "__main__",  # 或者 "scripts.alpha158_extended"
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

    dataset = init_instance_by_config(predict_dataset_config)
    print("✓ 数据集构建完成")

    # 5. 预测
    print("\n执行预测...")
    pred_scores = model.predict(dataset, segment="prediction")
    print(f"✓ 预测完成，共 {len(pred_scores)} 只股票")

    # 6. 处理结果
    print("\n" + "=" * 70)
    print("预测结果")
    print("=" * 70)

    # 排序
    pred_scores.columns = ["score"]
    result = pred_scores.sort_values(by="score", ascending=False)

    # 显示 Top 20
    print("\nTop 20 预测收益率最高的股票:")
    print(result.head(20))

    # 保存
    output_file = f"prediction_alpha158_extended_{end_date}.csv"
    result.to_csv(output_file)
    print(f"\n✓ 结果已保存到: {output_file}")

    # 统计
    print(f"\n预测统计:")
    print(f"  - 股票总数: {len(result)}")
    print(f"  - 平均预测收益: {result['score'].mean():.4f}")
    print(f"  - 最高预测收益: {result['score'].max():.4f}")
    print(f"  - 最低预测收益: {result['score'].min():.4f}")

    return result


def main():
    # 配置
    EXPERIMENT_NAME = "workflow_alpha158_extended"
    RECORDER_ID = "your_recorder_id_here"  # 替换为实际的 Recorder ID
    END_DATE = "2025-12-31"

    try:
        predict_with_extended_alpha158(EXPERIMENT_NAME, RECORDER_ID, END_DATE)
        return 0
    except Exception as e:
        print(f"\n✗ 预测失败: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
