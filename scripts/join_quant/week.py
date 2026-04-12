# 导入函数库
from jqdata import *
import pandas as pd
import datetime
import stock_strategy as strategy

# 依据qlib训练的结果，构建一个简单的基于等权重的选股和调仓策略
g_target_stocks = {}

g_max_stocks = 10
g_highest_price = {}
g_max_return = 0.1
g_max_lose = 0.05
g_max_position_days = 5

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
            open_commission=0.00015,
            close_commission=0.00015,
            min_commission=5,
        ),
        type="stock",
    )
    # 定时运行：每个交易日 14:30 执行调仓逻辑
    run_daily(trade_logic, time="14:50")
    # run_daily(stop_loss, time="every_bar")
  

def trade_logic(context):
    # 1. 获取当前日期
    current_date = context.current_dt.date()

    # 获取前n个交易日
    n = g_max_position_days
    trade_days = get_trade_days(end_date=current_date, count=n+1)   
    if len(trade_days) < n+1:
        log.warning(f"无法获取前{n} 个交易日，可能是回测结束或节假日安排未知")
        return
    position_trade_date = trade_days[0]
    pre_trade_date = trade_days[-2]
    trade_date = pre_trade_date.strftime("%Y-%m-%d")

    # 2. 获取需要交易的股票
    target_stocks = []
    if trade_date in g_target_stocks:
        target_stocks = g_target_stocks[trade_date]
        log.info(f"今日目标股票 ({len(target_stocks)}只): {target_stocks}")

    # 3. 获取当前持仓
    current_holdings = list(context.portfolio.positions.keys())
    log.info(f"当前持有股票：{current_holdings}")
    
    # 卖出股票
    # 卖出持仓超过g_max_position_days日，且不在目标列表中排名前n的股票,n = g_max_stocks
    for stock in current_holdings:
        # 检查持仓天数
        position = context.portfolio.positions.get(stock)
        if position.init_time.date() > position_trade_date:
            continue
        log.info(f"{stock} 持仓天数超过{g_max_position_days}天，准备卖出")
        if stock not in target_stocks[:g_max_stocks]:
            log.info(f"{stock} 不在目标股票列表中, 准备卖出")
            current_data = get_current_data()
            # 停牌检查
            if current_data[stock].paused:
                log.info(f"卖出过滤：{stock} 当前停牌，跳过卖出")
                continue
            
            # 跌停检查
            low_limit = current_data[stock].low_limit
            last_price = current_data[stock].last_price
            if low_limit is not None and last_price <= low_limit:
                log.info(f"卖出过滤：{stock} 当前价格 {last_price} 达到跌停价 {low_limit}，跳过卖出")
                continue

            # 卖出
            protection_limit_price = round(last_price * 0.9, 2)
            protection_limit_price = min(protection_limit_price, 9999)
            log.info(f"卖出: {stock} 当前价格：{last_price} 保护价：{protection_limit_price}")
            order_target_value(stock, 0, style=MarketOrderStyle(protection_limit_price))
            g_highest_price.pop(stock, None)

    # 买入股票：买入目标列表中排名前n的股票,n = g_max_stocks，跳过已经持有的股票
    for stock in target_stocks:
        current_holdings = list(context.portfolio.positions.keys())
        # 计算当前持仓数量和目标持仓数量，确保不超过最大持仓限制
        target_num = g_max_stocks - len(current_holdings)
        if target_num <= 0:
            log.info("已达到最大持仓数量限制，停止买入更多股票")
            break
        
        # 判断是否已经持有
        if stock in current_holdings:
            log.info(f"{stock} 已持有，跳过买入")
            continue
        
        current_data = get_current_data()
        
        # 60日均线检查
        if not check_price_above_ma(stock, context):
            log.info(f"买入过滤：{stock} 当前价格未在60日均线之上，跳过买入")
            continue
        
        # 停牌检查
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
            log.info(f"买入过滤：{stock} 当前价格 {last_price} 达到涨停价 {high_limit}，跳过买入")
            continue
        
        # 买入
        value_per_stock = context.portfolio.available_cash / target_num
        current_price = current_data[stock].last_price
        protection_limit_price = round(current_price * 1.1, 2)
        protection_limit_price = min(protection_limit_price, 9999)
        log.info(f"买入: {stock}, 目标金额: {value_per_stock:.2f}, 当前价格：{current_price:.2f} 保护限价: {protection_limit_price:.2f}")
        order_target_value(stock, value_per_stock, style=MarketOrderStyle(protection_limit_price))
        g_highest_price[stock] = current_price


def check_price_above_ma(stock, context):
    """
    检查指定股票的当前价格是否在5日、10日、20日、60日均线之上
    """
    # 1. 获取过去60天的历史行情数据（包含收盘价）
    # 为了确保能计算60日均线，至少需要获取60个周期的数据
    history_data = attribute_history(stock, 60, '1d', ['close'])
    
    # 如果数据不足，直接返回False
    if history_data is None or len(history_data) < 60:
        return False

    # 2. 计算各周期的移动平均线
    # 计算的是截至昨天的60天数据的均线
    ma5 = history_data['close'].tail(5).mean()
    ma10 = history_data['close'].tail(10).mean()
    ma20 = history_data['close'].tail(20).mean()
    ma60 = history_data['close'].mean() # 等同于 .tail(60).mean()

    # 3. 获取当前最新价格
    current_price = get_current_data()[stock].last_price

    # 4. 检查当前价格是否在所有均线之上
    # is_above_all_mas = (current_price > ma5) and (ma5 > ma10) and (ma10 > ma20) and (ma20 > ma60)
    is_above_all_mas = (current_price > ma5) and (ma5 > ma10) and (ma10 > ma20)
    
    # 可选：打印调试信息
    # log.info(f"股票: {stock}, 现价: {current_price}, MA5: {ma5:.2f}, MA10: {ma10:.2f}, MA20: {ma20:.2f}, MA60: {ma60:.2f}, 条件满足: {is_above_all_mas}")
    
    return is_above_all_mas


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
        highest = g_highest_price[stock]
        should_stop = False
        reason = ""

        if avg_cost > 0 and current_price < avg_cost * ( 1 - g_max_lose ):
            should_stop = True
            drop_pct = (avg_cost - current_price) / avg_cost
            reason = f"亏损止损: 买入价{avg_cost:.2f}, 现价{current_price:.2f}, 跌幅{drop_pct:.2%}"
        elif current_price < highest * ( 1 - g_max_return):
            should_stop = True
            drawdown_pct = (highest - current_price) / highest
            reason = f"回撤止损: 最高价{highest:.2f}, 现价{current_price:.2f}, 回撤{drawdown_pct:.2%}"

        if should_stop:
            log.info(f"止损卖出: {stock} {reason}")
            current_price = get_current_data()[stock].last_price
            protection_limit_price = round(current_price * 0.9, 2)
            protection_limit_price = min(protection_limit_price, 9999)
            order_target_value(stock, 0,style=MarketOrderStyle(protection_limit_price))
            g_highest_price.pop(stock, None)

