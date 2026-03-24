#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Alpha158 + 换手率(Turnover)特征训练脚本

在原始 Alpha158 的 158 个特征基础上，增加换手率相关特征:
- TURN0: 当日换手率
- TURN1~TURN4: 前1-4日换手率
- TURN_MA5: 5日平均换手率
- TURN_STD5: 5日换手率标准差
- TURN_RATIO: 换手率/成交量比
"""

import qlib
from qlib.utils import init_instance_by_config, flatten_dict
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord, SigAnaRecord
import pandas as pd


def get_turnover_features():
    """
    定义换手率相关特征
    返回 (fields, names) 元组
    """
    fields = []
    names = []

    # 1. 原始换手率 (近5日)
    for i in range(5):
        if i == 0:
            fields.append("$turnover")
            names.append("TURN0")
        else:
            fields.append(f"Ref($turnover, {i})")
            names.append(f"TURN{i}")

    # 2. 移动平均换手率
    for window in [5, 10, 20]:
        fields.append(f"Mean($turnover, {window})")
        names.append(f"TURN_MA{window}")

    # 3. 换手率标准差 (波动性)
    for window in [5, 10, 20]:
        fields.append(f"Std($turnover, {window})")
        names.append(f"TURN_STD{window}")

    # 4. 换手率变化率
    fields.append("$turnover/Ref($turnover, 1)-1")
    names.append("TURN_CHG")

    # 5. 换手率/成交量比
    fields.append("$turnover/($volume+1e-12)*10000")
    names.append("TURN_VOL_RATIO")

    # 6. 相对历史位置的换手率
    fields.append("Rank($turnover, 20)")
    names.append("TURN_RANK20")

    return fields, names


def get_enhanced_alpha158_config():
    """
    获取增强版 Alpha158 配置，包含换手率特征
    """
    # 获取换手率特征
    turn_fields, turn_names = get_turnover_features()

    # 构建配置
    config = {
        "class": "QlibDataLoader",
        "kwargs": {
            "config": {
                "feature": {
                    "fields": turn_fields,
                    "names": turn_names,
                },
                "label": {
                    "fields": ["Ref($close, -2)/Ref($close, -1) - 1"],
                    "names": ["LABEL0"],
                },
            }
        },
    }

    return config


def train_alpha158_with_turnover():
    """
    训练 Alpha158 + 换手率模型
    """

    # ========== 1. 初始化 Qlib ==========
    print("=" * 60)
    print("Alpha158 + 换手率特征训练")
    print("=" * 60)

    qlib.init(provider_uri="~/.qlib/qlib_data/akshare_data", region="cn")
    print("✓ Qlib 初始化完成")

    # ========== 2. 配置参数 ==========
    print("\n" + "=" * 60)
    print("2. 配置参数")
    print("=" * 60)

    # 数据处理器配置
    data_handler_config = {
        "start_time": "2015-01-01",
        "end_time": "2025-12-31",
        "fit_start_time": "2015-01-01",
        "fit_end_time": "2023-12-31",
        "instruments": "all",
        # 使用自定义 DataLoader 配置
        "data_loader": get_enhanced_alpha158_config(),
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

    # 显示换手率特征
    turn_fields, turn_names = get_turnover_features()
    print(f"✓ 换手率特征数量: {len(turn_names)}")
    print(f"  特征列表:")
    for name, field in zip(turn_names, turn_fields):
        print(f"    - {name}: {field}")

    # ========== 3. 初始化组件 ==========
    print("\n" + "=" * 60)
    print("3. 初始化组件")
    print("=" * 60)

    print("  - 初始化数据集...")
    dataset = init_instance_by_config(dataset_config)
    print("  ✓ 数据集初始化完成")

    # 检查特征数量
    sample_data = dataset.prepare("train")
    print(f"  ✓ 训练数据特征数: {sample_data.shape[1]}")
    print(f"  ✓ 训练数据样本数: {len(sample_data)}")

    print("  - 初始化模型...")
    model = init_instance_by_config(model_config)
    print("  ✓ 模型初始化完成")

    # ========== 4. 训练模型 ==========
    print("\n" + "=" * 60)
    print("4. 训练模型")
    print("=" * 60)

    task_config = {
        "model": model_config,
        "dataset": dataset_config,
    }

    with R.start(experiment_name="workflow_turnover"):
        # 记录参数
        R.log_params(**flatten_dict(task_config))
        print("  ✓ 参数已记录")

        # 训练
        print("  - 开始训练...")
        model.fit(dataset)
        print("  ✓ 训练完成")

        # ========== 5. 保存模型 ==========
        print("\n" + "=" * 60)
        print("5. 保存模型")
        print("=" * 60)

        R.save_objects(**{"model": model})
        print("  ✓ 模型已保存")

        recorder = R.get_recorder()
        print(f"\n  实验信息:")
        print(f"    - Experiment: workflow_turnover")
        print(f"    - Recorder ID: {recorder.id}")

        # ========== 6. 生成预测和记录 ==========
        print("\n" + "=" * 60)
        print("6. 生成预测和记录")
        print("=" * 60)

        sr = SignalRecord(model, dataset, recorder)
        sr.generate()
        print("  ✓ 信号记录已生成")

        sar = SigAnaRecord(recorder, ana_long_short=False, ann_scaler=252)
        sar.generate()
        print("  ✓ 信号分析已生成")

        # ========== 7. 完成 ==========
        print("\n" + "=" * 60)
        print("7. 训练完成!")
        print("=" * 60)

        print(f"\n✅ 模型已成功训练并保存！")
        print(f"\n关键信息:")
        print(f"  - Experiment Name: workflow_turnover")
        print(f"  - Recorder ID: {recorder.id}")
        print(f"\n使用预测脚本时，请使用:")
        print(f"  EXPERIMENT_NAME = 'workflow_turnover'")
        print(f"  RECORDER_ID = '{recorder.id}'")

        return recorder.id


def main():
    try:
        recorder_id = train_alpha158_with_turnover()
        print(f"\n{'=' * 60}")
        print(f"成功！Recorder ID: {recorder_id}")
        print(f"{'=' * 60}")
        return 0
    except Exception as e:
        print(f"\n{'=' * 60}")
        print(f"训练失败: {e}")
        print(f"{'=' * 60}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
