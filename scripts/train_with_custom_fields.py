#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
优化版：使用自定义 fields 训练 LightGBM 分类模型
优化点：
1. 标签改为未来5天收益率是否为正（降低噪声）
2. 模型超参数：降低学习率、减少叶子数、增加正则化、类别平衡
3. 特征中移除无意义的 $close/$close 项
4. 添加类别权重平衡
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
    优化：移除 $close/$close（恒为1），避免冗余信息
    """
    fields = []
    names = []

    # 1. 基础价格特征（归一化）- 去掉 $close/$close
    for field in ["open", "high", "low", "vwap"]:   # 去掉 close
        fields.append(f"${field}/$close")
        names.append(field.upper() + "0")
    # 补充 close 本身也可以作为特征，但不用除以自身，这里直接使用 $close
    fields.append("$close")
    names.append("CLOSE0")

    # 2. 历史价格（前5天）
    for d in range(1, 5):
        for field in ["open", "high", "low", "close"]:
            fields.append(f"Ref(${field}, {d})/$close")
            names.append(field.upper() + str(d))

    # 3. Volume 相关
    fields.append("$volume/($volume+1e-12)")
    names.append("VOLUME0")
    for d in range(1, 5):
        fields.append(f"Ref($volume, {d})/($volume+1e-12)")
        names.append(f"VOLUME{d}")

    # 4. Amount 成交额
    fields.append("$amount/($amount+1e-12)")
    names.append("AMOUNT0")
    for d in range(1, 5):
        fields.append(f"Ref($amount, {d})/($amount+1e-12)")
        names.append(f"AMOUNT{d}")

    # 5. Turnover 换手率
    fields.append("$turnover")
    names.append("TURNOVER0")
    for d in range(1, 5):
        fields.append(f"Ref($turnover, {d})")
        names.append(f"TURNOVER{d}")
    fields.append("Mean($turnover, 5)")
    names.append("TURNOVER_MA5")
    fields.append("Mean($turnover, 10)")
    names.append("TURNOVER_MA10")
    fields.append("Std($turnover, 5)")
    names.append("TURNOVER_STD5")

    # 6. Outstanding Share 流通股
    fields.append("$outstanding_share/($outstanding_share+1e-12)")
    names.append("OUTSTANDING0")
    for d in range(1, 3):
        fields.append(f"Ref($outstanding_share, {d})/($outstanding_share+1e-12)")
        names.append(f"OUTSTANDING{d}")

    # 7. 衍生特征 - 成交额/成交量 = 均价
    fields.append("$amount/($volume+1e-12)/$close")
    names.append("VWAP_CALC")

    # 8. 换手率变化
    fields.append("$turnover/Ref($turnover, 1)-1")
    names.append("TURNOVER_CHG")

    # 9. 量价关系
    fields.append("$volume*($close-$open)/($close+1e-12)")
    names.append("VOL_PRICE_MOM")

    # 10. K线特征
    fields += [
        "($close-$open)/$open",
        "($high-$low)/$open",
        "($close-$open)/($high-$low+1e-12)",
    ]
    names += ["KMID", "KLEN", "KMID2"]

    # 11. 滚动指标
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
    使用自定义 fields 训练 LightGBM 分类模型
    """

    print("=" * 70)
    print("优化版：使用自定义 Fields 训练 LightGBM 分类模型")
    print("Fields: $volume, $amount, $turnover, $outstanding_share")
    print("预测目标：未来5日收益率是否为正")
    print("=" * 70)

    qlib.init(provider_uri="~/.qlib/qlib_data/sina_data", region="cn")
    print("\n✓ Qlib 初始化完成")

    # ========== 2. 配置特征与标签 ==========
    print("\n" + "=" * 70)
    print("2. 配置自定义特征")
    print("=" * 70)

    feature_fields, feature_names = get_custom_feature_config()

    # 优化标签：未来5天收益率是否为正（使用 -6 表示未来第6天，-1 表示未来第1天）
    label_fields = ["(Ref($close, -6)/Ref($close, -1) - 1) > 0"]
    label_names = ["LABEL0"]

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

    # 数据处理器：横截面排名归一化 + 丢弃无效标签
    data_handler_config = {
        "start_time": "2019-01-01",
        "end_time": "2025-12-31",
        "instruments": "all",
        "data_loader": data_loader_config,
        "learn_processors": [
            {
                "class": "CSRankNorm",
                "module_path": "qlib.data.dataset.processor",
                "kwargs": {"fields_group": "feature"}
            },
            {
                "class": "DropnaLabel",
                "module_path": "qlib.data.dataset.processor"
            },
        ],
        "infer_processors": [
            {
                "class": "CSRankNorm",
                "module_path": "qlib.data.dataset.processor",
                "kwargs": {"fields_group": "feature"}
            },
        ],
        "shared_processors": [],
    }

    # 优化后的模型配置
    model_config = {
        "class": "LGBModel",
        "module_path": "qlib.contrib.model.gbdt",
        "kwargs": {
            "objective": "binary",          # 二分类
            "metric": "auc",                # 评估指标
            "boosting_type": "gbdt",
            "learning_rate": 0.05,          # 降低学习率
            "num_leaves": 64,               # 减小叶子数，防止过拟合
            "max_depth": 6,                 # 限制树深度
            "min_child_samples": 20,        # 叶子节点最小样本数
            "subsample": 0.8,               # 行采样
            "colsample_bytree": 0.8,        # 列采样
            "reg_alpha": 205.6999,          # L1 正则
            "reg_lambda": 580.9768,         # L2 正则
            "num_threads": 10,              # 并行线程数
            "early_stopping_rounds": 50,    # 早停轮数
            "verbose": -1,                  # 减少输出
            "class_weight": "balanced",     # 自动平衡类别权重
        },
    }

    # 数据集配置（仍使用单次划分，可根据需要改为 RollingDataset）
    dataset_config = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "DataHandlerLP",
                "module_path": "qlib.data.dataset.handler",
                "kwargs": data_handler_config,
            },
            "segments": {
                "train": ["2019-01-01", "2023-12-20"],
                "valid": ["2024-01-01", "2024-12-20"],
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

    sample_data = dataset.prepare("train")
    print(f"\n  训练数据信息:")
    print(f"    - 样本数: {len(sample_data)}")
    print(f"    - 特征数: {sample_data.shape[1] - 1}")
    print(f"    - 特征名: {list(sample_data.columns[:5])} ...")

    # 统计标签分布
    if 'LABEL0' in sample_data.columns:
        pos_ratio = sample_data['LABEL0'].mean()
        print(f"    - 正样本比例: {pos_ratio:.4f}")

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
        R.log_params(**flatten_dict(task_config))
        print("  ✓ 参数已记录到 MLflow")

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

        # ========== 6. 生成预测和评估 ==========
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