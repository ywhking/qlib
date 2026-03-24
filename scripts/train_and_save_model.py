#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基于 workflow_config_lightgbm_Alpha158_sina.yaml 的代码实现
增加了模型保存功能
"""

import qlib
from qlib.utils import init_instance_by_config, flatten_dict
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord, SigAnaRecord
from qlib.data.dataset.handler import DataHandlerLP
import pandas as pd


def train_and_save_model():
    """
    训练 LightGBM 模型并保存
    基于 examples/benchmarks/LightGBM/workflow_config_lightgbm_Alpha158_sina.yaml
    """

    # ========== 1. 初始化 Qlib ==========
    print("=" * 60)
    print("1. 初始化 Qlib")
    print("=" * 60)

    provider_uri = "~/.qlib/qlib_data/akshare_data"
    region = "cn"

    qlib.init(provider_uri=provider_uri, region=region)
    print(f"✓ Qlib 初始化完成")
    print(f"  Provider URI: {provider_uri}")
    print(f"  Region: {region}")

    # ========== 2. 配置参数 ==========
    print("\n" + "=" * 60)
    print("2. 配置参数")
    print("=" * 60)

    # 市场配置
    market = "all"
    benchmark = "SH000300"

    # 数据处理配置
    data_handler_config = {
        "start_time": "2015-01-01",
        "end_time": "2025-12-31",
        "fit_start_time": "2015-01-01",
        "fit_end_time": "2023-12-31",
        "instruments": market,
    }

    # LightGBM 模型配置
    model_config = {
        "class": "LGBModel",
        "module_path": "qlib.contrib.model.gbdt",
        "kwargs": {
            "loss": "mse",
            "colsample_bytree": 0.8879,
            "learning_rate": 0.2,
            "subsample": 0.8789,
            "lambda_l1": 205.6999,
            "lambda_l2": 580.9768,
            "max_depth": 8,
            "num_leaves": 210,
            "num_threads": 20,
        },
    }

    # 数据集配置
    dataset_config = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "Alpha158",
                "module_path": "qlib.contrib.data.handler",
                "kwargs": data_handler_config,
            },
            "segments": {
                "train": ["2015-01-01", "2023-12-31"],
                "valid": ["2024-01-01", "2024-12-31"],
                "test": ["2025-01-01", "2025-12-31"],
            },
        },
    }

    print(f"✓ 配置完成")
    print(f"  Market: {market}")
    print(f"  Benchmark: {benchmark}")

    # ========== 3. 初始化组件 ==========
    print("\n" + "=" * 60)
    print("3. 初始化组件")
    print("=" * 60)

    print("  - 初始化数据集...")
    dataset = init_instance_by_config(dataset_config)
    print("  ✓ 数据集初始化完成")

    print("  - 初始化模型...")
    model = init_instance_by_config(model_config)
    print("  ✓ 模型初始化完成")

    # ========== 4. 训练模型 ==========
    print("\n" + "=" * 60)
    print("4. 训练模型")
    print("=" * 60)

    # 完整的任务配置（用于日志记录）
    task_config = {
        "model": model_config,
        "dataset": dataset_config,
    }

    with R.start(experiment_name="workflow"):
        # 记录参数
        R.log_params(**flatten_dict(task_config))
        print("  ✓ 参数已记录到 MLflow")

        # 训练模型
        print("  - 开始训练 LightGBM 模型...")
        print("    这可能需要几分钟，请耐心等待...")
        model.fit(dataset)
        print("  ✓ 模型训练完成")

        # ========== 5. 保存模型（关键步骤）==========
        print("\n" + "=" * 60)
        print("5. 保存模型")
        print("=" * 60)

        # 保存模型对象，以便后续加载
        R.save_objects(**{"model": model})
        print("  ✓ 模型已保存为 artifact: 'model'")

        # 同时保存模型参数（兼容性）
        R.save_objects(**{"params.pkl": model})
        print("  ✓ 模型参数已保存为 artifact: 'params.pkl'")

        # 获取当前 recorder
        recorder = R.get_recorder()
        print(f"\n  实验信息:")
        print(f"    - Experiment ID: {recorder.experiment_id}")
        print(f"    - Recorder ID: {recorder.id}")

        # ========== 6. 生成预测和记录 ==========
        print("\n" + "=" * 60)
        print("6. 生成预测和记录")
        print("=" * 60)

        print("  - 生成信号记录...")
        sr = SignalRecord(model, dataset, recorder)
        sr.generate()
        print("  ✓ 信号记录已生成 (pred.pkl, label.pkl)")

        print("  - 生成信号分析记录...")
        sar = SigAnaRecord(recorder, ana_long_short=False, ann_scaler=252)
        sar.generate()
        print("  ✓ 信号分析记录已生成")

        # ========== 7. 完成 ==========
        print("\n" + "=" * 60)
        print("7. 训练完成！")
        print("=" * 60)

        print(f"\n✅ 模型已成功训练并保存！")
        print(f"\n关键信息:")
        print(f"  - Experiment Name: workflow")
        print(f"  - Experiment ID: {recorder.experiment_id}")
        print(f"  - Recorder ID: {recorder.id}")
        print(f"\n使用以下代码加载模型:")
        print(f"  from qlib.workflow import R")
        print(f"  R.set_uri('file://E:/myprojects/qlib/mlruns')")
        print(f"  recorder = R.get_recorder(")
        print(f"      recorder_id='{recorder.id}',")
        print(f"      experiment_name='workflow'")
        print(f"  )")
        print(f"  model = recorder.load_object('model')")

        return recorder.id


def main():
    """主函数"""
    try:
        recorder_id = train_and_save_model()
        print(f"\n{'=' * 60}")
        print(f"成功！Recorder ID: {recorder_id}")
        print(f"{'=' * 60}")
    except Exception as e:
        print(f"\n{'=' * 60}")
        print(f"训练失败: {e}")
        print(f"{'=' * 60}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
