import sys
import json
import csv
from pathlib import Path

def extract_results(result):
    formatted_results = []
    try:
        impacts = result.get_total_impacts()
        for impact in impacts:
            cat = impact.impact_category
            formatted_results.append({
                "category_name": cat.name if cat else "Unknown",
                "category_id": cat.id if cat else "Unknown",
                "amount": impact.amount if impact.amount is not None else 0.0,
                "unit": cat.ref_unit if cat and cat.ref_unit else ""
            })
    except Exception as e:
        print(f"[错误] 获取影响评估结果失败: {e}")
        try:
            result.dispose()
        except Exception:
            pass
        sys.exit(1)

    # 释放句柄
    try:
        result.dispose()
    except Exception:
        pass
        
    return formatted_results

def print_results_table(formatted_results):
    if not formatted_results:
        print("\n[提示] 未获取到任何影响评估结果（可能未指定 LCIA 方法或该方法无有效因子）。")
        return

    # 控制台打印 Markdown 表格
    print("\n### 计算结果总览 (LCIA Results)")
    print("| 影响类别 (Impact Category) | 数值 (Amount) | 单位 (Unit) | 影响分类 UUID (UUID) |")
    print("| --- | --- | --- | --- |")
    for r in formatted_results:
        print(f"| {r['category_name']} | {r['amount']:.6e} | {r['unit']} | {r['category_id']} |")
    print()

def export_results(formatted_results, output_path_str):
    if not formatted_results or not output_path_str:
        return
    output_path = Path(output_path_str)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ext = output_path.suffix.lower()
    if ext == ".json":
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(formatted_results, f, ensure_ascii=False, indent=2)
            print(f"[成功] 结果已成功导出至 JSON 文件: {output_path.absolute()}")
        except Exception as e:
            print(f"[错误] 写入 JSON 文件失败: {e}")
    elif ext == ".csv":
        try:
            with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Impact Category", "Amount", "Unit", "UUID"])
                for r in formatted_results:
                    writer.writerow([r["category_name"], r["amount"], r["unit"], r["category_id"]])
            print(f"[成功] 结果已成功导出至 CSV 文件: {output_path.absolute()}")
        except Exception as e:
            print(f"[错误] 写入 CSV 文件失败: {e}")
    else:
        print(f"[警告] 不支持的导出格式 '{ext}'，仅支持 .json 或 .csv 后缀。跳过文件导出。")
