# 交付清单

ChainScope · 产业链、跨市场与公司研究；2026-10-09。

## 产品与源码

- 网站地址：<https://chainscope-solid-state-research.keen-grebe-4495.chatgpt.site>。当前权限按用户授权设为公开，以交付回执的成功部署状态为准。
- 本机完整产品：<http://127.0.0.1:8000>；接口文档：<http://127.0.0.1:8000/docs>。
- 公开源码仓库：[Tbwt-236/chainscope-industry-research](https://github.com/Tbwt-236/chainscope-industry-research)。招聘方可匿名审阅，GitHub SHA 见交付回执。
- Sites 内部源码仓库需要平台授权；公开 GitHub 与网页 ZIP 为招聘方入口。
- 本地项目包含 Git 历史。另附源码 ZIP 与 Git bundle，支持不依赖平台凭据的审阅。网页也提供源码包下载。

## 文件

| 文件 | 用途 |
|---|---|
| `spec_task1_industry_chain.md` | 可交给 Cursor / Claude Code 的 SDD 合同 |
| `README.md` | 启动方法、目标用户、AI 角色、数据与边界 |
| `backend/`、`dist/` | FastAPI/LangGraph 后端与独立前端 |
| `data/research.json` | 历史证据样本 |
| `data/update-sample.json` | 2026 年发布的真实 QS 年报样本，需人工复核 |
| `tests/` | 自动验收 |
| `docs/TEST_REPORT.md` | 实际测试结果与未验证项 |
| `docs/AI_USAGE_AND_VALIDATION.md` | AI 使用与来源验证记录 |
| `docs/ChainScope_Task1_live_demo.mp4` | 约 73 秒连续浏览器采样实际操作，推荐提交 |
| `docs/live_demo_capture.json`、`docs/live_demo_zh.srt` | 真实捕获时序与中文字幕 |
| `docs/ChainScope_Task1_demo.mp4` | 旧 90 秒截帧剪辑，补充材料 |
| `docs/live_model_validation.json` | 在线模型配置缺失的真实验证记录 |
| `docs/PORTFOLIO_ASSESSMENT.md` | 优化后自评与后续优先级 |
| `docs/DEMO_SCRIPT.md`、`docs/demo_zh.srt` | 演示脚本与字幕 |

主视频为连续浏览器屏幕采样，保留实际时序，无旁白；不是操作系统级高帧率录屏。旧视频为截帧剪辑。整包小于题目 30 MB 限制，不含令牌、环境秘密或运行数据库。

## 提交时准确描述

托管网页是独立规则演示；完整 Python 后端已在本机运行并验证。未接通扶摇/iFinD，未实测在线模型。材料为历史快照；PostgreSQL 配置已提供，未启动容器验证。不能将这些状态改写为“实时云端多智能体金融终端”。
