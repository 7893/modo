# 已知问题登记册 (Known Issues Register)

更新日期：2026-09-23
状态：现行
适用范围：MODO 全系统（data-bridge、edge-app、deploy、CI/CD）已知问题与技术债追踪

---

## 治理规则

1. **登记原则**：本文档为 MODO 项目已知缺陷与技术债务的唯一全景索引看板。所有经只读核验确证的问题统一登记于此，每个条目的技术细节、真实代码证据与治理方案详见 `docs/issues/` 对应的专门文档。
2. **状态机规范**：条目状态严格遵循四态流转：
   - `DRAFT`：草案（正在采信与排查，证据待补全）
   - `OPEN`：待处理（已完成证据核验，缺陷成立，等待分配治理）
   - `IN-PROGRESS`：处理中（已建立修复分支，正在进行代码改造或测试验证）
   - `DONE`：已关闭（修复已合入并通过自动化门禁，或经评审终止追踪，保留作为历史追溯）
3. **原子更新要求**：任何代码修复提交必须在**同一次 Git Commit** 中将对应 `docs/issues/KI-xxx.md` 的完成定义勾选并将状态更新为 `DONE`，同时同步更新本看板表格，杜绝“代码已修但 Issue 悬空”的状态漂移。
4. **安全红线**：问题登记与证据切片严禁包含未脱敏的公网密码、API Token、私钥或内部敏感资产标识。

---

## 活跃问题（DRAFT / OPEN / IN-PROGRESS）

| 编号 | 标题 | 状态 | 优先级 | 影响模块 | 详情链接 |
|---|---|:---:|:---:|---|---|
| - | 暂无活跃问题 | - | - | - | - |

---

## 已关闭问题（DONE）

| 编号 | 标题 | 状态 | 优先级 | 影响模块 | 关闭日期 | 详情链接 |
|---|---|:---:|:---:|---|:---:|---|
| **KI-001** | 敏感资产泄露与生产节点IP暴露 | DONE | **P0** | `data-bridge/config`, Git History | 2026-09-23 | [详情](issues/KI-001-敏感资产泄露与生产节点IP暴露.md) |
| **KI-002** | 数据库初始化 DDL 缺失与核心视图断档 | DONE | **P1** | `data-bridge/src` | 2026-09-23 | [详情](issues/KI-002-数据库初始化DDL缺失与核心视图断档.md) |
| **KI-003** | 遥测清理接口依赖未定义的归档表 | DONE | **P1** | `data-bridge/src/api.py` | 2026-09-23 | [详情](issues/KI-003-遥测清理接口依赖未定义的归档表.md) |
| **KI-004** | 采集服务顶层加载配置导致模块导入阻断 | DONE | **P1** | `data-bridge/src/ingest.py` | 2026-09-23 | [详情](issues/KI-004-采集服务顶层加载配置导致模块导入阻断.md) |
| **KI-005** | 私有 API 鉴权边界确认 | DONE | **P2** | `data-bridge/src/api.py`, `edge-app/src/index.ts` | 2026-09-23 | [详情](issues/KI-005-全局鉴权中间件误伤只读业务接口.md) |
| **KI-006** | 内存限流器缺少键清理导致内存泄漏隐患 | DONE | **P2** | `data-bridge/src/api.py` | 2026-09-23 | [详情](issues/KI-006-内存限流器缺少键清理导致内存泄漏隐患.md) |
| **KI-007** | 前端单屏高频轮询引发 429 限流 | DONE | **P1** | `edge-app`, `data-bridge/src/api.py` | 2026-09-23 | [详情](issues/KI-007-前端单屏高频并发轮询引发429限流.md) |
| **KI-008** | 自动重训调度强依赖 Linux 私有环境与固定路径 | DONE | **P1** | `data-bridge/src/api.py` | 2026-09-23 | [详情](issues/KI-008-自动重训调度强依赖Linux私有环境与固定路径.md) |
| **KI-009** | 模型自动重训备份表无限累积 | DONE | **P2** | `data-bridge/src/train_latency_model.py` | 2026-09-23 | [详情](issues/KI-009-模型自动重训备份表无限累积.md) |
| **KI-010** | 采集端冷启动 CPU 计算为零 | DONE | **P2** | `data-bridge/src/ingest.py` | 2026-09-23 | [详情](issues/KI-010-采集端冷启动CPU计算为零.md) |
| **KI-011** | 前端 Tailwind CDN 与 resize 性能问题 | DONE | **P2** | `edge-app/src` | 2026-09-23 | [详情](issues/KI-011-前端Tailwind-CDN生产告警与单文件维护性问题.md) |
| **KI-012** | 单元测试硬编码生产环境特定参数与域名 | DONE | **P2** | `data-bridge/tests/test_api.py` | 2026-09-23 | [详情](issues/KI-012-单元测试硬编码生产环境特定参数与域名.md) |
