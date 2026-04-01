import argparse
from datetime import datetime
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

def download_stock_info(ts_pro,row,start_date, end_date, target_dir):
    print(f"开始下载 {row['ts_code']} 的数据...")
    ts_code = row['ts_code']       # 例如: 600000.SH
    name = row['name']             # 股票名称
    list_date = row['list_date']   # 上市日期
    symbol = get_stock_name(ts_code)
    
    
    # 跳过ST股票和次新股（上市不足一年的股票），因为它们的数据可能不完整或不稳定
    if 'ST' in name or '退' in name:
        print(f"跳过 {ts_code} ({name})，因为它是ST股票。")
        return
    
    # 跳过次新股
    if (datetime.now() - datetime.strptime(list_date, '%Y%m%d')).days < 365:
        print(f"跳过 {ts_code} ({name})，因为它是次新股（上市不足一年）。")
        return
    
    # --- 1. 生成文件名 (核心修改点) ---
    file_name = symbol + '.csv'
    file_path = os.path.join(target_dir, file_name)
    
    try:
        df_daily = ts_pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        print(f"{symbol} 的行情数据下载完成: {len(df_daily)} 行")
        df_daily.rename(columns={'ts_code': 'symbol', 'trade_date': 'date', 'vol': 'volume'}, inplace=True)
                
        # --- 2. 获取前复权行情数据 ---
        # df_daily = ts_pro.pro_bar(ts_code=ts_code, adj='qfq', start_date=start_date, end_date=end_date)
        # print(f"{symbol} 的行情数据下载完成: {len(df_daily)} 行")
        # df_daily.rename(columns={'trade_date': 'date', 'ts_code': 'symbol', 'vol': 'volume'}, inplace=True)
        
        # 获取复权因子
        df_factor = ts_pro.adj_factor(ts_code=ts_code, start_date=start_date, end_date=end_date)
        print(f"{symbol} 的复权因子数据下载完成: {len(df_factor)} 行")
        df_factor.rename(columns={'ts_code': 'symbol','trade_date': 'date', 'adj_factor': 'factor'}, inplace=True)
        
        # --- 3. 获取基本面数据 ---
        df_basic = ts_pro.daily_basic(ts_code=ts_code, start_date=start_date, end_date=end_date)
        print(f"{symbol} 的基本面数据下载完成: {len(df_basic)} 行")
        df_basic.rename(columns={'ts_code': 'symbol','trade_date': 'date'}, inplace=True)
        df_basic.drop(columns=['close'], inplace=True)
        
        # 检查是否有数据 (防止停牌或刚上市的股票)
        if df_daily.empty or df_basic.empty:
            print(f"{ts_code} 数据为空，跳过。")
            return

        # --- 4. 数据合并与处理 ---
        print(f"正在合并 {symbol} 的数据...")
        df = pd.merge(df_daily, df_basic, on=['symbol', 'date'], how='inner')
        df = pd.merge(df, df_factor, on=['symbol', 'date'], how='inner')
        
        # 将date格式有20000101转换为2000-01-01
        df['date'] = pd.to_datetime(df['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
        df['symbol'] = symbol
        df['name'] = name
        df['list_date'] = list_date
        
        # 计算前复权因子
        base_factor = df_factor['factor'].iloc[0] # 以最后一个交易日的复权因子为基准
        df['factor'] = df['factor'] / base_factor
        # 计算前复权价格和调整成交量
        df['open'] = df['open'] * df['factor']
        df['high'] = df['high'] * df['factor']
        df['low'] = df['low'] * df['factor']
        df['close'] = df['close'] * df['factor']
        df['volume'] = df['volume'] / df['factor']
        
        # --- 6. 写入 CSV (核心修改点) ---
        # 按日期排序
        df.sort_values('date', inplace=True)
        # 保存，utf-8-sig 编码防止 Excel 打开中文乱码
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        
        print(f"{symbol} ✅ 下载成功: {file_name} (共 {len(df)} 行)")
        
    except Exception as e:
        print(f"❌ 获取 {ts_code} 失败: {e}")
    
def batch_download_stock_info(ts_pro,start_date, end_date, target_dir):
    """通过tushare接口下载历史数据，并转化成qlib数据格式"""

    # ================= 2. 获取股票池 =================
    print(f"正在获取股票基础列表...")
    # 获取所有上市股票
    stock_list = ts_pro.stock_basic(exchange='', list_status='L', fields='ts_code, name, list_date')

    # 筛选沪深 A 股
    stock_list = stock_list[stock_list['ts_code'].str.endswith('.SH') | stock_list['ts_code'].str.endswith('.SZ')]
    stock_list = stock_list.reset_index(drop=True)

    print(f"共找到 {len(stock_list)} 只沪深股票，开始下载...")
    # 便利股票列表，下载数据
    for idx, row in stock_list.iterrows():
        download_stock_info(ts_pro,row=row, start_date=start_date, end_date=end_date, target_dir=target_dir)
        # --- 7. 频率控制，非常重要！防止触发 Tushare 的积分限流
        time.sleep(0.15) 
    print("🎉 所有任务处理完毕！")
    
    
def download_st_data(ts_pro,stock_list,start_date, end_date, target_dir):
    """下载ST数据"""
    print(f"开始获取ST数据...")
    # 遍历股票列表，下载ST数据
    for idx, row in stock_list.iterrows():
        ts_code = row['ts_code']
        print(f"开始下载 {ts_code} 的ST数据...")
        df_st = ts_pro.stock_st(ts_code=ts_code, start_date=start_date, end_date=end_date)
        try:
            symbol = get_stock_name(ts_code)    
            file_name = symbol + '.st.csv'
            file_path = os.path.join(target_dir, file_name)
            df_st.rename(columns={'ts_code': 'symbol', 'trade_date': 'date'}, inplace=True)
            df_st['date'] = pd.to_datetime(df_st['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
            df_st['symbol'] = symbol
            # 将df_st按日期排序
            df_st.sort_values('date', inplace=True)
            df_st.to_csv(file_path, index=False, encoding='utf-8-sig')
            print(f"{symbol} ✅ 下载成功: {file_path} (共 {len(df_st)} 行)")
        except Exception as e:
            print(f"❌ 获取 {ts_code} 的ST数据失败: {e}")
        

def check_downloaded_files(stock_list, target_dir):
    """检查下载的文件是否完整"""    
    # 检查文件是否有缺失
    # target_dir 目录下应该有 stock_list 中每只股票对应的 4 类csv 文件
    # 文件名为 SH600000.daily.csv SH600000.daily_basic.csv SH600000.factor.csv SH600000.st.csv
    expected_files = []
    for idx, row in stock_list.iterrows():
        ts_code = row['ts_code']
        try:
            symbol = get_stock_name(ts_code)
            expected_files.append(symbol + '.daily.csv')
            expected_files.append(symbol + '.daily_basic.csv')
            expected_files.append(symbol + '.factor.csv')
            expected_files.append(symbol + '.st.csv')
        except Exception as e:
            print(f"❌ 生成 {ts_code} 的预期文件名失败: {e}")
    existing_files = set(os.listdir(target_dir))
    missing_files = [f for f in expected_files if f not in existing_files]
    if missing_files:
        print(f"⚠️ 发现 {len(missing_files)} 个缺失文件:")
        for f in missing_files:
            print(f"  - {f}")
    else:
        print("✅ 所有预期文件都已成功下载！")


if __name__ == "__main__":
    # 支持子命令 stock 和 index，分别用于下载股票数据和指数数据
    # stock命令需要参数 start_date, end_date, target_dir
    # index命令需要参数 index_code, start_date, end_date, target_dir
    parser = argparse.ArgumentParser(description="下载新浪数据并转化成qlib数据格式")
    parser.add_argument("--start_date", type=str, help="起始日期，格式为YYYY-MM-DD")
    parser.add_argument("--end_date", type=str, help="结束日期，格式为YYYY-MM-DD")
    parser.add_argument("--target_dir", type=str, help="保存下载数据的目标目录")
    
    # 如果输入参数不对，提示usage
    args = parser.parse_args()
    if not all([args.start_date, args.end_date, args.target_dir]):
        parser.print_usage()
        exit(1)
    
    # 检查参数数量，如果参数不足，显示usage
    if not all([args.start_date, args.end_date, args.target_dir]):
        parser.print_usage()
        exit(1)

    start_date = args.start_date
    end_date = args.end_date
    target_dir = args.target_dir
    
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
    
    # print(f"命令: 开始下载股票数据 ......")
    # batch_download_stock_info(
    #     ts_pro=ts_pro,
    #     start_date=start_date, 
    #     end_date=end_date, 
    #     target_dir=target_dir)
    
    # print(f"开始下载ST数据 ......")
    # download_st_data(
    #     ts_pro=ts_pro,
    #     stock_list=stock_list,
    #     start_date=start_date, 
    #     end_date=end_date, 
    #     target_dir=target_dir)
    
    print(f"开始检查下载的文件 ......")
    check_downloaded_files(stock_list, target_dir)

    
    
   

        