import re
import pandas as pd
from xtquant import xtdata

def download(target_dir="C:\\Users\\ywhki\\.qlib\\qmt_data"):
    """通过miniQMT客户端下载历史数据，并转化成qlib数据格式"""

    from xtquant import xtdata
    
    # 获取A股的成分股列表
    sector = '沪深A股'
    stock_list = xtdata.get_stock_list_in_sector(sector)

    # 下载历史数据
    for stock_name in stock_list:
        xtdata.download_history_data(stock_name, period='1d')
    
    # 将下载的数据转化成csv格式，并保存到target_dir
    downloaded_count = 0
    for stock_name in stock_list:
        # 获取原始数据，用于计算复权因子
        original_stock_info= xtdata.get_local_data(
            stock_list=[stock_name], 
            field_list=['open','close','high','low','volume'], 
            period='1d', 
            count=-1, 
            dividend_type='none', 
            fill_data=True)
        original_stock_df = original_stock_info[stock_name]
        
        # 获取前复权数据
        adjusted_stock_info= xtdata.get_local_data(
            stock_list=[stock_name], 
            field_list=['open','close','high','low','volume'], 
            period='1d', 
            count=-1, 
            dividend_type='front', 
            fill_data=True)
        
        adjusted_stock_df = adjusted_stock_info[stock_name]
        # 日期属性
        adjusted_stock_df.index.name = 'date'
        adjusted_stock_df.index = pd.to_datetime(adjusted_stock_df.index)
        symbol_value = re.sub(r'(.*)\.(.*)', r'\2\1', stock_name)
        # 股票代码属性
        adjusted_stock_df['symbol'] = symbol_value
        # 复权因子
        adjusted_stock_df['factor'] = adjusted_stock_df['close'] / original_stock_df['close']
        
        # 将前复权数据保存成csv格式
        adjusted_stock_df.to_csv(f"{target_dir}/{stock_name}.csv",index=True,encoding='utf-8-sig')
        print(f"{stock_name} data has been downloaded and saved to {target_dir}/{stock_name}.csv")
        
        downloaded_count += 1
        print(f"finished {downloaded_count}/{len(stock_list)}")
        # break
        
if __name__ == "__main__":
    download()