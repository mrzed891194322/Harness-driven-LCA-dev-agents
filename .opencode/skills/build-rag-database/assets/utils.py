import os
import json
from pathlib import Path
from dotenv import load_dotenv
from markitdown import MarkItDown
import chromadb
import chromadb.utils.embedding_functions as embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter

def load_embedding_config():
    """
    加载并验证从环境变量配置的嵌入（embedding）相关 API 参数。
    
    返回:
        tuple: (api_key, api_url, model_name) 分别对应 API 密钥、自定义接口地址和模型名称。
    """
    load_dotenv()
    api_key = os.getenv("EMBEDDING_API_KEY")
    api_url = os.getenv("EMBEDDING_API_URL")
    model_name = os.getenv("EMBEDDING_MODEL")
    
    # 验证 API 密钥是否已配置且非占位符
    if not api_key or api_key == "sk-your-api-key-here":
        raise ValueError("Please set a valid EMBEDDING_API_KEY in .env")
        
    return api_key, api_url, model_name

def init_chroma_collection(output_dir: Path, api_key: str, api_url: str, model_name: str) -> chromadb.Collection:
    """
    初始化 Chroma 客户端并创建/重建向量数据库集合。
    
    参数:
        output_dir (Path): 数据库持久化存储的目录。
        api_key (str): OpenAI/Embedding API 的密钥。
        api_url (str): 可选，自定义的 API 基础地址（api_base）。
        model_name (str): 嵌入模型名称。
        
    返回:
        chromadb.Collection: 创建成功的 ChromaDB 集合对象。
    """
    # 确保输出目录及其父级目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Initializing ChromaDB at {output_dir}...")
    client = chromadb.PersistentClient(path=str(output_dir))
    
    # 配置 OpenAI 嵌入函数需要的参数
    kwargs = {"api_key": api_key, "model_name": model_name}
    if api_url:
        kwargs["api_base"] = api_url
        
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(**kwargs)
    
    # 为了保证数据完全重建，先尝试删除已有的同名 collection
    try:
        client.delete_collection(name="rag_collection")
        print("Existing collection deleted for a clean rebuild.")
    except Exception:
        pass
        
    # 创建新的 collection
    collection = client.create_collection(
        name="rag_collection", 
        embedding_function=openai_ef
    )
    return collection

def get_supported_extensions(config_path: Path) -> list:
    """
    通过指定路径的 JSON 配置文件加载并解析支持的文档文件后缀名数组。
    
    参数:
        config_path (Path): json 配置文件的路径。
        
    返回:
        list: 解析得到的后缀名列表（如 ['.pdf', '.docx', '.doc']）。
    """
    default_extensions = [".pdf", ".docx", ".doc"]
    
    if not config_path.exists():
        return default_extensions
        
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        types = data.get("supported_file_types", [])
        
        # 直接读取并确保都是小写的后缀名
        extensions = [t.lower().strip() for t in types if isinstance(t, str) and t.strip()]
        return extensions if extensions else default_extensions
    except Exception as e:
        print(f"Warning: Failed to load config from {config_path}: {e}. Using default types.")
        return default_extensions

def is_supported_file(file_path: Path, supported_extensions: list = None) -> bool:
    """
    检查文件是否在支持的文件后缀数组中。
    
    参数:
        file_path (Path): 待检查的文件路径。
        supported_extensions (list): 可选，支持的后缀列表。如果为 None，则从本地 config.json 读取。
        
    返回:
        bool: 如果符合且非隐藏文件，则返回 True，否则返回 False。
    """
    # 忽略以 . 开头的隐藏文件
    if file_path.name.startswith('.'):
        return False
    suffix = file_path.suffix.lower()
    if supported_extensions is None:
        config_path = Path(__file__).parent / "config.json"
        supported_extensions = get_supported_extensions(config_path)
    return suffix in supported_extensions

def process_file(file_path: Path, md: MarkItDown, collection: chromadb.Collection, text_splitter: RecursiveCharacterTextSplitter):
    """
    转换单个文件内容，切分文本块，并将其添加至 Chroma 向量集合中。
    
    参数:
        file_path (Path): 文件路径。
        md (MarkItDown): MarkItDown 转换实例。
        collection (chromadb.Collection): ChromaDB 向量集合对象。
        text_splitter (RecursiveCharacterTextSplitter): 文本分割器实例。
    """
    print(f"Processing {file_path}...")
    try:
        # 如果是 .md 或 .txt 文件，直接读取内容，避免使用 markitdown 重复转换；其他格式则使用 markitdown 转换
        if file_path.suffix.lower() in (".md", ".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                text_content = f.read()
        else:
            result = md.convert(str(file_path))
            text_content = result.text_content
        
        # 将文本切分为较小的 chunk 以便于向量检索
        chunks = text_splitter.split_text(text_content)
        
        documents = []
        metadatas = []
        ids = []
        
        for i, chunk in enumerate(chunks):
            chunk_stripped = chunk.strip()
            if not chunk_stripped:
                continue
            documents.append(chunk_stripped)
            # 记录数据源信息作为元数据
            metadatas.append({"source": str(file_path)})
            # 为每个文本块生成唯一 ID
            ids.append(f"{file_path.name}_chunk_{i}")
            
        # 如果切分出了有效的文本块，将其批量写入向量数据库中
        if documents:
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Added {len(documents)} chunks from {file_path}")
            
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

