import argparse
import csv
import json
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
    # 使用字典存储数据，key为日期，value为列表 [(score, symbol), ...]
    data_by_date = defaultdict(list)

    try:
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                date = row['date']
                symbol = row['symbol']
                try:
                    score = float(row['score'])
                except ValueError:
                    print(f"警告：跳过无效分数行 {row}")
                    continue
                
                # 存储元组以便后续排序
                data_by_date[date].append((score, symbol))

        # 处理数据：排序并转换格式
        result = {}
        
        # 如果需要保持日期的顺序（如CSV中的出现顺序），可以使用 list(data_by_date.keys())
        # 如果需要日期按时间排序，可以使用 sorted(data_by_date.keys())
        sorted_dates = sorted(data_by_date.keys())

        for date in sorted_dates:
            items = data_by_date[date]
            
            # 核心逻辑：按分数从高到低排序 (descending)
            # x[0] 是 score
            items.sort(key=lambda x: x[0], reverse=True)
            
            # 转换符号格式并生成列表
            symbol_list = [convert_symbol(item[1]) for item in items]
            
            result[date] = symbol_list

        # 写入JSON文件
        # with open(json_file_path, 'w', encoding='utf-8') as f:
        #     # indent=4 让文件格式化更易读，ensure_ascii=False 支持中文（虽然本例主要是英文字符）
        #     json.dump(result, f, indent=4, ensure_ascii=False)
            
                # 替代方案：手动控制换行，实现每个日期一行
        with open(json_file_path, 'w', encoding='utf-8') as f:
            f.write('{\n')
            dates = list(result.keys())
            for i, date in enumerate(dates):
                # 将列表转换为字符串，去除多余空格
                list_str = json.dumps(result[date], ensure_ascii=False, separators=(',', ':'))
                line = f'"{date}":{list_str}'
                
                if i < len(dates) - 1:
                    f.write('\t' + line + ',\n') # 最后一项不加逗号，其他加逗号和换行
                else:
                    f.write('\t' + line)
            f.write('\n}')
            
        print(f"成功！已转换 {len(result)} 个日期的数据到 {json_file_path}")

    except FileNotFoundError:
        print(f"错误：找不到文件 {csv_file_path}")
    except Exception as e:
        print(f"发生未知错误：{e}")

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

