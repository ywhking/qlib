import argparse
import csv
import json
import pandas as pd
from collections import defaultdict

def convert_symbol(symbol: str) -> str:
    """
    转换股票代码格式：
    SH603007 -> 603007.XSHG
    SZ000981 -> 000981.XSHE
    """
    if symbol.startswith("SH"):
        return f"{symbol[2:]}.XSHG"
    elif symbol.startswith("SZ"):
        return f"{symbol[2:]}.XSHE"
    else:
        # 如果不符合前缀，原样返回或抛出异常，这里选择原样返回以防数据异常
        return symbol

def csv_to_custom_json(csv_file_path: str, json_file_path: str):
    """将 CSV 文件转换为指定格式的 JSON 文件  """
    # 1. 读取 CSV 文件
    df = pd.read_csv(csv_file_path)
    # 按date分组，按score排序
    df = df.sort_values(by=['date', 'score'], ascending=[True, False]) 
    # 选取每日0.10 到 0.05之间的记录，最多10条
    # df = df[(df['score'] >= 0.05) & (df['score'] <= 0.10)] 
    # # df = df[(df['score'] >= 0.05)]
    df = df.groupby('date').head(50)
    # 转换symbol格式
    df['symbol'] = df['symbol'].apply(convert_symbol)

    # 保存到目标文件中
    result_dict = df.groupby('date')['symbol'].apply(list).to_dict()
    lines = []
    for date, symbols in result_dict.items():
        # 构造单行 JSON: {"日期": ["代码1", "代码2"]}
        line = json.dumps({date: symbols}, separators=(',', ':'), ensure_ascii=False)
        # 去掉首尾的花括号
        line = line[1:-1]
        lines.append(line)

    # 用换行符将所有行拼接起来，多行之间逗号分隔
    compact_multiline_json = ",\n".join(lines)
    
    # 首尾添加花括号，形成完整的 JSON 对象
    compact_multiline_json = "{\n" + compact_multiline_json + "\n}"
    print(compact_multiline_json)

    with open(json_file_path, 'w', encoding='utf-8') as f:
        f.write(compact_multiline_json)
     

if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="将 CSV 文件转换为指定格式的 JSON 文件")
    parser.add_argument("--csv_path", type=str, required=True, help="输入的 CSV 文件路径")
    parser.add_argument("--json_path", type=str, required=True, help="输出的 JSON 文件路径")
    args = parser.parse_args()
    
    # 参数数量检查
    if not args.csv_path or not args.json_path:
        parser.print_help()
        exit(1)
    
    input_csv = args.csv_path
    output_json = args.json_path
    
    # 执行转换
    csv_to_custom_json(input_csv, output_json)

