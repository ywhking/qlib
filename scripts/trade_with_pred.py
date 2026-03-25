#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基于 pred.pkl 生成每日交易信号
适用于实盘交易或模拟交易
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent))

import qlib
from qlib.data import D
from qlib.workflow import R
from qlib.utils import get_next_trading_date


def generate_trade_signals(experiment_name, recorder_id, topk=10, threshold=0.0):
    """
    从 pred.pkl 生成交易信号

    参数:
    -----------
    experiment_name: str
        实验名称
    recorder_id: str
        Recorder ID
    topk: int
        每天选择的股票数量
    threshold: float
        预测收益率阈值，低于此值不买入

    返回:
    -----------
    signals: pd.DataFrame
        交易信号，包含 date, instrument, signal(买入/卖出/持有), score
    """
    # 初始化
    qlib.init(provider_uri="~/.qlib/qlib_data/akshare_data", region="cn")

    # 加载预测
    R.set_uri(f"file:{Path(__file__).parent.parent / 'mlruns'}")
    recorder = R.get_recorder(recorder_id=recorder_id, experiment_name=experiment_name)
    pred_df = recorder.load_object("pred.pkl")

    print("=" * 70)
    print("预测数据信息")
    print("=" * 70)
    print(f"预测数据形状: {pred_df.shape}")
    print(f"\n前5行:\n{pred_df.head()}")

    # 确保 pred_df 是 Series 格式
    if isinstance(pred_df, pd.DataFrame):
        pred_df = pred_df.iloc[:, 0]

    # 获取日期范围
    dates = pred_df.index.get_level_values("datetime").unique()
    print(f"\n预测日期数量: {len(dates)}")
    print(f"日期范围: {dates.min()} ~ {dates.max()}")

    # 生成每日交易信号
    signals_list = []

    for date in dates:
        # 获取当日所有股票的预测分数
        day_pred = pred_df.loc[date].dropna()

        if len(day_pred) == 0:
            continue

        # 按分数排序
        day_pred_sorted = day_pred.sort_values(ascending=False)

        # 选择 topk 股票作为买入候选
        top_stocks = day_pred_sorted.head(topk)

        # 筛选超过阈值的
        buy_candidates = top_stocks[top_stocks > threshold]

        for stock, score in day_pred_sorted.items():
            signal_type = "HOLD"  # 默认持有

            if stock in buy_candidates.index:
                signal_type = "BUY"
            elif score < day_pred_sorted.median():  # 分数低于中位数卖出
                signal_type = "SELL"

            signals_list.append(
                {
                    "date": date,
                    "instrument": stock,
                    "signal": signal_type,
                    "score": score,
                    "rank": day_pred_sorted.index.get_loc(stock) + 1,
                }
            )

    signals = pd.DataFrame(signals_list)

    return signals


def print_trade_plan(signals, date=None):
    """
    打印交易计划

    参数:
    -----------
    signals: pd.DataFrame
        交易信号
    date: str or None
        指定日期，None 表示最新日期
    """
    if date is None:
        date = signals["date"].max()
    else:
        date = pd.Timestamp(date)

    day_signals = signals[signals["date"] == date]

    if len(day_signals) == 0:
        print(f"没有 {date} 的交易信号")
        return

    print("\n" + "=" * 70)
    print(f"交易计划 - {date}")
    print("=" * 70)

    # 买入信号
    buy_signals = day_signals[day_signals["signal"] == "BUY"].sort_values(
        "score", ascending=False
    )
    print(f"\n【买入】共 {len(buy_signals)} 只:")
    print(buy_signals[["instrument", "score", "rank"]].to_string(index=False))

    # 卖出信号
    sell_signals = day_signals[day_signals["signal"] == "SELL"].sort_values(
        "score", ascending=True
    )
    print(f"\n【卖出】共 {len(sell_signals)} 只 (显示前10只):")
    print(sell_signals.head(10)[["instrument", "score", "rank"]].to_string(index=False))

    # 统计
    print(f"\n【统计】")
    print(f"  总股票数: {len(day_signals)}")
    print(f"  买入: {len(buy_signals)}")
    print(f"  卖出: {len(sell_signals)}")
    print(f"  持有: {len(day_signals) - len(buy_signals) - len(sell_signals)}")
    print(f"  平均预测收益: {day_signals['score'].mean():.4f}")
    print(f"  最高预测收益: {day_signals['score'].max():.4f}")
    print(f"  最低预测收益: {day_signals['score'].min():.4f}")


