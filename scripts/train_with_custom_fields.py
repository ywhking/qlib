#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用自定义 fields（$volume, $amount, $turnover, $outstanding_share）的完整训练脚本
基于 workflow_config_lightgbm_Alpha158_sina.yaml 的正确实现
"""

import qlib
from qlib.utils import init_instance_by_config, flatten_dict
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord, SigAnaRecord
from qlib.data.dataset.loader import QlibDataLoader


def get_custom_feature_config():
    """
    使用自定义 fields 创建特征配置
    包含：原始价格数据 + 自定义 fields（volume, amount, turnover, outstanding_share）
    """
    # 基础价格特征（类似 Alpha158 的价格部分）
    fields = []
    names = []

    # 1. 基础价格特征（归一化）
    for field in ["open", "high", "low", "close", "vwap"]:
        fields.append(f"${field}/$close")  # 归一化到收盘价
        names.append(field.upper() + "0")

    # 2. 历史价格（前5天）
    for d in range(1, 5):
        for field in ["open", "high", "low", "close"]:
            fields.append(f"Ref(${field}, {d})/$close")
            names.append(field.upper() + str(d))

    # 3. 【关键】自定义 Fields - Volume 相关
    # 当日成交量归一化
    fields.append("$volume/($volume+1e-12)")
    names.append("VOLUME0")

    # 历史成交量（前5天）
    for d in range(1, 5):
        fields.append(f"Ref($volume, {d})/($volume+1e-12)")
        names.append(f"VOLUME{d}")

    # 4. 【关键】自定义 Fields - Amount 成交额
    fields.append("$amount/($amount+1e-12)")
    names.append("AMOUNT0")

    for d in range(1, 5):
        fields.append(f"Ref($amount, {d})/($amount+1e-12)")
        names.append(f"AMOUNT{d}")

    # 5. 【关键】自定义 Fields - Turnover 换手率 ⭐
    fields.append("$turnover")  # 当日换手率
    names.append("TURNOVER0")

    for d in range(1, 5):
        fields.append(f"Ref($turnover, {d})")
        names.append(f"TURNOVER{d}")

    # 换手率移动平均
    fields.append("Mean($turnover, 5)")
    names.append("TURNOVER_MA5")

    fields.append("Mean($turnover, 10)")
    names.append("TURNOVER_MA10")

    # 换手率标准差（波动）
    fields.append("Std($turnover, 5)")
    names.append("TURNOVER_STD5")

    # 6. 【关键】自定义 Fields - Outstanding Share 流通股
    fields.append("$outstanding_share/($outstanding_share+1e-12)")
    names.append("OUTSTANDING0")

    for d in range(1, 3):
        fields.append(f"Ref($outstanding_share, {d})/($outstanding_share+1e-12)")
        names.append(f"OUTSTANDING{d}")

    # 7. 衍生特征 - 成交额/成交量 = 均价
    fields.append("$amount/($volume+1e-12)/$close")
    names.append("VWAP_CALC")

    # 8. 衍生特征 - 换手率变化
    fields.append("$turnover/Ref($turnover, 1)-1")
    names.append("TURNOVER_CHG")

    # 9. 衍生特征 - 量价关系
    fields.append("$volume*($close-$open)/($close+1e-12)")
    names.append("VOL_PRICE_MOM")

    # 10. Alpha158 风格的技术指标
    # K线特征
    fields += [
        "($close-$open)/$open",
        "($high-$low)/$open",
        "($close-$open)/($high-$low+1e-12)",
    ]
    names += ["KMID", "KLEN", "KMID2"]

    # 滚动指标
    for window in [5, 10, 20]:
        fields += [
            f"Mean($close, {window})/$close",
            f"Std($close, {window})/$close",
            f"Ref($close, {window})/$close",
        ]
        names += [f"MA{window}", f"STD{window}", f"ROC{window}"]

    print(f"总特征数: {len(names)}")
    print(f"\n特征列表示例:")
    for i, (f, n) in enumerate(zip(fields[:10], names[:10])):
        print(f"  {i + 1}. {n}: {f}")
    print(f"  ... 共 {len(names)} 个特征")

    return fields, names


def train_with_custom_fields():
    """
    使用自定义 fields 训练模型
    """

    # ========== 1. 初始化 Qlib ==========
    print("=" * 70)
    print("使用自定义 Fields 训练 LightGBM 模型")
    print("Fields: $volume, $amount, $turnover, $outstanding_share")
    print("=" * 70)

    qlib.init(provider_uri="~/.qlib/qlib_data/akshare_data", region="cn")
    print("\n✓ Qlib 初始化完成")

    # ========== 2. 配置参数 ==========
    print("\n" + "=" * 70)
    print("2. 配置自定义特征")
    print("=" * 70)

    # 获取自定义特征
    feature_fields, feature_names = get_custom_feature_config()

    # 标签配置（预测次日收益率）
    label_fields = ["Ref($close, -2)/Ref($close, -1) - 1"]
    label_names = ["LABEL0"]

    # 构建 DataLoader 配置
    data_loader_config = {
        "class": "QlibDataLoader",
        "kwargs": {
            "config": {
                "feature": (feature_fields, feature_names),
                "label": (label_fields, label_names),
            },
            "freq": "day",
        },
    }

    # 数据处理器配置
    data_handler_config = {
        "start_time": "2015-01-01",
        "end_time": "2025-12-31",
        "fit_start_time": "2015-01-01",
        "fit_end_time": "2023-12-31",
        "instruments": "all",
        "data_loader": data_loader_config,
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
                "class": "DataHandlerLP",  # 使用基础 handler，不是 Alpha158
                "module_path": "qlib.data.dataset.handler",
                "kwargs": data_handler_config,
            },
            "segments": {
                "train": ["2015-01-01", "2023-12-31"],
                "valid": ["2024-01-01", "2024-12-31"],
                "test": ["2025-01-01", "2025-12-31"],
            },
        },
    }

    # ========== 3. 初始化组件 ==========
    print("\n" + "=" * 70)
    print("3. 初始化组件")
    print("=" * 70)

    print("  - 初始化数据集...")
    dataset = init_instance_by_config(dataset_config)
    print("  ✓ 数据集初始化完成")

    # 检查数据
    sample_data = dataset.prepare("train")
    print(f"\n  训练数据信息:")
    print(f"    - 样本数: {len(sample_data)}")
    print(f"    - 特征数: {sample_data.shape[1] - 1}")  # 减去 label
    print(f"    - 特征名: {list(sample_data.columns[:5])} ...")

    print("  - 初始化模型...")
    model = init_instance_by_config(model_config)
    print("  ✓ 模型初始化完成")

    # ========== 4. 训练模型 ==========
    print("\n" + "=" * 70)
    print("4. 训练模型")
    print("=" * 70)

    task_config = {
        "model": model_config,
        "dataset": dataset_config,
    }

    with R.start(experiment_name="workflow_custom_fields"):
        # 记录参数
        R.log_params(**flatten_dict(task_config))
        print("  ✓ 参数已记录到 MLflow")

        # 训练
        print("  - 开始训练 LightGBM...")
        print("    (使用包含 volume/amount/turnover/outstanding_share 的特征集)")
        model.fit(dataset)
        print("  ✓ 训练完成")

        # ========== 5. 保存模型 ==========
        print("\n" + "=" * 70)
        print("5. 保存模型")
        print("=" * 70)

        R.save_objects(**{"model": model})
        print("  ✓ 模型已保存")

        recorder = R.get_recorder()
        print(f"\n  实验信息:")
        print(f"    - Experiment: workflow_custom_fields")
        print(f"    - Recorder ID: {recorder.id}")

        # ========== 6. 生成记录 ==========
        print("\n" + "=" * 70)
        print("6. 生成预测和评估")
        print("=" * 70)

        sr = SignalRecord(model, dataset, recorder)
        sr.generate()
        print("  ✓ 信号记录已生成")

        sar = SigAnaRecord(recorder, ana_long_short=False, ann_scaler=252)
        sar.generate()
        print("  ✓ 信号分析已生成")

        # ========== 7. 完成 ==========
        print("\n" + "=" * 70)
        print("7. 训练完成!")
        print("=" * 70)

        print(f"\n✅ 模型训练成功！")
        print(f"\n使用了以下自定义 Fields:")
        print(f"  ✓ $volume - 成交量")
        print(f"  ✓ $amount - 成交额")
        print(f"  ✓ $turnover - 换手率 ⭐")
        print(f"  ✓ $outstanding_share - 流通股")
        print(f"\n关键信息:")
        print(f"  - Experiment Name: workflow_custom_fields")
        print(f"  - Recorder ID: {recorder.id}")
        print(f"\n预测时使用:")
        print(f"  EXPERIMENT_NAME = 'workflow_custom_fields'")
        print(f"  RECORDER_ID = '{recorder.id}'")

        return recorder.id


def main():
    try:
        recorder_id = train_with_custom_fields()
        print(f"\n{'=' * 70}")
        print(f"✓ 成功！Recorder ID: {recorder_id}")
        print(f"{'=' * 70}")
        return 0
    except Exception as e:
        print(f"\n{'=' * 70}")
        print(f"✗ 训练失败: {e}")
        print(f"{'=' * 70}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
