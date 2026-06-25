# LCA 项目方案与待完善清单自检规范 (Plan Self-Check)

本文件用于 `eval-executor` 对生成的 `execution_plan.md` 和 `todo_list.md` 文件内容进行质量与规范自检。

## 1. 结构与格式规范
- 是否成功在 `src/plan/` 目录下生成了 `execution_plan.md` 并在需要时生成了 `todo_list.md`？
- 两个文件是否严格遵守了 `template/execution_plan.md` 和 `template/todo_list.md` 中定义的 Markdown 结构框架？

## 2. 核心内容自检 (Execution Plan)
- **范围定义**：是否明确了研究对象、目的、系统边界、截断规则和功能单位 (FU)？
- **数据与环境**：是否明确了 openLCA 的连接情况、使用的数据库（如 ecoinvent）和所选的 LCIA 方法？是否体现了对现有数据的参考？
- **模型方案**：是否清晰地列出了将要建立的流 (Flow)、过程 (Process) 和产品系统 (Product System) 的架构？

## 3. 待完善清单自检 (Todo List)
- 计划文档中未明确的假设或缺失的关键参数是否已被正确提取并记录在 `todo_list.md` 中，而不是强行编造？

## 4. 交付标准
如果以上检查项存在遗漏或不符合规范，必须给出“需要改进”的结论，并附上详细修改建议，驱动 Agent Loop 要求修复。
如果因缺乏信息确实无法完善某一部分，但已在 Todo List 中详细记录供人类决策，可视为达标并交付。
