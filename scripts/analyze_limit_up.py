#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证涨停票的特征分布
分析为什么模型会选中涨停票
"""

import qlib
from qlib.data import D
import pandas as pd
import numpy as np


def analyze_limit_up_features():
    """
    分析涨停票 vs 非涨停票的特征差异
    """
    print("=" * 70)
    print("涨停票特征分析")
    print("=" * 70)

    # 初始化
    qlib.init(provider_uri="~/.qlib/qlib_data/akshare_data", region="cn")

    # 获取某天的数据（示例：2025-01-02）
    date = "2025-01-02"

    # 获取关键特征
    instruments = D.instruments("all")
    fields = [
        "$close/$open",  # 当天涨跌幅
        "$high/$close",  # 最高价/收盘价
        "$low/$close",  # 最低价/收盘价
        "$close/$close",  # 收盘价/收盘价
        "$volume",  # 成交量
        "$amount",  # 成交额
        "$turnover",  # 换手率
    ]

    data = D.features(instruments, fields, start_time=date, end_time=date)
    data = data.droplevel(level=0)  # 去掉datetime层级

    # 识别涨停票（涨幅>9.5%，A股涨停约9.9-10%）
    data["is_limit_up"] = data["$close/$open"] > 1.095

    print(f"\n日期: {date}")
    print(f"总股票数: {len(data)}")
    print(f"涨停票数量: {data['is_limit_up'].sum()}")
    print(f"涨停比例: {data['is_limit_up'].mean() * 100:.2f}%")

    # 分析涨停票的特征分布
    print("\n" + "=" * 70)
    print("特征对比：涨停票 vs 非涨停票")
    print("=" * 70)

    limit_up = data[data["is_limit_up"]]
    normal = data[~data["is_limit_up"]]

    features_to_analyze = ["$close/$open", "$high/$close", "$low/$close", "$turnover"]

    for feat in features_to_analyze:
        print(f"\n{feat}:")
        print(f"  涨停票均值: {limit_up[feat].mean():.4f}")
        print(f"  非涨停票均值: {normal[feat].mean():.4f}")
        print(f"  涨停票中位数: {limit_up[feat].median():.4f}")
        print(f"  非涨停票中位数: {normal[feat].median():.4f}")

        # 统计显著性（简单判断）
        if limit_up[feat].mean() > normal[feat].mean() * 1.5:
            print(f"  ⚠️ 差异显著！涨停票明显高于非涨停票")

    # 关键发现
    print("\n" + "=" * 70)
    print("关键发现")
    print("=" * 70)

    high_close_ratio = limit_up["$high/$close"].mean()
    print(f"\n涨停票的 $high/$close 均值: {high_close_ratio:.4f}")
    print(f"理论涨停价比值: ~1.099 (ST股) 或 ~1.10 (普通股)")

    if high_close_ratio > 1.08:
        print(
            "✅ 验证: 涨停票的 $high/$close 接近涨停线，模型可以通过此特征识别涨停票！"
        )

    # 次日收益分析
    print("\n" + "=" * 70)
    print("涨停票次日收益分析")
    print("=" * 70)

    # 获取次日收益
    next_date = "2025-01-03"
    next_data = D.features(
        instruments, fields=["$close/$open"], start_time=next_date, end_time=next_date
    )
    next_data = next_data.droplevel(level=0)
    next_data.columns = ["next_day_return"]

    # 合并数据
    merged = data.join(next_data, how="inner")

    limit_up_next = merged[merged["is_limit_up"]]["next_day_return"] - 1
    normal_next = merged[~merged["is_limit_up"]]["next_day_return"] - 1

    print(
        f"涨停票次日收益均值: {limit_up_next.mean():.4f} ({limit_up_next.mean() * 100:.2f}%)"
    )
    print(
        f"非涨停票次日收益均值: {normal_next.mean():.4f} ({normal_next.mean() * 100:.2f}%)"
    )
    print(f"涨停票次日收益>0比例: {(limit_up_next > 0).mean() * 100:.2f}%")
    print(f"非涨停票次日收益>0比例: {(normal_next > 0).mean() * 100:.2f}%")

    if abs(limit_up_next.mean() - normal_next.mean()) < 0.01:
        print("\n⚠️ 重要发现: 涨停票次日收益与非涨停票无显著差异！")
        print("   模型不应该偏好涨停票，除非它通过特征'认出'了涨停票")


if __name__ == "__main__":
    analyze_limit_up_features()
