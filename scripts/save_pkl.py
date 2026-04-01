import os
import pickle
import sys
import pandas as pd

def save_to_csv(pkl_file_path, csv_file_path):
    try:
        with open(pkl_file_path, 'rb') as f:
            # 尝试直接加载
            data = pickle.load(f)
    except Exception as e:
        print(f"错误: 无法加载 pkl 文件: {e}")
        raise e
    
    # 3. 按日期删选出score > 0.05的记录
    df = data
    df = df.reset_index()
    df.columns = ["date", "symbol", "score"]
    # df = df[df["score"] > 0.05]

    # 4. 保存为 .csv 文件
    df.to_csv(csv_file_path, index=False)
    
# main
if __name__ == "__main__":
    # 检查参数数量，提示用户正确使用
    if len(sys.argv) < 3:
        print("用法: python save_pkl.py <input.pkl> <output.csv>")
        print("示例: python save_pkl.py pred.pkl pred.csv")
        sys.exit(1) 
        
    # 通过命令行参数获取文件路径
    pkl_file_path = sys.argv[1]
    csv_file_path = sys.argv[2]
    
    # 检查文件是否存在
    if not os.path.isfile(pkl_file_path):
        print(f"错误: 输入文件不存在: {pkl_file_path}")
        sys.exit(1) 
    
    save_to_csv(pkl_file_path, csv_file_path)
    print(f"转换成功！文件已保存为: {csv_file_path}")