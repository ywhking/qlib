#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用 Alpha158 进行预测
"""

import sys
from pathlib import Path

import qlib
from qlib.utils import get_date_by_shift, get_pre_trading_date, init_instance_by_config
from qlib.workflow import R
import pandas as pd


def predict_with_extented_alpha158(
    experiment_name,
    recorder_id,
    start_date,
    end_date,
    label_shift=-2,  # 默认T+1→T+2，传入-1则为T→T+1
):
    """
    使用 Alpha158Extented 模型预测
    """
    from qlib.data import D

    # 1. 初始化
    print("=" * 70)
    print("Alpha158Extented 预测")
    print("=" * 70)

    qlib.init(provider_uri="~/.qlib/qlib_data/akshare_data", region="cn")

    # 1.5 检查并修正日期范围
    calendar = D.calendar()
    last_available_date = calendar[-1]

    start_dt = pd.Timestamp(start_date)
    end_dt = pd.Timestamp(end_date)

    # 如果开始日期超出可用范围，报错
    if start_dt > last_available_date:
        raise ValueError(
            f"开始日期 {start_date} 超出了数据范围。"
            f"最新可用数据日期为: {last_available_date.strftime('%Y-%m-%d')}"
        )

    # 如果结束日期超出可用范围，自动修正
    if end_dt > last_available_date:
        print(f"⚠️ 警告: 结束日期 {end_date} 超出了数据范围。")
        print(f"   最新可用数据日期为: {last_available_date.strftime('%Y-%m-%d')}")
        end_date = last_available_date.strftime("%Y-%m-%d")
        print(f"   自动修正结束日期为: {end_date}")
        end_dt = last_available_date

    # 2. 设置 MLflow
    R.set_uri(f"file:{Path(__file__).parent.parent / 'mlruns'}")

    # 3. 加载模型
    print("\n加载模型...")
    recorder = R.get_recorder(recorder_id=recorder_id, experiment_name=experiment_name)
    model = recorder.load_object("model")
    print(f"✓ 模型加载成功 (Recorder: {recorder_id})")

    # 4. 构建预测数据集
    # 关键理解：
    # - Handler 加载特征数据日期（今天）
    # - Segments.prediction 指定要预测的日期（也是今天）
    # - 模型预测的是 T+1 收益率（明天）
    # 所以：handler_end_time 必须是今天（有数据），而不是明天

    # 获取最新可用数据日期
    from qlib.data import D

    calendar = D.calendar()
    last_data_date = calendar[-1]

    # 检查预测日期范围
    start_dt = pd.Timestamp(start_date)
    end_dt = pd.Timestamp(end_date)

    if end_dt > last_data_date:
        print(f"⚠️ 注意: 预测结束日期 {end_date} 是未来日期")
        print(f"   最新数据日期: {last_data_date.strftime('%Y-%m-%d')}")
        print(f"   将用今天({last_data_date.strftime('%Y-%m-%d')})的数据预测明天")
        # 将预测日期调整为最后一个有数据的日期
        prediction_end = last_data_date.strftime("%Y-%m-%d")
    else:
        prediction_end = end_date

    if start_dt > last_data_date:
        print(f"⚠️ 注意: 预测开始日期 {start_date} 也是未来日期")
        print(f"   将调整为: {last_data_date.strftime('%Y-%m-%d')}")
        prediction_start = last_data_date.strftime("%Y-%m-%d")
    else:
        prediction_start = start_date

    # Handler 加载到 prediction_end（今天），用于计算特征
    handler_start_time = get_date_by_shift(prediction_start, -120)
    handler_end_time = prediction_end  # Handler 必须有特征数据

    print(f"\n数据加载: {handler_start_time} 至 {handler_end_time}")
    print(f"预测日期: {prediction_start} 至 {prediction_end}")
    if label_shift == -1:
        print(f"   (即预测 {prediction_start}~{prediction_end} 的 T→T+1 收益率)")
        print(f"   建议: T日收盘前买入, T+1日收盘卖出")
    else:
        print(f"   (即预测 {prediction_start}~{prediction_end} 的 T+1→T+2 收益率)")
        print(f"   建议: T+1日开盘买入, T+2日收盘卖出")

    predict_dataset_config = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "Alpha158Extented",
                "module_path": "qlib.contrib.data.handler",
                "kwargs": {
                    "start_time": handler_start_time,
                    "end_time": handler_end_time,
                    "label_shift": label_shift,  # 传入label_shift
                    "fit_start_time": None,
                    "fit_end_time": None,
                    "instruments": "all",
                },
            },
            "segments": {"prediction": [prediction_start, prediction_end]},
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
    if isinstance(pred_scores, pd.Series):
        pred_scores = pred_scores.to_frame(name="score")
    else:
        pred_scores.columns = ["score"]

    # 🔴 关键修改：过滤涨停票（买不到）
    print("\n过滤涨停票...")
    from qlib.data import D

    # 获取预测日的涨跌幅
    pred_date_data = D.features(
        D.instruments("all"),
        fields=["$close/$open"],
        start_time=prediction_end,
        end_time=prediction_end,
    )
    pred_date_data = pred_date_data.droplevel(level=0)
    pred_date_data.columns = ["day_return"]

    # 识别涨停票（涨幅>9.5%）
    limit_up_stocks = pred_date_data[pred_date_data["day_return"] > 1.095].index
    print(f"  涨停票数量: {len(limit_up_stocks)} 只")

    # 从预测结果中剔除涨停票
    tradable_pred = pred_scores[~pred_scores.index.isin(limit_up_stocks)]
    print(f"  可交易股票: {len(tradable_pred)} 只")

    # 重新排序
    result = tradable_pred.sort_values(by="score", ascending=False)

    # 显示 Top 20（过滤后）
    print("\nTop 20 预测收益率最高的股票（已过滤涨停）:")
    print(result.head(20))

    # 保存
    output_file = f"prediction_alpha158_{prediction_end}.csv"
    result.to_csv(output_file)
    print(f"\n✓ 结果已保存到: {output_file}")
    print(f"   (预测的是 {prediction_end} 的 T+1 收益率，即次日收益)")

    # 统计
    print(f"\n预测统计:")
    print(f"  - 预测日期: {prediction_start} 至 {prediction_end}")
    print(f"  - 目标收益: T+1 (次日收益率)")
    print(f"  - 股票总数: {len(result)}")
    print(f"  - 平均预测收益: {result['score'].mean():.4f}")
    print(f"  - 最高预测收益: {result['score'].max():.4f}")
    print(f"  - 最低预测收益: {result['score'].min():.4f}")

    return result


def main():
    # 从命令行参数获取配置
    if len(sys.argv) != 5:
        print(
            "Usage: python predict_with_alpha158.py <experiment_name> <recorder_id> <start_date> <end_date>"
        )
        print(
            "Example: python predict_with_alpha158.py alpha158_workflow your_recorder_id_here 2025-01-01 2025-12-31"
        )
        return 1
    experiment_name = sys.argv[1]
    recorder_id = sys.argv[2]
    start_date = sys.argv[3]  # 预测开始日期
    end_date = sys.argv[4]  # 预测结束日期

    try:
        predict_with_extented_alpha158(
            experiment_name, recorder_id, start_date, end_date
        )
        print("\n✅ 预测流程完成！")
        return 0
    except Exception as e:
        print(f"\n✗ 预测失败: {e}")


if __name__ == "__main__":
    exit(main())
