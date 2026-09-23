# KI-002 · 数据库初始化DDL缺失与核心视图断档

- 状态：DONE
- 优先级：P1
- 更新日期：2026-09-23
- 适用范围：`data-bridge/src/db_setup.py`, `data-bridge/src/api.py`, `data-bridge/src/train_latency_model.py`
- 关联：[已知问题看板](../KNOWN-ISSUES.md)

---

## 结论

在 `modo` 项目中，核心数据库脚本 [`db_setup.py`](../../data-bridge/src/db_setup.py) 仅创建了基础表 `vm_telemetry` 与 2 个基础视图。而后端服务 [`api.py`](../../data-bridge/src/api.py) 和模型训练脚本 [`train_latency_model.py`](../../data-bridge/src/train_latency_model.py) 依赖的 7 个核心视图和表在代码仓库中完全没有 SQL/DDL 定义。任何新部署环境运行初始化后，核心接口均会抛出 `Table doesn't exist` 导致 500 崩溃。

---

## 只读证据（2026-09-23）

### 1. `db_setup.py` 中仅有 3 个数据库对象定义
查看 [`data-bridge/src/db_setup.py`](../../data-bridge/src/db_setup.py#L62-L130)：
- 第 62 行：`CREATE TABLE IF NOT EXISTS vm_telemetry`
- 第 86 行：`CREATE OR REPLACE VIEW v_telemetry_ml_features`
- 第 108 行：`CREATE OR REPLACE VIEW v_telemetry_hourly_forecasting`

### 2. 核心业务代码依赖的大量视图/表查无定义
在代码中通过 `grep` 检索，以下被频繁查询的数据库对象在项目中没有任何建表或创建视图语句：
1. **`v_node_latest_status`**：
   在 [`data-bridge/src/api.py#L230`](../../data-bridge/src/api.py#L230)、[`#L547`](../../data-bridge/src/api.py#L547)、[`#L738`](../../data-bridge/src/api.py#L738)、[`#L839`](../../data-bridge/src/api.py#L839) 中被用作获取节点最新状态、健康分及特征的基础视图。
2. **`v_realtime_analytics`**：
   在 [`data-bridge/src/api.py#L337`](../../data-bridge/src/api.py#L337) 的 `/api/analytics/hourly` 接口中被直接查询。
3. **`v_fleet_health_report`**：
   在 [`data-bridge/src/api.py#L375`](../../data-bridge/src/api.py#L375) 的 `/api/analytics/fleet` 接口中被直接查询。
4. **`v_anomaly_dashboard`**：
   在 [`data-bridge/src/api.py#L408`](../../data-bridge/src/api.py#L408) 的 `/api/analytics/anomalies` 接口中被直接查询。
5. **`anomaly_detection`**：
   在 [`data-bridge/src/api.py#L565`](../../data-bridge/src/api.py#L565) 的 `/api/ai/diagnostics` 接口中被查询。
6. **`latency_forecast_train`**：
   在 [`data-bridge/src/train_latency_model.py#L69`](../../data-bridge/src/train_latency_model.py#L69)、[`#L141`](../../data-bridge/src/train_latency_model.py#L141)、[`#L182`](../../data-bridge/src/train_latency_model.py#L182) 以及 [`api.py#L713`](../../data-bridge/src/api.py#L713) 中被作为训练集表查询和清洗。
7. **`vm_telemetry_hourly`**：
   在 [`db_setup.py#L126`](../../data-bridge/src/db_setup.py#L126) 的视图定义中直接被 `FROM vm_telemetry_hourly` 引用，但此底层聚合表本身未被创建。

---

## 影响分析

1. **不可复现性**：第三方开发者无法根据仓库文档拉起完整的服务环境，严重破坏了开源软件的基本可用性标准。
2. **运行时崩溃**：任何未经过作者手工在云上预建数据库对象的全新实例，前端拉取数据时所有核心卡片全部呈现网络错误或 500 状态。

---

## 治理目标与方案

1. **补全 DDL 脚本**：
   - 梳理现有 HeatWave 生产实例上上述视图与表的定义语句（`SHOW CREATE VIEW` / `SHOW CREATE TABLE`）。
   - 将其完整补入 `data-bridge/src/db_setup.py` 中，或在 `database/schema.sql` 中统一版本化维护。
2. **提供标准 MySQL 语法兼容支持**：
   - 为缺少 HeatWave 专有加速引擎的环境提供标准 SQL 视图定义。

---

## 开源范围修复进展（本地验证通过）

`db_setup.py` 已补充遥测归档表、异常表、训练表、小时聚合视图及 API 依赖的分析视图，并为旧库增加 `rtt_ms` 幂等迁移。训练表与模型目录 schema 已环境化；HeatWave 专属状态表不可用时会降级为空指标。Python 编译、单元测试和开源配置审计均已通过，贡献者无需安装本地数据库。

## 完成定义

- [x] 固化 API 当前依赖的数据库对象定义
- [x] 在 `db_setup.py` 中集成幂等建表、视图和旧库列迁移逻辑
- [x] 在部署文档中记录 Oracle MySQL HeatWave 初始化和回滚边界
- [x] 本地测试不依赖 MySQL、Docker 或维护者基础设施
- [x] 同步更新本文档状态为 DONE，更新日期变更为完成当天
- [x] 同步更新 `docs/KNOWN-ISSUES.md` 看板条目为 DONE

## 部署验证（不阻塞开源发布）

在操作者自有的 Oracle MySQL HeatWave 测试 schema 中验证 DDL 和视图兼容性。该检查属于部署验收，详见 [`docs/deployment/ORACLE-HEATWAVE.md`](../deployment/ORACLE-HEATWAVE.md)。
