import pandas as pd
import pickle
import argparse

def save_pkl_to_csv(pkl_path, csv_path):
    """
    将 Qlib 的 pred.pkl 转换为聚宽可用的 CSV 文件。
    自动处理：MultiIndex 重置、日期格式化、股票代码转换 (SH600000 -> 600000.XSHG)。
    """
    # 1. 读取 pkl
    with open(pkl_path, "rb") as f:
        df = pickle.load(f)
    
    # 2. 重置索引 (datetime, instrument) -> 列
    df = df.reset_index()
    df.columns = ["date", "symbol", "score"]
    
    # 按日期删选出score > 0.2的前5只股票
    df = df[df["score"] > 2]
    df = df.groupby("date").apply(lambda x: x.nlargest(5, "score")).reset_index(drop=True)
    
    # 5. 保存 CSV
    df.to_csv(csv_path, index=False)
    print(f"✅ 成功保存至: {csv_path} (共 {len(df)} 条记录)")

# main
if __name__ == "__main__":
    # 通过命令行参数获取 pkl 路径和 csv 路径
    parser = argparse.ArgumentParser(description="将 Qlib 的 pred.pkl 转换为聚宽可用的 CSV 文件")
    parser.add_argument("--pkl_path", type=str, required=True, help="输入的 pkl 文件路径")
    parser.add_argument("--csv_path", type=str, required=True, help="输出的 CSV 文件路径")
    args = parser.parse_args()
    
    # 参数数量检查
    if not args.pkl_path or not args.csv_path:
        parser.print_help()
        exit(1)
        
    
    pkl_file = args.pkl_path
    csv_file = args.csv_path
    save_pkl_to_csv(pkl_file, csv_file)