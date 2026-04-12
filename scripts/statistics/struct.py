import os

import pandas as pd

def oops():
    """
    统计出现中期低点场景下买入股票，后续看涨的概率
    短期低点定义，需同时满足一下两个点：
    1）当某个交易的最低点低于前一个交易的最低点，且低于后一个交易的最低点，
    2）且该交易日的最高点低于前一个交易的最高点，且低于后一个交易的最高点，认为形成了一个短期低点
    中期低点定义：当短期低点低于前一次中期低点，且低于后一次短期期低点，认为形成了一个新的中期低点
    中期低点场景定义：当天开盘价低于前一天最低价，并且当天最高价高于前一天最低价
    交易数据来源：
    数据存储目录：~/.qlib/tushare_data2
    目录下每只股票对应一个csv文件，文件命名格式为"{stock_code}.csv"
    """
    
    # 定义跳空比例常量
    GAP_DOWN_THRESHOLD = 0.95
    
    # 定义持有天数常量
    HOLD_DAYS = 5
    
    # 遍历数据目录，读取每只股票的交易数据
    data_dir = os.path.expanduser("~/.qlib/tushare_data2")
    all_files = [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.endswith(".csv")]
    df_list = []
    for file in all_files:
        stock_code = os.path.basename(file).replace(".csv", "")
        df_stock = pd.read_csv(file)
        df_list.append(df_stock)
        
    # 合并所有股票的交易数据
    df = pd.concat(df_list, ignore_index=True)
    df['date'] = pd.to_datetime(df['date'])  # 确保日期类型
    df.sort_values(['symbol', 'date'], inplace=True)
    

    
    # 计算前一天的最低价
    df['prev_low'] = df.groupby('symbol')['low'].shift(1)
    
    # 定义跳空低开的场景：当天开盘价低于前一天最低价5%以上
    df['is_gap_down'] = df['open'] < df['prev_low'] * GAP_DOWN_THRESHOLD
    
    # 统计跳空低开场景占比
    gap_down_ratio = df['is_gap_down'].mean()
    print(f"跳空低开场景占比: {gap_down_ratio:.2%}")
    
    # 定义oops场景：当天开盘价低于前一天最低价5%以上，并且当天最高价高于前一天最低价
    df['is_oops'] = df['is_gap_down'] & (df['high'] > df['prev_low'])
    
    # 统计oops数据在跳空低开场景中的占比
    oops_in_gap_down_ratio = df[df['is_gap_down']]['is_oops'].mean()
    print(f"在跳空低开场景中，oops场景占比: {oops_in_gap_down_ratio:.2%}")
    
    # 计算下n个交易日的收盘价
    df['next_close'] = df.groupby('symbol')['close'].shift(-HOLD_DAYS)  # 获取下n个交易日的收盘价

    # 2. 计算下n个交易日收盘相对前一个交易日最低价的收益率
    df['next_return'] = df['next_close'] / df['prev_low'] - 1

    # 3. 最后，再筛选出 'is_oops' 为 True 的行进行统计分析
    oops_df = df[df['is_oops']]
    
    # 统计is_st 和 is_new 的占比
    is_st_ratio = oops_df['is_st'].mean()
    is_new_ratio = oops_df['is_new'].mean()
    print(f"在oops场景下，is_st占比: {is_st_ratio:.2%}")
    print(f"在oops场景下，is_new占比: {is_new_ratio:.2%}")     
    
    # 排除is_st 和 is_new
    oops_df = oops_df[(oops_df['is_st'] == 0) & (oops_df['is_new'] == 0)]
    
    # 统计在oops场景下，后续看涨的概率
    bullish_prob = (oops_df['next_return'] > 0).mean()
    print(f"在oops场景下，后续看涨的概率为: {bullish_prob:.2%}")
    
    # 统计在oops场景下，正收益率的平均值
    avg_return = oops_df[oops_df['next_return'] > 0]['next_return'].mean()
    print(f"在oops场景下，正收益率的平均值为: {avg_return:.2%}")
    
    # 统计在oops场景下，负收益率的平均值
    avg_loss = oops_df[oops_df['next_return'] < 0]['next_return'].mean()
    print(f"在oops场景下，负收益率的平均值为: {avg_loss:.2%}")
    
    
if __name__ == "__main__":
    oops()