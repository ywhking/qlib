# 导入函数库
from jqdata import *
import pandas as pd
import datetime
import stock_strategy as strategy

# 依据qlib训练的结果，构建一个简单的基于等权重的选股和调仓策略
g_target_stocks = {}
g_max_stocks = 5
g_highest_price = {}
g_stopped_stocks = set()


def initialize(context):
    # 设置基准
    set_benchmark("000300.XSHG")
    # 开启动态复权模式
    set_option("use_real_price", True)
    # 日志输出级别
    log.set_level("order", "error")
    # 设置滑点
    set_slippage(FixedSlippage(0.05))
    # 设定手续费
    set_order_cost(
        OrderCost(
            close_tax=0.001,
            open_commission=0.0003,
            close_commission=0.0003,
            min_commission=5,
        ),
        type="stock",
    )
    # 定时运行：每个交易日 14:30 执行调仓逻辑
    run_daily(trade_logic, time="14:50")
    # run_daily(buy_logic, time='9:35')
    # run_daily(sell_logic, time='14:50')
    # 每分钟检查一次止损条件
    run_daily(stop_loss, time="every_bar")
    run_daily(reset_stopped, time="09:00")


def reset_stopped(context):
    g_stopped_stocks.clear()


def trade_logic(context):
    # 1. 获取当前日期
    current_date = context.current_dt.date()

    # # 获取前一个交易日
    # trade_days = get_trade_days(end_date=current_date, count=2)
    # if len(trade_days) < 2:
    #     log.warning("无法获取前一个交易日，可能是回测结束或节假日安排未知")
    #     return
    # pre_trade_date = trade_days[0].strftime("%Y-%m-%d")
    # log.info(f"当前日期: {current_date},按前一个交易日: {pre_trade_date} 给出的信号交易")

    trade_date = current_date.strftime("%Y-%m-%d")

    # 2. 获取下一个交易日的目标股票
    target_stocks = []
    if trade_date in g_target_stocks:
        target_stocks = g_target_stocks[trade_date]
        log.info(f"今日目标股票 ({len(target_stocks)}只): {target_stocks}")

    # 3. 获取当前持仓
    current_holdings = list(context.portfolio.positions.keys())
    log.info(f"当前持有股票：{current_holdings}")

    # 4. 获取当前实时数据（用于判断停牌、ST、涨跌停）
    current_data = get_current_data()

    # ========== 卖出过滤 ==========
    # 需要卖出的股票：不在目标列表中的持仓股票
    stocks_to_sell = [stock for stock in current_holdings if stock not in target_stocks]
    log.info(f"计划卖出股票：{stocks_to_sell}")

    for stock in stocks_to_sell:
        # 停牌检查
        if current_data[stock].paused:
            log.info(f"卖出过滤：{stock} 当前停牌，跳过卖出")
            continue
        # 检查是否跌停
        low_limit = current_data[stock].low_limit
        last_price = current_data[stock].last_price
        if low_limit is not None and last_price <= low_limit:
            log.info(
                f"卖出过滤：{stock} 当前价格 {last_price} 达到跌停价 {low_limit}，跳过卖出"
            )
            continue

        position = context.portfolio.positions.get(stock)
        if position and position.closeable_amount > 0:
            current_price = get_current_data()[stock].last_price
            protection_limit_price = round(current_price * 0.9, 2)
            protection_limit_price = min(protection_limit_price, 9999)
            log.info(
                f"卖出: {stock} (数量: {position.closeable_amount}) 当前价格：{current_price} 保护价：{protection_limit_price}"
            )
            order_target_value(stock, 0, style=MarketOrderStyle(protection_limit_price))
            g_highest_price.pop(stock, None)
    # 需要买入的股票：在目标列表中但当前未持仓的股票
    stocks_to_buy = [stock for stock in target_stocks if stock not in current_holdings]
    log.info(f"计划买入股票：{stocks_to_buy}")

    # 过滤掉停牌、ST、涨停的股票
    valid_buy_stocks = []
    for stock in stocks_to_buy:
        if stock in g_stopped_stocks:
            log.info(f"买入过滤：{stock} 当日已止损，跳过买入")
            continue

        if current_data[stock].paused:
            log.info(f"买入过滤：{stock} 当前停牌，跳过买入")
            continue

        # ST 检查
        # if hasattr(current_data[stock], 'is_st') and current_data[stock].is_st:
        #     log.info(f"买入过滤：{stock} 当前为 ST 股票，跳过买入")
        #     continue

        # 涨停检查
        high_limit = current_data[stock].high_limit
        last_price = current_data[stock].last_price
        if high_limit is not None and last_price >= high_limit:
            log.info(
                f"买入过滤：{stock} 当前价格 {last_price} 达到涨停价 {high_limit}，跳过买入"
            )
            continue

        valid_buy_stocks.append(stock)

    log.info(f"过滤后可买入股票：{valid_buy_stocks}")

    if len(valid_buy_stocks) == 0:
        log.info("所有目标股票均被过滤或已在持仓，无需新开仓。")
        return

    # 计算每只股票的目标金额（等权重策略）
    # 注意：过滤后实际买入股票数量减少，但为了保持原策略简洁，仍按原目标总数计算每只金额
    # 如有需要可调整为按实际可买数量重新分配，此处不做改动
    # 当前持仓数量
    current_holdings = list(context.portfolio.positions.keys())
    num_targets = g_max_stocks - len(current_holdings)
    log.info(f"开始买入股票：{valid_buy_stocks}，计划买入数量: {num_targets}只")
    for stock in valid_buy_stocks:
        if num_targets <= 0:
            log.info("已达到最大持仓数量限制，停止买入更多股票")
            break
        value_per_stock = context.portfolio.available_cash / num_targets
        current_price = get_current_data()[stock].last_price
        protection_limit_price = round(current_price * 1.1, 2)
        protection_limit_price = min(protection_limit_price, 9999)
        log.info(
            f"买入: {stock}, 目标金额: {value_per_stock:.2f}, 当前价格：{current_price:.2f} 保护限价: {protection_limit_price:.2f}"
        )
        order_target_value(
            stock, value_per_stock, style=MarketOrderStyle(protection_limit_price)
        )

        g_highest_price[stock] = current_price

        current_holdings = list(context.portfolio.positions.keys())
        num_targets = g_max_stocks - len(current_holdings)


