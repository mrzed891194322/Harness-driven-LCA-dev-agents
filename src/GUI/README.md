# LCA Agent 控制面板 UI 脚本 (src/GUI)

本目录下的 Python 脚本用于构建并运行本 LCA 项目的 Gradio 网页控制台界面。

## 目录结构

- `main.py`：GUI 唯一启动入口，启动 Gradio 服务。
- `ui/`：界面展示与事件绑定层。
  - `ui_main.py`：组装 Gradio 主界面布局并传递组件。
  - `components/`：存放具体的 UI 组件文件（如左侧边栏、终端控制台、计划表单）。
  - `events.py`：**核心事件绑定逻辑**，负责绑定所有界面按钮和上传组件的触发函数。
  - `assets/`：存放自定义样式（CSS）及计划输入模板等静态资源。
- `functions/`：底层业务逻辑层。
  - `utils/`：**公共/调用工具函数**（例如 `process_manager.py` 和 `log_exporter.py`）。
  - `[feature_name]/`：实现特定功能的子目录（例如 `project_init/`, `executor/`, `plan_loader/`）。
    - ⚠️ **规范**：该子目录下只有 `main.py` 作为外部接口；所有该特征内部特有的、不对外暴露的辅助脚本需放入子目录 `private_utils/` 中。
- `log/`：运行原始日志输出目录。

---

## 开发指南 (新增控件与绑定功能规范)

若需要为控制面板添加新的功能或控件，请遵循以下规范：

### 1. 如果要增加控件 (Adding UI Controls)
1. 在 `src/GUI/ui/components/` 下新建或修改组件文件（如添加按钮、输入框等）。
2. 在 `src/GUI/ui/ui_main.py` 中实例化并编排该组件的页面布局。
3. 将组件变量通过 `bind_ui_events()` 的参数传递到事件绑定中。

### 2. 如果要实现底层功能 (Implementing Logic)
- **非共享逻辑**：在 `src/GUI/functions/` 下为该功能建立子目录（例如 `functions/my_new_feature/`），在子目录中建立 `main.py` 作为唯一的外部接口。将其余的私有支撑函数放在 `functions/my_new_feature/private_utils/` 目录下。
- **公共共享逻辑**：如果是被多个独立特征（feature）共同调用的公共辅助逻辑或工具函数，直接放在 `src/GUI/functions/utils/` 下。

### 3. 如果要绑定控件功能 (Binding Logic to Controls)
1. 打开 `src/GUI/ui/events.py`。
2. 引入你刚才在 `src/GUI/functions/` 中编写的业务接口函数（`main.py` 或 `utils/...`）。
3. 在 `bind_ui_events` 函数中绑定你传递进来的 Gradio 控件事件（如 `.click()`, `.change()`, `.upload()` 等）。

---

## 运行方式

在项目根目录下运行：
```bash
uv run python src/GUI/main.py
```
启动后访问 [http://127.0.0.1:7860](http://127.0.0.1:7860) 查看控制台界面。
