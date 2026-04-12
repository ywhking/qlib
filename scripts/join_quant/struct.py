# 聚宽平台 威廉姆斯市场结构策略
# 策略逻辑：
# 候选股票
# 在当前交易日之前的20个交易日内已形成一个中期低点
# 在当前交易日和前一个中期低点之间没有短期或中期低点
# 当天交易可能形成一个短期低点，即前两个交易的最高价高于前一日的最高价，前两个交易日的最低价也高于前一日的最低价
# 当日股价冲高，高过前一个交易日的高点，形成前一个交易日的低点为短期低点，且低点高于前一次中期低点时产生买入信号


# 导入聚宽平台内置库（不需要手动导入，平台自动注入）
# jqdata 提供数据获取功能，无需额外 import

g_initialized = {} # 用于标记是否已初始化，避免重复执行 initialize 函数 key:stock_code value: bool


def initialize(context):
    """
    初始化函数，在整个回测开始时执行一次
    """
    # 设置基准：沪深300指数
    set_benchmark('000300.XSHG')
    
    # 设置股票池：单标的回测（可修改为任意A股代码，如 '000001.XSHE' 平安银行）
    # 聚宽A股代码格式：6位代码 + .XSHG（上海）或 .XSHE（深圳）
    g.security = '000001.XSHE'  # 平安银行
    
    # 设置全局变量，存储短期低点和中期低点
    g.short_term_lows = []      # 存储 (index_date, low_price) 已确认的短期低点
    g.last_mid_low_price = None # 最近一个中期低点的价格
    g.last_mid_low_date = None  # 最近一个中期低点的日期
    
    # 状态变量
    g.pending_buy = False       # 是否有待执行的买入信号
    g.pending_buy_stop = 0      # 待执行买入的止损价
    g.position_held = False     # 当前是否持仓
    
    # 运行频率：每个交易日调用一次
    run_daily(market_open, time='every_bar')
    
    # 可选：设置佣金（默认万分之二点五）、滑点（固定滑点0.01元）
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, 
                             open_commission=0.00025, close_commission=0.00025,
                             min_commission=5), type='stock')
    set_slippage(FixedSlippage(0.01))


def market_open(context):
    """
    每个交易日开盘时执行的核心交易逻辑
    """
    stock = g.security
    
    # 获取当前日期
    current_date = context.current_dt.date()
    
    # 获取足够的历史日线数据（至少需要20根以上才能完成高低点识别）
    # attribute_history: 获取过去N天的历史数据，包含 open, high, low, close, volume
    hist = attribute_history(stock, 50, '1d', ['open', 'high', 'low', 'close'], skip_paused=True)
    
    if hist is None or len(hist) < 10:
        return
    
    # 转换为列表格式便于处理
    dates = hist.index.tolist()
    lows = hist['low'].values
    
    # ----- 1. 检查持仓是否需要止损（每个交易日开盘前检查）-----
    if g.position_held and g.last_mid_low_price is not None:
        # 获取当前价格（开盘价或最新价）
        current_price = get_current_data()[stock].last_price
        
        if current_price <= g.last_mid_low_price:
            # 触发止损，清仓
            order_target(stock, 0)
            g.position_held = False
            g.last_mid_low_price = None
            g.last_mid_low_date = None
            log.info(f'{current_date} 止损平仓，价格: {current_price:.2f}')
            return
    
    # ----- 2. 执行待执行的买入信号（如果有）-----
    if g.pending_buy and not g.position_held:
        current_price = get_current_data()[stock].last_price
        # 按当前可用现金的全仓买入
        order_target_percent(stock, 1.0)
        g.position_held = True
        g.pending_buy = False
        log.info(f'{current_date} 执行买入，价格: {current_price:.2f}')
        return
    
    # ----- 3. 识别短期低点和中期低点 -----
    # 遍历历史数据识别短期低点：当日最低价低于前后两日的最低价
    for i in range(1, len(lows) - 1):
        if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
            # 确认是短期低点
            low_date = dates[i]
            low_price = lows[i]
            
            # 避免重复添加
            if g.short_term_lows and g.short_term_lows[-1][0] == low_date:
                continue
            
            # 存储短期低点
            g.short_term_lows.append((low_date, low_price))
            
            # 检查中期低点：当短期低点数量 >= 3 时，检查倒数第二个是否为中期低点
            if len(g.short_term_lows) >= 3:
                # 倒数第二个短期低点为候选中期低点
                cand_date, cand_price = g.short_term_lows[-2]
                prev_date, prev_price = g.short_term_lows[-3]
                next_date, next_price = g.short_term_lows[-1]
                
                if cand_price < prev_price and cand_price < next_price:
                    # 确认是中期低点
                    g.last_mid_low_price = cand_price
                    g.last_mid_low_date = cand_date
                    log.debug(f'确认中期低点: 日期 {cand_date}, 价格 {cand_price:.2f}')
            
            # 检查买入条件
            if g.last_mid_low_price is not None and low_price > g.last_mid_low_price:
                # 条件满足：当前短期低点高于前一次中期低点
                if not g.position_held and not g.pending_buy:
                    g.pending_buy = True
                    g.pending_buy_stop = g.last_mid_low_price
                    log.info(f'{current_date} 产生买入信号，当前短期低点 {low_price:.2f} > '
                             f'前中期低点 {g.last_mid_low_price:.2f}')
                    break


def after_trading_end(context):
    """
    每个交易日收盘后执行，用于记录和日志
    """
    current_date = context.current_dt.date()
    total_value = context.portfolio.total_value
    log.info(f'{current_date} 收盘，账户总值: {total_value:.2f}')
    
    
def has_mid_low_point_stock(stock):
    """
    判断指定股票在前20个交易日是否存在中期低点
    """
    hist = attribute_history(stock, 50, '1d', ['low'], skip_paused=True)
    
    if hist is None or len(hist) < 10:
        return False
    
    lows = hist['low'].values
    dates = hist.index.tolist()
    
    short_term_lows = []
    
    for i in range(1, len(lows) - 1):
        if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
            low_date = dates[i]
            low_price = lows[i]
            short_term_lows.append((low_date, low_price))
    
    # 检查是否存在中期低点
    for i in range(1, len(short_term_lows) - 1):
        prev_date, prev_price = short_term_lows[i-1]
        cand_date, cand_price = short_term_lows[i]
        next_date, next_price = short_term_lows[i+1]
        
        if cand_price < prev_price and cand_price < next_price:
            return True
    
    return False