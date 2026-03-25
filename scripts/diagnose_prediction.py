#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
诊断预测结果问题
检查训练数据和预测数据的分布
"""

import qlib
from qlib.workflow import R
from qlib.utils import init_instance_by_config
from pathlib import Path
import pandas as pd
import numpy as np
import sys


def diagnose_prediction(experiment_name, recorder_id):
    """
    诊断预测结果
    """
    print("=" * 70)
    print("预测结果诊断")
    print("=" * 70)

    # 初始化
    qlib.init(provider_uri="~/.qlib/qlib_data/akshare_data", region="cn")
    R.set_uri(f"file:{Path(__file__).parent.parent / 'mlruns'}")

    # 加载预测结果
    recorder = R.get_recorder(recorder_id=recorder_id, experiment_name=experiment_name)

    try:
        pred = recorder.load_object("pred.pkl")
        print(f"\n✓ 成功加载 pred.pkl")
    except:
        print(f"\n✗ 无法加载 pred.pkl")
        return

    # 检查预测结果
    print("\n" + "=" * 70)
    print("1. 预测结果 (pred.pkl) 分析")
    print("=" * 70)

    if isinstance(pred, pd.DataFrame):
        pred_series = pred.iloc[:, 0]
    else:
        pred_series = pred

    print(f"\n预测值统计:")
    print(f"  形状: {pred_series.shape}")
    print(f"  最小值: {pred_series.min():.6f}")
    print(f"  最大值: {pred_series.max():.6f}")
    print(f"  均值: {pred_series.mean():.6f}")
    print(f"  中位数: {pred_series.median():.6f}")
    print(f"  标准差: {pred_series.std():.6f}")
    print(f"  负值比例: {(pred_series < 0).mean() * 100:.2f}%")
    print(f"  正值比例: {(pred_series > 0).mean() * 100:.2f}%")

    # 分布直方图
    print(f"\n预测值分布:")
    hist, bins = np.histogram(pred_series.dropna(), bins=10)
    for i in range(len(hist)):
        print(f"  [{bins[i]:.4f}, {bins[i + 1]:.4f}): {hist[i]} 个")

    # 尝试加载 label.pkl
    print("\n" + "=" * 70)
    print("2. 真实标签 (label.pkl) 分析")
    print("=" * 70)

    try:
        label = recorder.load_object("label.pkl")
        print(f"\n✓ 成功加载 label.pkl")

        if isinstance(label, pd.DataFrame):
            label_series = label.iloc[:, 0]
        else:
            label_series = label

        print(f"\n标签值统计:")
        print(f"  形状: {label_series.shape}")
        print(f"  最小值: {label_series.min():.6f}")
        print(f"  最大值: {label_series.max():.6f}")
        print(f"  均值: {label_series.mean():.6f}")
        print(f"  中位数: {label_series.median():.6f}")
        print(f"  标准差: {label_series.std():.6f}")
        print(f"  负值比例: {(label_series < 0).mean() * 100:.2f}%")
        print(f"  正值比例: {(label_series > 0).mean() * 100:.2f}%")

        # 标签分布
        print(f"\n标签值分布:")
        hist, bins = np.histogram(label_series.dropna(), bins=10)
        for i in range(len(hist)):
            print(f"  [{bins[i]:.4f}, {bins[i + 1]:.4f}): {hist[i]} 个")

    except Exception as e:
        print(f"\n✗ 无法加载 label.pkl: {e}")

    # 分析可能原因
    print("\n" + "=" * 70)
    print("3. 问题分析")
    print("=" * 70)

    if pred_series.min() > 0:
        print("\n⚠️ 发现问题：预测值全是正值！")
        print("\n可能原因：")
        print("  1. Label 被错误地取绝对值或其他非负转换")
        print("  2. 模型过拟合（不太可能全是正值）")
        print("  3. 预测时数据预处理与训练时不一致")
        print("\n建议检查：")
        print("  - 训练时的 label 定义是否正确")
        print("  - 是否使用了错误的 label_shift")
        print("  - 数据处理器是否将 label 转换为正值")

    if pred_series.mean() > 1:
        print("\n⚠️ 预测均值大于1，这可能意味着：")
        print("  - Label 没有被转换为收益率（使用了价格而不是收益率）")
        print("  - 正确的 Label 应该是：Ref($close, -1)/$close - 1")
        print("    范围通常在 -0.2 ~ +0.2 之间")
        print(f"    但当前预测均值是 {pred_series.mean():.4f}")

    # 显示一些样本
    print("\n" + "=" * 70)
    print("4. 预测样本（前10个）")
    print("=" * 70)
    print(pred_series.head(10))


def main():
    if len(sys.argv) != 3:
        print("Usage: python diagnose_prediction.py <experiment_name> <recorder_id>")
        print("Example: python diagnose_prediction.py workflow your_recorder_id")
        sys.exit(1)

    experiment_name = sys.argv[1]
    recorder_id = sys.argv[2]

    diagnose_prediction(experiment_name, recorder_id)


if __name__ == "__main__":
    main()
