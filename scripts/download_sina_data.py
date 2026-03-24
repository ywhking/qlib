import argparse
import re
import pandas as pd
import akshare as ak

def get_stock_name(stock_code):
    """
    根据股票代码判断市场前缀 (sz/sh)。
    注意：ak.stock_zh_a_daily 其实通常只需要纯数字代码，
    但为了逻辑严谨，这里保留判断逻辑供参考。
    """
    code = str(stock_code).strip()
    if code.startswith('00') or code.startswith('30'):
        return 'sz' + code
    elif code.startswith('60') or code.startswith('68'):
        return 'sh' +  code
    else:
        # 如果不符合常见规则，打印警告但不中断，尝试直接用原代码
        raise ValueError(f"无法识别的股票代码格式: {code}")
    
def download_index_info(index_code,start_date, end_date, target_dir):
    """通过miniQMT客户端下载历史数据，并转化成qlib数据格式"""
    
    print(f"开始下载{index_code}指数数据...")
    
    try:
    
        # 获取原始数据，用于计算复权系数
        original_stock_df= ak.stock_zh_index_daily(symbol=stock_name, start_date=start_date, end_date=end_date, adjust="")
        
        # 获取前复权数据
        adjusted_stock_df= ak.stock_zh_a_daily(symbol=stock_name, start_date=start_date, end_date=end_date, adjust="qfq")
        
        # 计算复权系数
        adjusted_stock_df['factor'] = adjusted_stock_df['close'] / original_stock_df['close']
        
        # 将成交量调整为前复权的成交量
        adjusted_stock_df['volume'] = original_stock_df['volume'] / adjusted_stock_df['factor']
        
        # 调整流通股本
        adjusted_stock_df['outstanding_share'] = original_stock_df['outstanding_share'] / adjusted_stock_df['factor']
        
        # 添加symbol列
        adjusted_stock_df['symbol'] = stock_name.upper()

    
        # 将前复权数据保存成csv格式
        adjusted_stock_df.to_csv(f"{target_dir}/{stock_name}.csv",index=False,encoding='utf-8-sig')
        print(f"{stock_name} data has been downloaded and saved to {target_dir}/{stock_name}.csv")
        
        # 将原始数据保存成csv格式
        # original_stock_df.to_csv(f"{target_dir}/{stock_name}_original.csv",index=False,encoding='utf-8-sig')
    
    except Exception as e:
        print(f"下载{stock_name}数据时发生错误: {e}")
        
def download_stock_info(stock_code,start_date, end_date, target_dir):
    """通过miniQMT客户端下载历史数据，并转化成qlib数据格式"""

    stock_name = None
    try :
        stock_name = get_stock_name(stock_code)
    except ValueError as e:
        print(e)
    
    print(f"开始下载{stock_name}数据...")
    
    try:
    
        # 获取原始数据，用于计算复权系数
        original_stock_df= ak.stock_zh_a_daily(symbol=stock_name, start_date=start_date, end_date=end_date, adjust="")
        
        # 获取前复权数据
        adjusted_stock_df= ak.stock_zh_a_daily(symbol=stock_name, start_date=start_date, end_date=end_date, adjust="qfq")
        
        # 计算复权系数
        adjusted_stock_df['factor'] = adjusted_stock_df['close'] / original_stock_df['close']
        
        # 将成交量调整为前复权的成交量
        adjusted_stock_df['volume'] = original_stock_df['volume'] / adjusted_stock_df['factor']
        
        # 调整流通股本
        adjusted_stock_df['outstanding_share'] = original_stock_df['outstanding_share'] / adjusted_stock_df['factor']
        
        # 添加symbol列
        adjusted_stock_df['symbol'] = stock_name.upper()

    
        # 将前复权数据保存成csv格式
        adjusted_stock_df.to_csv(f"{target_dir}/{stock_name}.csv",index=False,encoding='utf-8-sig')
        print(f"{stock_name} data has been downloaded and saved to {target_dir}/{stock_name}.csv")
        
        # 将原始数据保存成csv格式
        # original_stock_df.to_csv(f"{target_dir}/{stock_name}_original.csv",index=False,encoding='utf-8-sig')
    
    except Exception as e:
        print(f"下载{stock_name}数据时发生错误: {e}")
            
    
def batch_download_stock_info(start_code,end_code, start_date, end_date, target_dir):
    """通过miniQMT客户端下载历史数据，并转化成qlib数据格式"""

    # 获取A股的成分股列表
    stock_list = ak.stock_info_a_code_name()

    # 下载股票数据，将下载的数据转化成csv格式，并保存到target_dir
    downloaded_count = 0
    for stock_code in stock_list['code']:
        # 比较股票代码，跳过小于start_code的股票
        if stock_code < start_code or stock_code > end_code:
            continue
        stock_name = None
        try :
            stock_name = get_stock_name(stock_code)
        except ValueError as e:
            print(e)
            continue
        try:
            download_stock_info(stock_code, start_date, end_date, target_dir)
            print(f"finished {downloaded_count}/{len(stock_list)}")
            downloaded_count += 1
        except Exception as e:
            print(f"下载{stock_name}数据时发生错误: {e}")
        
if __name__ == "__main__":
    # 支持子命令 stock 和 index，分别用于下载股票数据和指数数据
    # stock命令需要参数 start_code, end_code, start_date, end_date, target_dir
    # index命令需要参数 index_code, start_date, end_date, target_dir
    parser = argparse.ArgumentParser(description="下载新浪数据并转化成qlib数据格式")
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    stock_parser = subparsers.add_parser("stock", help="下载股票数据")
    stock_parser.add_argument("--start_code", type=str, help="起始股票代码")
    stock_parser.add_argument("--end_code", type=str, help="结束股票代码")
    stock_parser.add_argument("--start_date", type=str, help="起始日期，格式为YYYY-MM-DD")
    stock_parser.add_argument("--end_date", type=str, help="结束日期，格式为YYYY-MM-DD")
    stock_parser.add_argument("--target_dir", type=str, help="保存下载数据的目标目录")
    
    index_parser = subparsers.add_parser("index", help="下载指数数据")
    index_parser.add_argument("--index_code", type=str, help="指数代码")
    index_parser.add_argument("--start_date", type=str, help="起始日期，格式为YYYY-MM-DD")
    index_parser.add_argument("--end_date", type=str, help="结束日期，格式为YYYY-MM-DD")
    index_parser.add_argument("--target_dir", type=str, help="保存下载数据的目标目录")
    
    # 如果输入参数不对，提示usage
    args = parser.parse_args()
    if not args.command:
        parser.print_usage()
        exit(1)
        
    if args.command == "stock":
        # 检查参数数量，如果参数不足，显示usage
        if not all([args.start_code, args.end_code, args.start_date, args.end_date, args.target_dir]):
            parser.print_usage()
            exit(1)

            start_code = args.start_code
            end_code = args.end_code
            start_date = args.start_date
            end_date = args.end_date
            target_dir = args.target_dir
            
            batch_download_stock_info(
                start_code=start_code, 
                end_code=end_code, 
                start_date=start_date, 
                end_date=end_date, 
                target_dir=target_dir)
   
    elif args.command == "index":
        # 检查参数数量，如果参数不足，显示usage
        if not all([args.index_code, args.start_date, args.end_date, args.target_dir]):
            parser.print_usage()
            exit(1)
            
        index_code = args.index_code
        start_date = args.start_date
        end_date = args.end_date
        target_dir = args.target_dir
        download_index_info(index_code, start_date, end_date, target_dir)
        
    else :
        parser.print_usage()
        exit(1)
        