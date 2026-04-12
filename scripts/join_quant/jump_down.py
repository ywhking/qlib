# 跳空反抽策略（Oops策略）- 最终修正版
from datetime import time

import pandas as pd
from jqdata import *

# 定义常量
g_max_hold_stocks = 5
g_max_buy_stocks = g_max_hold_stocks
g_max_holding_days = 3
g_jump_threshold = 0.05
g_max_loss = 0.02
# g_market = '000300.XSHG'  # 沪深300指数作为基准
g_market = '000852.XSHG'  # 中证1000指数作为基准

def initialize(context):
    # 初始化全局变量
    g.candidate_pool = {}
    
    set_benchmark(g_market)
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(0.002))
    set_commission(commission.PerTrade(buy_cost=0.00025, sell_cost=0.00025, min_cost=5))
    
    
    run_daily(opening_selection, time='09:31')
    run_daily(check_oops_signal, time='every_bar')
    run_daily(check_stop_loss, time='every_bar')
    run_daily(sell_by_holding_days, time='14:50')

def opening_selection(context):
    # 清空备选股池
    g.candidate_pool = {}
    
    current_date = context.current_dt.date()
    log.info('=' * 50)
    log.info('开盘选股 - 日期: %s' % current_date)
    
    # 获取全市场股票列表
    # all_stocks_df = get_all_securities(['stock'],date=current_date)
    # log.info('全市场股票数量: %d' % len(all_stocks_df))
    
    # # 过滤掉次新股, start_date 距离当前日期不足60个交易日的股票
    # all_stocks_df = all_stocks_df[all_stocks_df['start_date'] <= current_date - pd.Timedelta(days=90)]
    # log.info('过滤掉次新股后的股票数量: %d' % len(all_stocks_df))
    # all_stocks = all_stocks_df.index.tolist()
    
    all_stocks = get_index_stocks(g_market, date=current_date)
    
    # 过滤ST股
    st_status = get_extras('is_st', all_stocks, start_date=current_date, end_date=current_date, df=True)
    candidate_stocks = []
    for stock_name, is_st_series in st_status.items():
        if not is_st_series.any():
            candidate_stocks.append(stock_name)
    log.info('过滤掉ST后的股票数量: %d' % len(candidate_stocks))
    
    # 4. 筛选跳空低开超5%的股票
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
        
        # 获取前一天的最低价
        his_price = get_price(stock, end_date=current_date, frequency='daily', fields=None, skip_paused=False, fq='pre', count=2, panel=False, fill_paused=True)
        if len(his_price) < 2:
            log.info('无法获取前一天价格，跳过: %s' % stock)
            continue
        prev_low = his_price['low'].iloc[0]
        
        # 筛选跳空低开超过5%的股票
        open_price = current_data[stock].day_open
        if open_price < prev_low * (1 - g_jump_threshold):
            g.candidate_pool[stock] = prev_low
            log.info('选中跳空低开股票: %s, 开盘价: %.2f, 前一天最低价: %.2f' % (stock, open_price, prev_low))  
    
    log.info('备选股数量: %d' % len(g.candidate_pool))
    log.info('=' * 50)


def check_oops_signal(context):
    current_holdings = len(context.portfolio.positions)
    if current_holdings >= g_max_hold_stocks:
        return
    
    g_max_buy_stocks = g_max_hold_stocks - current_holdings
    
    for stock in list(g.candidate_pool.keys()):
        if stock in context.portfolio.positions:
            # log.info('已持有股票，跳过: %s' % stock)
            continue

        current_data = get_current_data()
        if stock not in current_data:
            continue
        
        current_price = current_data[stock].last_price
        if current_price > g.candidate_pool[stock]:
            log.info('满足Oops条件，准备买入: %s, 当前价: %.2f, 前一天最低价: %.2f' % (stock, current_price, g.candidate_pool[stock]))
            # 跳过涨停股票
            if current_data[stock].high_limit is not None and current_price >= current_data[stock].high_limit:
                log.info('跳过涨停股票: %s, 当前价: %.2f, 涨停价: %.2f' % (stock, current_price, current_data[stock].high_limit))
                # 从备选池中移除该股票，避免重复检查
                g.candidate_pool.pop(stock, None)
                continue
            buy_stock(context, stock, current_price)
            log.info('买入股票: %s, 当前价: %.2f' % (stock, current_price))
            g_max_buy_stocks -= 1
            if g_max_buy_stocks <= 0:
                break
    

def buy_stock(context, stock, current_price):
    value_per_stock = context.portfolio.available_cash / g_max_buy_stocks
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