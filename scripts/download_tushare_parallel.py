import argparse
from datetime import datetime
import multiprocessing
import os
import re
import time
import pandas as pd
import tushare as ts

def get_stock_name(stock_code):
    """
    将 600000.SH 转换为 SH600000，000001.SZ 转换为 SZ000001。
    """
    code = str(stock_code).strip()
    if code.endswith('.SH'):
        return 'SH' + code[:-3]
    elif code.endswith('.SZ'):
        return 'SZ' + code[:-3]
    else:
        # 如果不符合常见规则，打印警告但不中断，尝试直接用原代码
        raise ValueError(f"无法识别的股票代码格式: {code}")

def download_daily(ts_pro,ts_code,start_date, end_date, target_dir):
    print(f"开始下载 {ts_code} 的数据...")
    symbol = get_stock_name(ts_code)
    
    # --- 1. 生成文件名 (核心修改点) ---
    file_name = symbol + '.daily.csv'
    file_path = os.path.join(target_dir, file_name)
    
    try:
        df_daily = ts_pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        print(f"{symbol} 的行情数据下载完成: {len(df_daily)} 行")
        df_daily.rename(columns={'ts_code': 'symbol', 'trade_date': 'date', 'vol': 'volume'}, inplace=True)
                
        # 检查是否有数据 (防止停牌或刚上市的股票)
        # if df_daily.empty:
        #     print(f"{ts_code} 数据为空，跳过。")
        #     return

        # --- 4. 数据合并与处理 ---
        df = df_daily
        
        # 将date格式有20000101转换为2000-01-01
        df['date'] = pd.to_datetime(df['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
        df['symbol'] = symbol
        
        # --- 6. 写入 CSV (核心修改点) ---
        # 按日期排序
        df.sort_values('date', inplace=True)
        # 保存，utf-8-sig 编码防止 Excel 打开中文乱码
        if os.path.exists(file_path):
            # 加载现有数据，检查是否有重复日期
            existing_df = pd.read_csv(file_path)
            # 追加新数据，去重后保存
            df = pd.concat([existing_df, df], ignore_index=True).drop_duplicates(subset=['date'])
            
        df.to_csv(file_path, index=False, encoding='utf-8-sig')        
        print(f"{symbol} ✅ 数据下载完成: {file_path} (共 {len(df)} 行)")
        
    except Exception as e:
        print(f"❌ 获取 {ts_code} 失败: {e}")
        
def download_factor(ts_pro,ts_code,start_date, end_date, target_dir):
    print(f"开始下载 {ts_code} 的数据...")
    symbol = get_stock_name(ts_code)
    
    # --- 1. 生成文件名 (核心修改点) ---
    file_name = symbol + '.factor.csv'
    file_path = os.path.join(target_dir, file_name)
    
    try:
        # 获取复权因子
        df_factor = ts_pro.adj_factor(ts_code=ts_code, start_date=start_date, end_date=end_date)
        print(f"{symbol} 的复权因子数据下载完成: {len(df_factor)} 行")
        df_factor.rename(columns={'ts_code': 'symbol','trade_date': 'date', 'adj_factor': 'factor'}, inplace=True)
        
        # 检查是否有数据 (防止停牌或刚上市的股票)
        # if df_factor.empty:
        #     print(f"{ts_code} 数据为空，跳过。")
        #     return

        # --- 4. 数据合并与处理 ---
        df = df_factor
        
        # 将date格式有20000101转换为2000-01-01
        df['date'] = pd.to_datetime(df['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
        df['symbol'] = symbol
        
        # --- 6. 写入 CSV (核心修改点) ---
        # 按日期排序
        df.sort_values('date', inplace=True)
        # 保存，utf-8-sig 编码防止 Excel 打开中文乱码
        if os.path.exists(file_path):
            # 加载现有数据，检查是否有重复日期
            existing_df = pd.read_csv(file_path)
            # 追加新数据，去重后保存
            df = pd.concat([existing_df, df], ignore_index=True).drop_duplicates(subset=['date'])
            
        df.to_csv(file_path, index=False, encoding='utf-8-sig')        
        print(f"{symbol} ✅ 数据下载完成: {file_path} (共 {len(df)} 行)")
        
    except Exception as e:
        print(f"❌ 获取 {ts_code} 失败: {e}")
        
        
def download_daily_basic(ts_pro,ts_code,start_date, end_date, target_dir):
    print(f"开始下载 {ts_code} 的数据...")
    symbol = get_stock_name(ts_code)
    
    # --- 1. 生成文件名 (核心修改点) ---
    file_name = symbol + '.daily_basic.csv'
    file_path = os.path.join(target_dir, file_name)
    
    try:
        # --- 3. 获取基本面数据 ---
        df_basic = ts_pro.daily_basic(ts_code=ts_code, start_date=start_date, end_date=end_date)
        print(f"{symbol} 的基本面数据下载完成: {len(df_basic)} 行")
        df_basic.rename(columns={'ts_code': 'symbol','trade_date': 'date'}, inplace=True)
        df_basic.drop(columns=['close'], inplace=True)
        
        # 检查是否有数据 (防止停牌或刚上市的股票)
        # if df_basic.empty:
        #     print(f"{ts_code} 数据为空，跳过。")
        #     return

        # --- 4. 数据合并与处理 ---
        df = df_basic
        
        # 将date格式有20000101转换为2000-01-01
        df['date'] = pd.to_datetime(df['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
        df['symbol'] = symbol
        
        # --- 6. 写入 CSV (核心修改点) ---
        # 按日期排序
        df.sort_values('date', inplace=True)
        # 保存，utf-8-sig 编码防止 Excel 打开中文乱码
        if os.path.exists(file_path):
            # 加载现有数据，检查是否有重复日期
            existing_df = pd.read_csv(file_path)
            # 追加新数据，去重后保存
            df = pd.concat([existing_df, df], ignore_index=True).drop_duplicates(subset=['date'])
            
        df.to_csv(file_path, index=False, encoding='utf-8-sig')        
        print(f"{symbol} ✅ 数据下载完成: {file_path} (共 {len(df)} 行)")
        
    except Exception as e:
        print(f"❌ 获取 {ts_code} 失败: {e}")
        
        
def download_st_data(ts_pro,ts_code,start_date, end_date, target_dir):
    """下载ST数据"""
    print(f"开始下载 {ts_code} 的ST数据...")
    try:
        df_st = ts_pro.stock_st(ts_code=ts_code, start_date=start_date, end_date=end_date)
        symbol = get_stock_name(ts_code)    
        file_name = symbol + '.st.csv'
        file_path = os.path.join(target_dir, file_name)
        df_st.rename(columns={'ts_code': 'symbol', 'trade_date': 'date'}, inplace=True)
        df_st['date'] = pd.to_datetime(df_st['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
        df_st['symbol'] = symbol
        # 将df_st按日期排序
        df_st.sort_values('date', inplace=True)
        if os.path.exists(file_path):
            # 加载现有数据，检查是否有重复日期
            existing_df = pd.read_csv(file_path)
            # 追加新数据，去重后保存
            df_st = pd.concat([existing_df, df_st], ignore_index=True).drop_duplicates(subset=['date'])
        df_st.to_csv(file_path, index=False, encoding='utf-8-sig')        
        print(f"{symbol} ✅ ST数据下载完成: {file_path} (共 {len(df_st)} 行)")
    except Exception as e:
        print(f"❌ 获取 {ts_code} 的ST数据失败: {e}")
        
    
def batch_download_stock_info(stock_list, start_date, end_date, target_dir,single_download_func):
    """通过tushare接口下载历史数据，并转化成qlib数据格式"""
    
    # 初始化 Tushare API
    MY_TOKEN = '0cde551845a233915fa6d31f169cc6a65f15f32007cc8b79371b6d8e'
    ts.set_token(MY_TOKEN)
    ts_pro = ts.pro_api()
    
    # 便利股票列表，下载数据
    for idx, row in stock_list.iterrows():
        single_download_func(ts_pro,ts_code=row['ts_code'], start_date=start_date, end_date=end_date, target_dir=target_dir)
        time.sleep(0.15) 
    print("🎉 所有任务处理完毕！")
    
def download_stock_parallel(stock_list,start_date, end_date, target_dir):
    p_list = []
    
    p_daily = multiprocessing.Process(
        target=batch_download_stock_info, args=(stock_list,start_date, end_date, target_dir,download_daily))  
    p_factor = multiprocessing.Process(
        target=batch_download_stock_info, args=(stock_list,start_date, end_date, target_dir,download_factor))
    p_daily_basic = multiprocessing.Process(
        target=batch_download_stock_info, args=(stock_list,start_date, end_date, target_dir,download_daily_basic))
    p_st = multiprocessing.Process(
        target=batch_download_stock_info, args=(stock_list,start_date, end_date, target_dir,download_st_data))
    
    p_list.extend([p_daily, p_factor, p_daily_basic, p_st])
    
    for p in p_list:
        p.start()

    for p in p_list:
        p.join()   


def merge_stock_data(ts_code, list_date,download_dir,data_dir):
    """通过tushare接口下载历史数据，并转化成qlib数据格式"""
    print(f"开始合并 {ts_code} 的数据...")
    
    daily_csv_file = os.path.join(download_dir, get_stock_name(ts_code) + '.daily.csv')
    factor_csv_file = os.path.join(download_dir, get_stock_name(ts_code) + '.factor.csv')
    daily_basic_csv_file = os.path.join(download_dir, get_stock_name(ts_code) + '.daily_basic.csv')
    st_csv_file = os.path.join(download_dir, get_stock_name(ts_code) + '.st.csv')
    if not os.path.exists(daily_csv_file) or \
       not os.path.exists(factor_csv_file) or \
       not os.path.exists(daily_basic_csv_file) or \
       not os.path.exists(st_csv_file):
        print(f"缺少 {ts_code} 的数据文件，无法合并。请确保 daily、factor、daily_basic 和 st 数据都已下载。")
        return
    
    # 读取数据
    df_daily = pd.read_csv(daily_csv_file)
    df_factor = pd.read_csv(factor_csv_file)    
    df_basic = pd.read_csv(daily_basic_csv_file)
    df_st = pd.read_csv(st_csv_file)
    
    # 检查数据长度是否一致
    if len(df_daily) != len(df_basic) or len(df_daily) > len(df_factor):  
        print(f"{ts_code} 的数据长度不匹配，无法合并。")
        return
    
    # --- 4. 数据合并与处理 ---
    print(f"正在合并 {ts_code} 的数据...")
    df = pd.merge(df_daily, df_basic, on=['symbol', 'date'], how='inner')
    df = pd.merge(df, df_factor, on=['symbol', 'date'], how='inner')
    df = pd.merge(df, df_st, on=['symbol', 'date'], how='left')  # ST数据可能不完整，使用左连接保留所有行情数据
    
    # 计算前复权因子
    base_factor = df_factor['factor'].iloc[-1] # 以最后一个交易日的复权因子为基准
    # 计算前复权数值，并保留两位小数
    df['factor'] = (df['factor'] / base_factor).round(2)
    # 计算前复权价格和调整成交量
    df['open'] = df['open'] * df['factor']
    df['high'] = df['high'] * df['factor']
    df['low'] = df['low'] * df['factor']
    df['close'] = df['close'] * df['factor']
    df['volume'] = df['volume'] / df['factor']
    
    # 判断是否是次新股数据（上市不足一年的股票）
    condition = pd.to_datetime(df['date'], format='%Y-%m-%d', errors='coerce') < \
        (pd.to_datetime(list_date, format='%Y%m%d') + pd.Timedelta(days=365))
    df['is_new'] = 0
    df.loc[condition, 'is_new'] = 1
        
    # 判断是否是ST股票数据
    df['is_st'] = df['type'].apply(lambda x: 1 if x == 'ST' else 0)
    
    # --- 6. 写入 CSV (核心修改点) ---
    # 按日期排序
    df.sort_values('date', inplace=True)
    # 选择需要保存的列
    df = df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'factor']]
    csv_path = os.path.join(data_dir, get_stock_name(ts_code) + '.csv')

    # 保存，utf-8-sig 编码防止 Excel 打开中文乱码
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"{ts_code} ✅ 数据合并完成: {csv_path} (共 {len(df)} 行)")
    
    
def merge_csv_files(stock_list,download_dir,data_dir):
    """通过tushare接口下载历史数据，并转化成qlib数据格式"""
    print(f"开始合并csv文件中的数据 ...")
    # 便利股票列表，下载数据
    for idx, row in stock_list.iterrows():
        merge_stock_data(row['ts_code'], row['list_date'], download_dir, data_dir)
        
    print("🎉 数据合并完毕！")
    
    
if __name__ == "__main__":
    # 支持子命令 stock 和 index，分别用于下载股票数据和指数数据
    # stock命令需要参数 start_date, end_date, target_dir
    # index命令需要参数 index_code, start_date, end_date, target_dir
    parser = argparse.ArgumentParser(description="下载新浪数据并转化成qlib数据格式")
    parser.add_argument("--start_date", type=str, help="起始日期，格式为YYYY-MM-DD")
    parser.add_argument("--end_date", type=str, help="结束日期，格式为YYYY-MM-DD")
    parser.add_argument("--download_dir", type=str, help="保存下载数据的目标目录")
    parser.add_argument("--data_dir", type=str, help="保存合并数据的目标目录")
    
    # 如果输入参数不对，提示usage
    args = parser.parse_args()
    if not all([args.start_date, args.end_date, args.download_dir, args.data_dir]):
        parser.print_usage()
        exit(1)
    
    # 检查参数数量，如果参数不足，显示usage
    if not all([args.start_date, args.end_date, args.download_dir]):
        parser.print_usage()
        exit(1)

    start_date = args.start_date
    end_date = args.end_date
    download_dir = args.download_dir
    data_dir = args.data_dir
    
    # 请在此处填入你的 Tushare Token
    MY_TOKEN = '0cde551845a233915fa6d31f169cc6a65f15f32007cc8b79371b6d8e'
    ts.set_token(MY_TOKEN)
    ts_pro = ts.pro_api()

    # ================= 2. 获取股票池 =================
    print(f"正在获取股票基础列表...")
    # 获取所有上市股票
    stock_list = ts_pro.stock_basic(exchange='', list_status='L', fields='ts_code, name, list_date')

    # 筛选沪深 A 股
    stock_list = stock_list[stock_list['ts_code'].str.endswith('.SH') | stock_list['ts_code'].str.endswith('.SZ')]
    stock_list = stock_list.reset_index(drop=True)
    
    # print(f"开始下载股票数据 ......")
    # download_stock_parallel(stock_list,start_date, end_date, target_dir)
    # print("所有下载任务已完成。")
    
    # 合并数据
    print(f"开始合并股票数据 ......")
    merge_csv_files(stock_list, download_dir, data_dir)
    print("所有数据合并任务已完成。")
    
    

    
    
   

        