#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
扩展 Alpha158，加入换手率、成交额等自定义特征
"""

# 训练脚本
def train_with_extended_alpha158():
    """
    使用扩展版 Alpha158 训练
    """
    import qlib
    from qlib.utils import init_instance_by_config, flatten_dict
    from qlib.workflow import R
    from qlib.workflow.record_temp import SignalRecord, SigAnaRecord

    print("=" * 70)
    print("Alpha158 Extended - 扩展版训练")
    print("=" * 70)

    # 初始化
    qlib.init(provider_uri="~/.qlib/qlib_data/akshare_data", region="cn")
    print("\n✓ Qlib 初始化完成")

    # 数据集配置 - 优化内存使用
    dataset_config = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "Alpha158Extended",
                "module_path": "qlib.contrib.data.handler",  # 当前文件
                "kwargs": {
                    "start_time": "2020-01-01",  # 缩短时间范围
                    "end_time": "2025-12-31",
                    "fit_start_time": "2020-01-01",
                    "fit_end_time": "2023-12-31",
                    "instruments": "all", 
                },
            },
            "segments": {
                "train": ["2020-01-01", "2023-12-31"],
                "valid": ["2024-01-01", "2024-12-31"],
                "test": ["2025-01-01", "2025-12-31"],
            },
        },
    }

    # LightGBM 配置
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

    # 初始化组件
    print("\n" + "=" * 70)
    print("2. 初始化组件")
    print("=" * 70)

    print("  - 初始化数据集...")
    dataset = init_instance_by_config(dataset_config)
    print("  ✓ 数据集初始化完成")

    # 检查特征
    sample = dataset.prepare("train")
    print(f"\n  数据信息:")
    print(f"    - 训练样本数: {len(sample)}")
    print(f"    - 特征数: {sample.shape[1] - 1}")  # 减去 label

    # 统计各类特征
    cols = list(sample.columns)
    turnover_cols = [c for c in cols if "TURNOVER" in c]
    amount_cols = [c for c in cols if "AMOUNT" in c]
    outstanding_cols = [c for c in cols if "OUTSTANDING" in c]

    print(f"\n  自定义特征统计:")
    print(f"    - 换手率相关: {len(turnover_cols)} 个")
    print(f"      示例: {turnover_cols[:5]}")
    print(f"    - 成交额相关: {len(amount_cols)} 个")
    print(f"      示例: {amount_cols[:5]}")
    print(f"    - 流通股相关: {len(outstanding_cols)} 个")

    print("  - 初始化模型...")
    model = init_instance_by_config(model_config)
    print("  ✓ 模型初始化完成")

    # 训练
    print("\n" + "=" * 70)
    print("3. 训练模型")
    print("=" * 70)

    with R.start(experiment_name="workflow_alpha158_extended"):
        model.fit(dataset)
        R.save_objects(**{"model": model})

        recorder = R.get_recorder()

        sr = SignalRecord(model, dataset, recorder)
        sr.generate()

        sar = SigAnaRecord(recorder, ana_long_short=False, ann_scaler=252)
        sar.generate()

        print("\n" + "=" * 70)
        print("4. 训练完成!")
        print("=" * 70)

        print(f"\n✅ 成功！")
        print(f"  - Experiment: workflow_alpha158_extended")
        print(f"  - Recorder ID: {recorder.id}")
        print(f"\n使用以下信息预测:")
        print(f"  EXPERIMENT_NAME = 'workflow_alpha158_extended'")
        print(f"  RECORDER_ID = '{recorder.id}'")

        return recorder.id


if __name__ == "__main__":
    try:
        rid = train_with_extended_alpha158()
        print(f"\n✓ Recorder ID: {rid}")
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback

        traceback.print_exc()
