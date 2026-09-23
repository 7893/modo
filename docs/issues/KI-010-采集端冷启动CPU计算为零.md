# KI-010 · 采集端冷启动CPU计算为零

- 状态：DONE
- 优先级：P2
- 更新日期：2026-09-23
- 适用范围：`data-bridge/src/ingest.py`
- 关联：[已知问题看板](../KNOWN-ISSUES.md)

---

## 结论

在 [`data-bridge/src/ingest.py`](../../data-bridge/src/ingest.py) 中，各节点的 CPU 使用率是通过前后两次 Prometheus 采样周期的 CPU 累计秒数差值（ΔCPU）计算的。当采集守护进程初次启动或因异常重启时，内存全局状态 `_previous_cpu_state` 为空。导致所有节点在服务启动后的第一轮采样入库时，其 `cpu_usage_percent` 均被强制设为 `0.0%`，污染了时序图表并导致监控曲线出现非预期的突发断崖下跌。

---

## 只读证据（2026-09-23）

### 1. 初次抓取缺少前置状态直接置零
在 [`data-bridge/src/ingest.py#L122`](../../data-bridge/src/ingest.py#L122) 与 [`#L262-L281`](../../data-bridge/src/ingest.py#L262-L281) 中：
```python
# Global state for CPU usage calculation
_previous_cpu_state = {}  # Format: { "node_name": {"timestamp": float, "cpu_total": float, "cpu_idle": float} }

# ... 在 scrape_single_node 中：
prev = _previous_cpu_state.get(node["name"])
if prev:
    delta_total = parsed["cpu_total_secs"] - prev["cpu_total"]
    delta_idle = parsed["cpu_idle_secs"] - prev["cpu_idle"]
    if delta_total > 0:
        cpu_usage = 100.0 * (1.0 - (delta_idle / delta_total))
        result["cpu_usage_percent"] = max(0.0, min(100.0, round(cpu_usage, 2)))
# 若 prev is None，result["cpu_usage_percent"] 保持第 232 行默认初始化的 0.0%
```

---

## 影响分析

1. **时序图表失真**：每次更新或发布重启 `modo.service` 时，ECharts 历史波形图中都会记录一个刻度为 0% 的异常点。
2. **告警误判**：如果上游配置了低负载或异常波动告警规则，服务重启可能会触发短时的假警报。

---

## 治理目标与方案

1. **冷启动快速预热采样**：
   - 在采集器启动时，先进行一次只读初始采样建立基准，等待短暂间隔（如 1 秒）后再进行正式第一轮抓取入库。
2. **可选 NULL 语义**：
   - 当前表只保存计算后的 CPU 百分比，没有保存 node_exporter 的累计 CPU/idle 计数，因此无法从现有记录恢复差分基线。若不采用预热，应将首轮值标记为 `NULL`。

---

## 本地修复进展（本地验证通过）

采集服务启动后先并发执行一次不入库的预热采样，等待可配置的 `CPU_WARMUP_SECONDS` 后才进入正式管线，避免首轮持久化为假 0%。测试已确认预热发生在正式管线之前，第二次 CPU 累计值能计算出非零使用率。实际部署重启后的图表观察属于运行验收，不阻塞开源代码关闭。

## 完成定义

- [x] 采集进程启动时先建立 CPU 累计计数基线
- [x] 单元序列确认首个持久化样本不再使用冷启动假零值
- [x] 同步更新本文档状态为 DONE，更新日期变更为完成当天
- [x] 同步更新 `docs/KNOWN-ISSUES.md` 看板条目为 DONE

## 部署验证（不阻塞开源发布）

部署者可在维护窗口重启采集服务，并观察实际时序图没有新增冷启动假零毛刺。
