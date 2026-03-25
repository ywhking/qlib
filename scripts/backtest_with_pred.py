#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基于 pred.pkl 进行回测交易
"""

import qlib
from qlib.constant import REG_CN
from qlib.data import D
from qlib.contrib.strategy import TopkDropoutStrategy
from qlib.contrib.evaluate import backtest
from qlib.workflow import R
from pathlib import Path
import pandas as pd


def backtest_with_pred(experiment_name, recorder_id):
    """
    使用 pred.pkl 进行回测
    """
    # 初始化
    qlib.init(provider_uri="~/.qlib/qlib_data/akshare_data", region=REG_CN)

    # 设置 MLflow
    R.set_uri(f"file:{Path(__file__).parent.parent / 'mlruns'}")

    # 加载预测结果
    recorder = R.get_recorder(recorder_id=recorder_id, experiment_name=experiment_name)
    pred_df = recorder.load_object("pred.pkl")

    print("预测数据预览:")
    print(pred_df.head())
    print(f"\n预测数据形状: {pred_df.shape}")
    print(
        f"预测日期范围: {pred_df.index.get_level_values('datetime').min()} ~ {pred_df.index.get_level_values('datetime').max()}"
    )

    # 配置策略
    # TopkDropoutStrategy: 选择 topk 只股票，每天更换 n_drop 只
    strategy = TopkDropoutStrategy(
        signal=pred_df,  # 直接使用预测作为信号
        topk=50,  # 持仓50只股票
        n_drop=5,  # 每天更换5只
        risk_degree=0.95,  # 使用95%的资金
        method_buy="top",  # 买入分数最高的
        method_sell="bottom",  # 卖出分数最低的
    )

    # 配置回测
    backtest_config = {
        "start_time": "2025-01-02",
        "end_time": "2025-03-25",
        "account": 100000000,  # 初始资金1亿
        "benchmark": "SH000300",  # 沪深300基准
        "exchange_kwargs": {
            "freq": "day",
            "limit_threshold": 0.095,  # 涨跌停限制
            "deal_price": "close",  # 收盘价成交
            "open_cost": 0.0005,  # 开仓手续费
            "close_cost": 0.0015,  # 平仓手续费
            "min_cost": 5,  # 最低手续费
        },
    }

    # 执行回测
    print("\n开始回测...")
    report = backtest(strategy=strategy, **backtest_config)

    # 输出结果
    print("\n" + "=" * 70)
    print("回测结果")
    print("=" * 70)

    # 收益率分析
    from qlib.contrib.evaluate import risk_analysis

    analysis = risk_analysis(report)
    print(analysis)

    return report, analysis


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python backtest_with_pred.py <experiment_name> <recorder_id>")
        print(
            "Example: python backtest_with_pred.py workflow_alpha158_extended 5daaf9d5590447269b3d087cbafe4549"
        )
        sys.exit(1)

    experiment_name = sys.argv[1]
    recorder_id = sys.argv[2]

    backtest_with_pred(experiment_name, recorder_id)