def stop_loss(context):
    if context.current_dt.hour < 9 or (
        context.current_dt.hour == 9 and context.current_dt.minute < 31
    ):
        return
    if context.current_dt.hour == 14 and context.current_dt.minute >= 50:
        return

    current_holdings = list(context.portfolio.positions.keys())
    if not current_holdings:
        return

    current_data = get_current_data()
    for stock in list(current_holdings):
        position = context.portfolio.positions.get(stock)
        if not position or position.closeable_amount <= 0:
            continue
        if current_data[stock].paused:
            continue
        low_limit = current_data[stock].low_limit
        current_price = current_data[stock].last_price
        if low_limit is not None and current_price <= low_limit:
            continue

        avg_cost = position.avg_cost

        if stock not in g_highest_price:
            g_highest_price[stock] = current_price
        g_highest_price[stock] = max(g_highest_price[stock], current_price)
        highest = g_highest_price[stock]

        should_stop = False
        reason = ""

        if avg_cost > 0 and current_price < avg_cost * 0.99:
            should_stop = True
            drop_pct = (avg_cost - current_price) / avg_cost
            reason = f"亏损止损: 买入价{avg_cost:.2f}, 现价{current_price:.2f}, 跌幅{drop_pct:.2%}"
        elif current_price < highest * 0.95:
            should_stop = True
            drawdown_pct = (highest - current_price) / highest
            reason = f"回撤止损: 最高价{highest:.2f}, 现价{current_price:.2f}, 回撤{drawdown_pct:.2%}"

        if should_stop:
            log.info(f"止损卖出: {stock} {reason}")
            order_target_value(stock, 0)
            g_stopped_stocks.add(stock)
            g_highest_price.pop(stock, None)
