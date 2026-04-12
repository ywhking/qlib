# 多头排列，ma5上穿ma10的策略
from datetime import time

import pandas as pd
from jqdata import *

# 定义常量
g_max_hold_stocks = 5
g_max_holding_days = 3
g_jump_threshold = 0.05
g_max_loss = 0.02
g_market = '000300.XSHG'  # 沪深300指数作为基准
# g_market = '000852.XSHG'  # 中证1000指数作为基准

def initialize(context):
    # 初始化全局变量
    g.candidate_pool = {}
    g.max_buy_stocks = 0
    
    set_benchmark(g_market)
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(0.002))
    set_commission(commission.PerTrade(buy_cost=0.00025, sell_cost=0.00025, min_cost=5))
    
    
    run_daily(opening_selection, time='09:40')
    run_daily(check_oops_signal, time='every_bar')
    run_daily(check_stop_loss, time='every_bar')
    run_daily(sell_by_holding_days, time='14:50')

def select_cantidate_stocks(context):
    # 清空备选股池
    g.candidate_pool = {}
    
    current_date = context.current_dt.date()
    log.info('=' * 50)
    log.info('开盘选股 - 日期: %s' % current_date)
    
    # 获取市场股票列表
    all_stocks = get_index_stocks(g_market, date=current_date)
    
    # 过滤ST股
    st_status = get_extras('is_st', all_stocks, start_date=current_date, end_date=current_date, df=True)
    candidate_stocks = []
    for stock_name, is_st_series in st_status.items():
        if not is_st_series.any():
            candidate_stocks.append(stock_name)
    log.info('过滤掉ST后的股票数量: %d' % len(candidate_stocks))
    
    # 4. 筛选ma10 ma20 ma60 多头排列的股票
    current_data = get_current_data()
    for stock in candidate_stocks:
        # 跳过停牌股票
        if current_data[stock].paused:
            log.info('跳过停牌股票: %s' % stock)
            continue
        
        # 跳过ST股票（再次确认）
        if current_data[stock].is_st:
            log.info('跳过ST股票: %s' % stock)
            continue
        
        # 获取前一天的最高价
        his_price = get_price(stock, end_date=current_date, frequency='daily', fields=None, skip_paused=False, fq='pre', count=2, panel=False, fill_paused=True)
        if len(his_price) < 2:
            log.info('无法获取前一天价格，跳过: %s' % stock)
            continue
        prev_high = his_price['high'].iloc[0]
        
        # 筛选多头排列，且ma5可能上穿ma10的股票
        if check_cross_up(stock, context):
            g.candidate_pool[stock] = prev_high
            log.info('选中多头排列且可能上穿ma10的股票: %s, 前一天最高价: %.2f' % (stock, prev_high))  
    
    log.info('备选股数量: %d' % len(g.candidate_pool))
    log.info('=' * 50)


def check_oops_signal(context):
    current_holdings = len(context.portfolio.positions)
    if current_holdings >= g_max_hold_stocks:
        return
    
    g.max_buy_stocks = g_max_hold_stocks - current_holdings
    
    for stock in list(g.candidate_pool.keys()):
        if stock in context.portfolio.positions:
            # log.info('已持有股票，跳过: %s' % stock)
            continue

        current_data = get_current_data()
        if stock not in current_data:
            continue
        
        current_price = current_data[stock].last_price
        if current_price > g.candidate_pool[stock]:
            log.info('满足Oops条件，准备买入: %s, 当前价: %.2f, 前一天最高价: %.2f' % (stock, current_price, g.candidate_pool[stock]))
            # 跳过涨停股票
            if current_data[stock].high_limit is not None and current_price >= current_data[stock].high_limit:
                log.info('跳过涨停股票: %s, 当前价: %.2f, 涨停价: %.2f' % (stock, current_price, current_data[stock].high_limit))
                # 从备选池中移除该股票，避免重复检查
                g.candidate_pool.pop(stock, None)
                continue
            buy_stock(context, stock, current_price)
            log.info('买入股票: %s, 当前价: %.2f' % (stock, current_price))
            g.max_buy_stocks -= 1
            if g.max_buy_stocks <= 0:
                break
    

