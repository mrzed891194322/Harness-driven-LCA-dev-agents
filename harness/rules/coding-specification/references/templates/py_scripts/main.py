from utils.data_helper import process_data
from utils.config_helper import load_config

def main():
    """
    工作脚本的唯一入口，作为总接口。
    """
    # 加载配置
    config = load_config()
    
    # 从配置中读取输入输出路径
    input_path = config.get("input_path", "workspace/inputs/references/data/example.csv")
    output_path = config.get("output_path", "workspace/tmp/processed_example.csv")
    
    process_data(input_path, output_path)

if __name__ == "__main__":
    main()
