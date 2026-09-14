# 本地完整闭环与测试验证指南

这份指南帮助你亲自验证：浏览器请求确实经过 Router、检索或 SQL 安全链路，而不是前端展示固定结果。

## 1. 当前闭环包含什么

```text
web/index.html + app.js
          ↓ POST /v1/query
FastAPI（queryweaver.api）
          ↓
QueryWeaverApplication.ask()
          ↓
   route_question()
      ├── documents → HybridRetriever → Reranker → Evidence
      └── sql → SqlGenerator → SQL Policy → SQLite → Result Table
          ↓
QueryResponse → JSON → 浏览器渲染
```

当前 Demo 使用内存数据和确定性模型替身，目标是让任何人无需 API Key 就能复现完整调用链。它不代表生产模型效果。

## 2. 安装与启动

要求 Python 3.11+。在仓库根目录执行：

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[api,dev]"
python -m uvicorn queryweaver.api:app --reload
```

macOS/Linux：

```bash
source .venv/bin/activate
python -m pip install -e ".[api,dev]"
python -m uvicorn queryweaver.api:app --reload
```

打开：

- 应用页面：<http://127.0.0.1:8000/>
- OpenAPI 调试页面：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/health>

## 3. 前端怎样连接后端

`web/app.js` 在用户点击“运行查询”后发送：

```http
POST /v1/query
Content-Type: application/json

{
  "question": "数字订阅可以在多少天内退款？",
  "top_k": 3
}
```

由于静态页面和 API 都由同一个 FastAPI 进程提供，本地请求使用相对地址 `/v1/query`，无需配置 API Host，也不会遇到跨域问题。未来迁移到独立 Next.js 服务后，再使用环境变量配置 API Base URL。

前端不做业务判断：它不决定 route、不生成 SQL、不计算 score。它只根据后端 JSON 渲染：

- `route=documents`：显示 Answer 和 Evidence Cards；
- `route=sql`：显示 Validated SQL 和 Result Table；
- 非 2xx：显示经过后端整理的错误。

前端渲染用户或模型内容时使用 `textContent`，不使用 `innerHTML`，避免把不可信内容当 HTML 执行。

## 4. 后端怎样完成编排

`queryweaver.api` 只处理 HTTP 契约：参数校验、状态码、响应序列化。核心逻辑位于 `QueryWeaverApplication.ask()`：

1. 校验 question 和 top_k；
2. Router 选择 `documents` 或 `sql`；
3. 文档路径调用统一 `Retriever`；
4. SQL 路径调用 `TextToSqlService`；
5. Synthesizer 只基于可信证据生成答案；
6. 形成统一 `QueryResponse`，记录 route、evidence/SQL 和 latency。

这种分层保证以后增加 CLI、任务 Worker 或 Next.js 时，不会复制业务逻辑。

## 5. 手工验证四个关键场景

### 场景 A：文档检索

问题：

```text
数字订阅可以在多少天内退款？
```

预期：

- route 是 `documents`；
- Evidence 第一项来自 `refund-policy`；
- Answer 中包含真实 Chunk ID；
- SQL 面板不显示。

### 场景 B：SQL 查询

问题：

```text
按地区统计销售额
```

预期：

- route 是 `sql`；
- 页面展示经过规范化的 SELECT；
- 华东销售额为 20000；
- Evidence 面板不显示。

### 场景 C：输入校验

在 OpenAPI 页面发送空字符串，预期 HTTP 422。说明无效请求在 API 边界被拒绝，还没有进入模型或数据库。

### 场景 D：SQL 攻击回归

当前 HTTP API 不接受用户直接提交 SQL。运行独立安全数据集：

```bash
python scripts/run_sql_policy_benchmark.py
```

预期 17/17。然后自己在 `benchmarks/sql_policy_cases.json` 添加一条攻击样本，确认它被拒绝。

## 6. 不打开浏览器也可以验证 API

PowerShell：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/v1/query `
  -ContentType 'application/json' `
  -Body '{"question":"按地区统计销售额","top_k":3}'
```

通用 curl：

```bash
curl -X POST http://127.0.0.1:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question":"按地区统计销售额","top_k":3}'
```

## 7. 自动化测试分层

### 单元测试

分别验证 tokenizer、BM25、RRF、Reranker、Schema 和 SQL Policy：

```bash
python -m unittest discover -s tests -v
```

### Application 集成测试

`tests/test_application.py` 不经过 HTTP，验证统一应用服务的两条业务路径。

```bash
python -m unittest tests.test_application -v
```

### API 契约测试

`tests/test_api.py` 使用 FastAPI TestClient，验证真实 HTTP 状态码和 JSON 结构，但不占用端口。

```bash
python -m unittest tests.test_api -v
```

### 离线质量与安全 Benchmark

```bash
python scripts/run_retrieval_benchmark.py --assert-minimum 0.75
python scripts/run_sql_policy_benchmark.py
```

### 静态检查

```bash
ruff check src tests scripts
mypy src
```

以上检查也会在 GitHub Actions 中运行。你本地成功、CI 失败时，应先比较 Python 版本、安装 extras、文件大小写和未提交文件。

## 8. 怎样确认请求真的经过完整链路

可以使用“逐层断言”，而不是只观察页面有答案：

| 层 | 验证证据 |
| --- | --- |
| Browser | DevTools Network 中存在 `/v1/query` POST |
| API | HTTP 200/422，响应符合 OpenAPI Schema |
| Router | JSON 中 `route` 符合预期 |
| Retrieval | `evidence` 包含 Chunk ID、document ID、score |
| SQL Generator | `generated_sql` 被保留用于审计 |
| SQL Validator | `validated_sql` 是规范化且允许执行的 SQL |
| Executor | `sql_result` 包含 columns、rows、elapsed、truncated |
| End-to-end | 前端展示的数据与 JSON 完全一致 |

只有每层都有可检查证据，才算完成闭环。

## 9. 你应该亲自完成的练习

1. 在 `demo.py` 增加一张 `orders` 表和一个新的聚合问题。
2. 先写失败测试，再让 `DemoSqlGenerator` 支持该问题。
3. 增加一篇容易与退款制度混淆的文档，观察排名变化。
4. 暂时删除 Validator 调用，观察测试为什么还不够，然后恢复并增加防绕过测试。
5. 在浏览器 DevTools 中完整解释一次请求和响应。

完成这些练习后，你会真正理解前端、API、应用编排、模型边界、检索和安全执行之间的关系。

## 10. 从 Demo 到生产还缺什么

- 用真实 Embedding/CrossEncoder 替换 Hashing/TokenOverlap；
- 用真实 LLM Adapter 替换 `DemoSqlGenerator` 和 `DeterministicSynthesizer`；
- SQLite 内存数据替换为只读 PostgreSQL 角色；
- 静态页面迁移为 Next.js，并支持流式响应；
- 增加认证、Workspace 隔离、上传 Worker 和 OpenTelemetry。

替换这些 Adapter 时，`QueryWeaverApplication`、HTTP 契约和测试结构应保持稳定，这就是当前架构分层的价值。