def simulate_trading(signals, initial_capital=1000000, position_pct=0.95):
    """
    简单模拟交易（基于信号）

    注意: 这是简化版，没有考虑手续费、滑点、涨跌停等

    参数:
    -----------
    signals: pd.DataFrame
        交易信号
    initial_capital: float
        初始资金
    position_pct: float
        仓位比例
    """
    dates = sorted(signals["date"].unique())

    capital = initial_capital
    positions = {}  # 当前持仓
    trades = []  # 交易记录

    for date in dates:
        day_signals = signals[signals["date"] == date]

        # 卖出
        sell_signals = day_signals[day_signals["signal"] == "SELL"]
        for _, row in sell_signals.iterrows():
            stock = row["instrument"]
            if stock in positions:
                # 假设以收盘价卖出
                sell_value = positions[stock]["shares"] * positions[stock]["price"]
                capital += sell_value
                trades.append(
                    {
                        "date": date,
                        "instrument": stock,
                        "action": "SELL",
                        "value": sell_value,
                    }
                )
                del positions[stock]

        # 买入
        buy_signals = day_signals[day_signals["signal"] == "BUY"]
        if len(buy_signals) > 0:
            # 计算可用资金
            available = capital * position_pct / len(buy_signals)

            for _, row in buy_signals.iterrows():
                stock = row["instrument"]
                if stock not in positions:
                    # 简化：假设以某个价格买入（实际需要获取当日收盘价）
                    buy_price = 10.0  # 假设价格
                    shares = available / buy_price
                    positions[stock] = {"shares": shares, "price": buy_price}
                    capital -= available
                    trades.append(
                        {
                            "date": date,
                            "instrument": stock,
                            "action": "BUY",
                            "value": available,
                        }
                    )

    # 计算最终价值
    final_value = capital + sum(p["shares"] * p["price"] for p in positions.values())

    print("\n" + "=" * 70)
    print("模拟交易结果（简化版）")
    print("=" * 70)
    print(f"初始资金: {initial_capital:,.2f}")
    print(f"最终资金: {final_value:,.2f}")
    print(f"总收益: {final_value - initial_capital:,.2f}")
    print(f"收益率: {(final_value / initial_capital - 1) * 100:.2f}%")
    print(f"交易次数: {len(trades)}")

    return trades


def main():
    import sys

    if len(sys.argv) < 3:
        print("Usage: python trade_with_pred.py <experiment_name> <recorder_id> [date]")
        print(
            "Example: python trade_with_pred.py workflow_alpha158_extended 5daaf9d5590447269b3d087cbafe4549"
        )
        print(
            "Example: python trade_with_pred.py workflow_alpha158_extended 5daaf9d5590447269b3d087cbafe4549 2025-03-25"
        )
        sys.exit(1)

    experiment_name = sys.argv[1]
    recorder_id = sys.argv[2]
    target_date = sys.argv[3] if len(sys.argv) > 3 else None

    # 生成交易信号
    print("生成交易信号...")
    signals = generate_trade_signals(
        experiment_name=experiment_name,
        recorder_id=recorder_id,
        topk=10,  # 每天选10只
        threshold=0.0,  # 预测收益>0才买入
    )

    # 保存信号
    output_file = f"trade_signals_{experiment_name}.csv"
    signals.to_csv(output_file, index=False)
    print(f"\n✓ 交易信号已保存到: {output_file}")

    # 打印特定日期的交易计划
    print_trade_plan(signals, target_date)

    # 简单模拟（可选）
    # simulate_trading(signals)


if __name__ == "__main__":
    main()
