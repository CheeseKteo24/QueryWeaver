# 全栈 Demo 部署与负载测试

本文针对 v0.5 的部署单元：FastAPI 同时提供 JSON API 和 `web/` 静态前端。这是最小可演示全栈形态，不是最终的 Next.js + Worker + PostgreSQL + Qdrant 生产拓扑。

## 1. 部署拓扑

```text
Browser
   │ HTTPS（云平台终止 TLS）
   ▼
QueryWeaver Container :${PORT}
   ├── GET  /              静态前端
   ├── GET  /health        健康检查
   ├── GET  /docs          OpenAPI UI
   └── POST /v1/query      统一查询接口
          ├── documents    本地 Hybrid Retrieval
          └── sql          内存 SQLite 安全查询
```

当前单容器部署的优势是成本低、无跨域、容易复现；限制是文档和数据库都是 Demo 数据，不能持久化用户内容，也不能独立扩缩前后端。

## 2. 本地 Docker Compose 部署

先确保 Docker Desktop/Engine 正在运行。在仓库根目录执行：

```bash
docker compose up --build --detach
docker compose ps
```

验证：

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/
```

打开：

- Demo：<http://127.0.0.1:8000/>
- OpenAPI：<http://127.0.0.1:8000/docs>

查看日志与停止：

```bash
docker compose logs --follow queryweaver
docker compose down
```

Compose 配置包含只读根文件系统、非 root 用户、`no-new-privileges`、`/tmp` 临时文件系统和 `/health` 探针。它们不能替代应用安全，但能减少 Demo 容器的攻击面。

## 3. Dockerfile 做了什么

1. 基于官方 `python:3.12-slim`；
2. 复制项目并安装 `.[api]`；
3. 创建非 root 用户；
4. 使用 exec 替换启动 Uvicorn，保证容器停止信号能到达服务；
5. 从云平台 `PORT` 环境变量读取监听端口；
6. 使用 `/health` 判断容器是否可服务。

`scripts/container_entrypoint.py` 只负责验证端口并执行 Uvicorn，不包含业务逻辑。

## 4. 部署到公共 Docker 平台

任何支持从 GitHub 仓库构建 Dockerfile 的平台都可以部署当前 Demo。推荐操作顺序：

1. 在平台中新建 Web Service；
2. 连接 `CheeseKteo24/QueryWeaver`；
3. 选择仓库根目录的 `Dockerfile`；
4. 开放平台提供的 `PORT`；
5. Health Check Path 设置为 `/health`；
6. 先部署一个实例，最低从 512 MB 内存开始测量；
7. 部署完成后访问 `/`、`/docs` 和 `/health`；
8. 使用本文压测脚本对公网 URL 做小流量验证。

当前 Demo 无需 API Key。未来接入模型时，将 Key 配置在平台 Secret Store，不能写进 Dockerfile、Compose、代码或 GitHub Actions 日志。

### 发布后 Smoke Test

```bash
curl --fail https://YOUR_HOST/health

curl --fail \
  --header "Content-Type: application/json" \
  --data '{"question":"按地区统计销售额","top_k":3}' \
  https://YOUR_HOST/v1/query
```

检查返回的 `route`、`validated_sql`、`sql_result`，不能只检查 HTTP 200。

## 5. 运行负载测试

先启动本地或公网 Demo：

```bash
python scripts/run_load_test.py \
  --base-url http://127.0.0.1:8000 \
  --requests 500 \
  --concurrency 20 \
  --warmup 20 \
  --assert-p95-ms 1000 \
  --assert-max-error-rate 0 \
  --json-output outputs/load-tests/local-c20.json
```

Windows PowerShell 可以使用反引号换行，或写成一行。

输出字段包括：请求数、并发、成功/失败、错误率、吞吐、mean、p50、p95、max 和两条 route 的请求数量。脚本中的任何示例数字都不能写进简历；简历只能使用你在固定环境实际测出的结果。

## 6. 正确的压测步骤

不要上来只跑一次高并发。使用阶梯测试：

| 阶段 | 并发 | 请求数 | 目的 |
| --- | ---: | ---: | --- |
| 预热 | 1 | 20 | 排除首次导入和缓存影响 |
| 基线 | 1 | 100 | 单请求服务时间 |
| 轻载 | 5 | 300 | 检查基本并发正确性 |
| 中载 | 10 | 500 | 观察吞吐与 p95 |
| 压力 | 20/50 | 1000 | 找到错误率开始上升的位置 |

每次记录 Git SHA、CPU/内存、测试位置、请求数、并发、p50/p95/max、吞吐、错误率和 route 分布。

公网压测前先确认云平台限额，并从小流量开始。不要对不属于自己的服务运行压测。

## 7. 怎样分析结果

### 吞吐上升且 p95 稳定

说明当前并发还在系统可承受范围内。

### 吞吐不再增长、p95 快速升高

说明某个资源已经饱和。当前 Demo 最可能是 Python CPU 计算、SQLite SQL 路径串行锁、线程池排队或部署平台 CPU 配额。

### SQL p95 比文档路径高

当前 Demo 共享一个 SQLite Connection。为了避免 progress handler 和 connection 状态互相干扰，SQL 执行被锁保护，因此并发 SQL 会排队。这是安全正确性优先的 Demo 取舍。生产环境应改成只读 PostgreSQL 连接池，每个请求独立连接。

### 接入真实模型后延迟显著增加

需要把延迟拆成 route、embedding、lexical search、vector search、RRF、reranker、LLM generation 和 SQL validation/execution。只看端到端 p95 无法定位瓶颈，后续 M4 要使用 OpenTelemetry spans。

## 8. CI 中的容器验证

GitHub Actions 除了 Python 测试，还会构建镜像、启动真实容器、等待 `/health`、请求浏览器首页、发送 SQL 查询并检查 route，最后删除容器。

CI 只执行 Smoke Test，不执行压力测试。共享 Runner 性能波动较大，不适合产生可写入简历的延迟数字。

## 9. 从 Demo 部署到实用系统

```text
静态页面         → Next.js + 登录 + Workspace
内存文档         → 上传 Worker + Object Storage
Hashing向量       → 真实 Embedding + Qdrant
规则Reranker      → CrossEncoder
规则SQL生成       → 真实 LLM + repair
内存SQLite        → PostgreSQL只读连接池
单实例           → 外部状态 + 多副本
简单health        → readiness + metrics + traces
```

因此，应把当前版本描述为“可复现的安全 AI 数据查询纵向切片”，而不是生产就绪 SaaS。