def buy_stock(context, stock, current_price):
    value_per_stock = context.portfolio.available_cash / g.max_buy_stocks
    protection_limit_price = round(current_price * 1.1, 2)
    protection_limit_price = min(protection_limit_price, 9999)
    log.info(f"买入: {stock}, 目标金额: {value_per_stock:.2f}, 当前价格：{current_price:.2f} 保护限价: {protection_limit_price:.2f}")
    order_target_value(stock, value_per_stock, style=MarketOrderStyle(protection_limit_price))


def sell_by_holding_days(context):
    # 获取当前持仓
    current_holdings = list(context.portfolio.positions.keys())
    log.info(f"当前持有股票：{current_holdings}")
    
    # 获取前n个交易日日期，n = g_max_holding_days
    current_date = context.current_dt.date()
    trade_days = get_trade_days(end_date=current_date, count=g_max_holding_days+1)   
    if len(trade_days) < g_max_holding_days+1:
        log.warning(f"无法获取前{g_max_holding_days} 个交易日，可能是回测结束或节假日安排未知")
        return
    position_trade_date = trade_days[0]
    
    # 卖出股票
    # 卖出持仓超过g_max_holding_days日，且不在目标列表中排名前n的股票,n = g_max_stocks
    current_data = get_current_data()
    for stock in current_holdings:
        # 检查持仓天数
        position = context.portfolio.positions.get(stock)
        if position.init_time.date() > position_trade_date:
            continue
        log.info(f"{stock} 持仓天数超过{g_max_holding_days}天，准备卖出")

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
        order_target_value(stock, 0, style=MarketOrderStyle(protection_limit_price))
        log.info(f"{stock}卖出成功，挂单价格：{last_price} 保护价：{protection_limit_price}")


def check_stop_loss(context):
    stocks_to_sell = []
    current_data = get_current_data()
    for stock, position in context.portfolio.positions.items():
        if position.total_amount == 0:
            continue
        # 跳过当天买入的股票
        if position.init_time.date() == context.current_dt.date():
            continue
        avg_cost = position.avg_cost
        if avg_cost is None or avg_cost == 0:
            continue
        if stock not in current_data:
            continue
        current_price = current_data[stock].last_price
        if current_price < avg_cost * (1 - g_max_loss):
            stocks_to_sell.append(stock)
            log.info('【止损】%s, 成本: %.2f, 当前价: %.2f, 亏损: %.2f%%' 
                     % (stock, avg_cost, current_price, (current_price - avg_cost)/avg_cost*100))
    
    for stock in stocks_to_sell:
        try:
            current_price = current_data[stock].last_price
            protection_limit_price = round(current_price * 0.9, 2)
            protection_limit_price = min(protection_limit_price, 9999)
            order_target_value(stock, 0,style=MarketOrderStyle(protection_limit_price))
        except Exception as e:
            log.error('止损卖出失败 %s: %s' % (stock, str(e)))
            
def check_cross_up(stock, context):
    """
    检查指定股票是否按10日、20日、60日均线多头排列
    前一日的 ma5 在 ma10下方，当日可能形成上穿ma10的机会 
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
    is_bullish_alignment = (ma5 < ma10) and (ma10 > ma20) and (ma20 > ma60) 
    
    # 前一日的 ma5 在 ma10下方，当日可能形成上穿ma10的机会
    will_cross_up = (ma5 < ma10) 
    
    # 可选：打印调试信息
    # log.info(f"股票: {stock}, 现价: {current_price}, MA5: {ma5:.2f}, MA10: {ma10:.2f}, MA20: {ma20:.2f}, MA60: {ma60:.2f}, 条件满足: {is_above_all_mas}")
    
    return is_bullish_alignment and will_cross_up