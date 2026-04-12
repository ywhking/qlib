import argparse
import tushare as ts
import pandas as pd

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

if __name__ == "__main__":
    # 支持子命令 stock 和 index，分别用于下载股票数据和指数数据
    # stock命令需要参数 start_date, end_date, target_dir
    # index命令需要参数 index_code, start_date, end_date, target_dir
    parser = argparse.ArgumentParser(description="下载新浪数据并转化成qlib数据格式")
    parser.add_argument("--index_code", type=str, help="指数代码，例如 '000300.SH' 表示沪深300指数")
    parser.add_argument("--start_date", type=str, help="起始日期，格式为YYYY-MM-DD")
    parser.add_argument("--end_date", type=str, help="结束日期，格式为YYYY-MM-DD")
    parser.add_argument("--all_path", type=str, help="包含所有股票交易日期数据的文件路径")
    parser.add_argument("--index_path", type=str, help="包含指数成分股数据的文件路径")
    
    # 如果输入参数不对，提示usage
    args = parser.parse_args()
    if not all([args.index_code, args.start_date, args.end_date, args.all_path, args.index_path]):
        parser.print_usage()
        exit(1)
    
    index_code = args.index_code    
    start_date = args.start_date
    end_date = args.end_date
    all_path = args.all_path
    index_path = args.index_path
    
    # 请在此处填入你的 Tushare Token
    MY_TOKEN = '0cde551845a233915fa6d31f169cc6a65f15f32007cc8b79371b6d8e'
    ts.set_token(MY_TOKEN)
    ts_pro = ts.pro_api()
    
    index_con_df = ts_pro.index_weight(index_code=index_code, start_date=start_date, end_date=end_date)
    index_con_df['con_code'] = index_con_df['con_code'].apply(get_stock_name)
    
    all_df = pd.read_csv(
        all_path, 
        header=None,
        names=['ts_code', 'start_date', 'end_date'],
        sep="\t")
    
    # 过滤数据，只保留在指数成分股列表中的股票数据
    csi_df = all_df[all_df['ts_code'].isin(index_con_df['con_code'])]
    
    # 保存过滤后的数据到新的CSV文件
    csi_df.to_csv(index_path, index=False, header=False, sep="\t")
    
    
    
    
