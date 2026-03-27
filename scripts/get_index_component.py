from datetime import datetime
from xtquant import xtdata

def get_index_constituents_history(index_code, start_date, end_date):
    """
    获取指定指数的历史成分股变动信息，并计算每只股票的进入和退出时间。

    :param index_code: str, 指数代码，格式如 '000300.SH' (沪深300)
    :param start_date: str, 开始日期，格式 'YYYYMMDD'
    :param end_date: str, 结束日期，格式 'YYYYMMDD'，若为今天则表示为至今
    :return: dict, 包含每只股票及其进入和退出时间的字典
    """
    # 1. 下载必要的板块分类数据，这是获取成分股的前提
    print("正在下载板块分类数据...")
    xtdata.download_sector_data()
    print("正在下载历史数据...")
    xtdata.download_history_data("", "1d", "", "")
    print("数据下载完成。")

    # 2. 获取交易日历
    print("正在获取交易日历...")
    days = xtdata.get_trading_calendar(market="SZ", start_time=start_date, end_time=end_date)
    print(f"获取到 {len(days)} 个交易日。")

    # 3. 逐日获取成分股，构建一个字典：日期 -> 成分股列表
    constituents_at_date = {}
    for i, day_str in enumerate(days):
        dt = datetime.strptime(day_str, "%Y%m%d")
        # 获取指定日期的成分股列表，格式如 ['000001.SZ', '600000.SH']
        # 关键：传入日期参数，避免未来函数
        symbols = xtdata.get_stock_list_in_sector(index_code, day_str)
        
        # 将迅投研格式转换为更通用的格式（可选）
        # vt_symbols = [s.replace('SH', 'SSE').replace('SZ', 'SZSE') for s in symbols] 
        
        constituents_at_date[dt] = set(symbols)  # 用set便于后续计算
        
        if i % 100 == 0:  # 每100天打印一次进度
            print(f"已处理 {i+1}/{len(days)} 个交易日...")
    print("成分股数据获取完成。")

    # 4. 分析每只股票的进入和退出时间
    stock_dates = {}  # 用于存储每只股票出现的所有日期
    all_dates = sorted(constituents_at_date.keys())
    
    for date, stocks in constituents_at_date.items():
        for stock in stocks:
            if stock not in stock_dates:
                stock_dates[stock] = []
            stock_dates[stock].append(date)
    
    # 计算最终结果
    result = []
    today = datetime.now()
    for stock, dates in stock_dates.items():
        entry_date = min(dates)  # 进入时间 = 最早出现日期
        
        # 退出时间逻辑：如果最后一次出现是最后一个交易日，则视为未退出，否则为最后一次出现的日期
        last_appearance = max(dates)
        if last_appearance == all_dates[-1]:
            # 还没退出，显示当前日期
            exit_date = today.strftime("%Y-%m-%d")
            exit_status = "至今"
        else:
            # 已退出，退出时间为最后一次出现的日期
            # 注意：实际退出是在下一次调仓时，但这里简化逻辑，取最后出现日
            exit_date = last_appearance.strftime("%Y-%m-%d")
            exit_status = exit_date
        
        result.append({
            "stock_code": stock,
            "entry_date": entry_date.strftime("%Y-%m-%d"),
            "exit_date": exit_status
        })
    
    return result

# --- 使用示例 ---
if __name__ == "__main__":
    # 参数设置：以沪深300 (000300.SH) 为例，时间范围从 2023-01-01 到 2025-12-31
    INDEX = "000300.SH"        # 中证指数代码示例，沪深300
    START = "20230101"
    END = "20251231"
    
    print(f"正在获取指数 {INDEX} 从 {START} 到 {END} 的成分股历史...")
    components_info = get_index_constituents_history(INDEX, START, END)
    
    # 打印结果
    print("\n===== 成分股变动历史 =====")
    print(f"{'股票代码':<15} {'进入时间':<12} {'退出时间':<12}")
    print("-" * 40)
    for item in components_info:
        print(f"{item['stock_code']:<15} {item['entry_date']:<12} {item['exit_date']:<12}")
    
    print(f"\n总计处理股票数量: {len(components_info)}")