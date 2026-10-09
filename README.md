# ChainScope · 产业研究工作台

围绕固态电池，将“属于哪个产业环节”拆成可核验的公司业务关系：从财报收入、研发产线，到未来表态和无证据。支持中外公司对照、外部情景传导、人工审核更新与快照。

[公开产品](https://chainscope-solid-state-research.keen-grebe-4495.chatgpt.site/) · [公开 GitHub 源码](https://github.com/Tbwt-236/chainscope-industry-research) · [约 73 秒实际操作演示](https://chainscope-solid-state-research.keen-grebe-4495.chatgpt.site/ChainScope_Task1_live_demo.mp4) · [源码与验证材料 ZIP](https://chainscope-solid-state-research.keen-grebe-4495.chatgpt.site/ChainScope_Task1_source.zip)。网页运行浏览器规则引擎，完整 Python 后端按下方步骤本机运行。

## 运行

Python 3.12；在项目根目录执行：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

打开 <http://127.0.0.1:8000>。接口文档为 <http://127.0.0.1:8000/docs>。首次启动自动创建 SQLite 数据库，无需模型密钥。也可使用 `uv venv` 与 `uv pip install -r requirements.lock`。

PostgreSQL 运行：`docker compose up --build`；仍访问本机 8000。容器配置已提供，当前环境未实测容器。生产部署须另行设置数据库密码、访问控制、HTTPS 与服务资源限制。

只运行独立演示：`python3 -m http.server 8080 --directory dist`，访问本机 8080。此模式为浏览器规则引擎，材料/审核/快照仅保存于当前浏览器，不运行 Python 或云端 LLM。不要双击 `index.html`，需要 HTTP 服务。

托管 URL 和代码仓库信息见 `docs/DELIVERY.md`。托管网页采用上述独立模式；不能把它描述为已上线的 FastAPI 服务。

## 产品与使用

目标用户为券商行研人员和机构研究员；核心设计是先定技术口径，再验证公司业务关系。数据样本包含六家公司、七条关系，分类为锂源与前驱体、固态电解质、电芯开发、工艺许可与产线工程、整车集成。

1. 在产业图谱点击环节或选择市场/技术路径，打开每条关系的证据。
2. 查看可比与不可比因素。赣锋的半固态路线不能等同 QS 的固态锂金属平台。
3. 切换三种外部假设，追踪业务变化、财务指标、成立条件与反向机制。
4. 在证据页填写表单或导入 JSON，打开原文人工复核，再生成新快照并查看新增/移除来源及财务字段差异。
5. 点击“载入更新样本”：QS 2025 年报于 2026-02-25 发布。导入并复核后，将证据截止改为 2026-02-25 或更晚再核验；来源从 7 增至 8，QS 保持 B。试验产线进展不能证明电芯销售收入或全固态商业化。

默认截止 2025-03-01，展示已核对的**历史材料**；2026-10-09 为来源核对日，不代表数据最新。把截止改为 2023-01-01 可验证缺证据场景。

更新样本仅补充 QS 一条业务关系，不代表全产业已更新至 2026 年。证券标识沿用 2025 基线，不代表当前上市信息。

最重要的收入样本来自 Solid Power 2024 年报：技术服务关系披露约 1,180 万美元收入，而非量产电芯销量。其电解质研发关系仍是 B。收入占比不计算。题目中的扶摇/iFinD 没有可用连接，因此没有伪造这两个平台的数据；使用题目允许的官方公开材料。

## AI 角色

后端是真实 LangGraph StateGraph：IntentParser → IndustryStructurer → CompanyLocatorEvidenceGrader → CrossMarketComparator → TransmissionTracer → ReportGate。

默认节点采用确定性规则，跨市场与传导文本由已核对材料及人工维护的分析模板提供；未宣称在线多智能体自主研究。设置 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 可连接兼容模型，只允许模型选择已有证据 ID。自由生成数字/事实被丢弃，异常返回规则报告及 warning。实际在线模型连接尚未验证。

开发过程中使用 AI 编写规范、代码和测试，核对真实来源并执行验证。记录见 `docs/AI_USAGE_AND_VALIDATION.md`。

真实模型验证：`python scripts/validate_live_model.py --output docs/live_model_validation.json`。该命令读取本地 `.env` 中上述三个 LLM 变量，不记录密钥；常规后端启动需自行设置环境变量。当前结果为 `not_configured`、`real_model_verified=false`，未发送真实请求。HTTP mock 验证 ID 白名单与自由事实阻断，不能替代在线联调。

## 更新与数据接入

本机写接口默认禁用。启动前设置随机 `ADMIN_TOKEN`，网页导入时输入令牌（页面内暂存，刷新即丢弃）。不要将令牌提交到仓库。导入材料先待审，不能自报 verified；管理员对照原文后确认复核。新增材料仍须满足当前证据截止日期才参与评级。

`DATA_PROVIDER=bridge` 与 `DATA_BRIDGE_URL` 支持管理员配置的 HTTPS 标准化数据桥接，schema 以 `data/research.json` 为准。它不是假设的 iFinD SDK；接入真实 MCP 前需根据实际工具合同开发桥接。桥接超时返回 503，不静默冒充实时成功。

`DATABASE_URL` 可切换 SQLite / PostgreSQL。SQL 保存终态快照和导入证据，未实现跨进程断点恢复。静态版 localStorage 只在本浏览器内有效，最多保存 20 个快照；后台 API 可查询最近 50 条。

## 验证

```bash
python -m pytest tests -q
node tests/test_browser_engine.mjs
```

验证结果、浏览器实测与限制见 `docs/TEST_REPORT.md`。演示视频及脚本见交付清单。代码锁文件记录本次实际安装依赖；没有把 PostgreSQL、真实 MCP、线上模型或生产压测标为已通过。

本轮实际结果：**58 项 Python 测试、34 条 JavaScript 引擎断言通过**。新增连续浏览器屏幕采样演示约 73 秒，保持实际操作时序；旧 90 秒界面帧剪辑保留为补充。自评见 `docs/PORTFOLIO_ASSESSMENT.md`。

## 边界

这是有明确数据和 AI 边界的可操作 MVP。无自动实时抓取、全行业覆盖、语义自动审阅或多人云端证据库。没有买卖建议、目标价或交易功能。传导计算为假设敏感度，不能解读为公司盈利预测。

详细合同见 `spec_task1_industry_chain.md`；架构唯一源文件为 `docs/architecture.mmd`。
