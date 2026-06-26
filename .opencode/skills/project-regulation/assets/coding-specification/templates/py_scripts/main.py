from utils.data_helper import process_data

def main():
    """
    工作脚本的唯一入口，作为总接口。
    """
    # 示例执行逻辑
    input_path = "input/data/example.csv"
    output_path = "src/data/processed_example.csv"
    process_data(input_path, output_path)

if __name__ == "__main__":
    main()
