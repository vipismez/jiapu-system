# Project Guidelines

## Project Overview
- 这是一个基于 Tkinter 的桌面家谱应用，核心入口是 main.py。
- UI 与交互集中在 app.py 的 GenealogyApp 类。
- 数据模型位于 model.py，持久化读写在 storage.py。
- 运行数据保存在 data.json（程序会自动创建或更新）。

## Build and Run
- 运行应用：`python main.py`
- Python 版本：3.10+
- 测试：仓库当前没有自动化测试；如果新增功能，优先补充最小可复现脚本或手工验证步骤。

## Architecture
- main.py 只负责创建 Tk 根窗口、初始化 GenealogyApp，并在退出时触发保存。
- app.py 负责：画布渲染、节点交互、关系计算、对话框与搜索。
- storage.py 负责：加载/保存 JSON、首次启动样例数据生成、历史脏数据标准化。
- model.py 的 Person 是唯一核心实体；子女/兄弟姐妹通过 father/mother 动态推导，不单独持久化。

## Conventions
- 修改人物关系时，必须保持配偶关系双向一致（A.spouses 包含 B，B.spouses 也应包含 A）。
- 不要引入“子女列表”或“兄弟姐妹列表”持久化字段；沿用父母字段反推关系的模型。
- 任何会改变 members 的操作后都应调用 save_data，保持 UI 与 data.json 一致。
- 画布展示是“当前中心人物的局部关系视图”，不是全量家谱平铺；修改渲染逻辑时保持这一交互预期。

## Environment Notes
- assets/gender_icons.png 是可选资源：缺失时应回退到内置头像绘制，不应导致程序崩溃。
- Linux 环境通常需要额外安装 python3-tk；Windows 常见 Python 发行版通常已包含 Tkinter。

## References
- 详细功能和使用方式见 README.md。
