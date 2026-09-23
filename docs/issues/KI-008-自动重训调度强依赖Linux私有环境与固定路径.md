# KI-008 · 自动重训调度强依赖Linux私有环境与固定路径

- 状态：DONE
- 优先级：P1
- 更新日期：2026-09-23
- 适用范围：`data-bridge/src/api.py`
- 关联：[已知问题看板](../KNOWN-ISSUES.md)

---

## 结论

在原实现中，后台线程使用固定虚拟环境路径及 Linux 专属 `nice`、`ionice` 命令启动训练。在命令缺失时异常会被捕获并记录，线程不会静默崩溃；但原调度只在周日 03 点窗口执行，失败后通常会错过整周重训。

---

## 只读证据（2026-09-23）

### 1. 外部依赖与固定路径硬编码
在 [`data-bridge/src/api.py#L797-L804`](../../data-bridge/src/api.py#L797-L804) 中：
```python
script_path = os.path.join(os.path.dirname(__file__), "train_latency_model.py")
venv_python = os.path.join(os.path.dirname(__file__), "..", "venv", "bin", "python")
# Run with low priority to not impact production
result = subprocess.run(
    ["nice", "-n", "19", "ionice", "-c", "3", venv_python, script_path],
    capture_output=True, text=True, timeout=600,
    cwd=os.path.dirname(script_path)
)
```
1. `ionice` / `nice`：许多精简镜像（如 Alpine）、容器环境或 Windows/macOS 开发机上并未安装或允许调用 `ionice`，会直接引发 `FileNotFoundError: [Errno 2] No such file or directory: 'ionice'`。
2. `venv_python`：若开发者以系统 Python、Conda 环境或全局容器环境启动，`../venv/bin/python` 物理文件并不存在。

---

## 影响分析

1. **容器化阻断**：任何将 `data-bridge` 打包为标准 Docker 容器的尝试，都会在执行重训时遇到命令缺失错误。
2. **缺乏自愈与感知**：重训失败仅在日志中输出一段字符串，无重试与异常告警机制。

---

## 治理目标与方案

1. **使用当前进程解释器**：
   - 使用标准库 `sys.executable` 替代手工拼接 `../venv/bin/python`。
2. **命令存在性安全探测或原生降级**：
   - 使用 `shutil.which("ionice")` 探测命令可用性，仅在存在时附加优先级参数，不存在时直接回退为标准 Python 进程调用。
   - 或者改用 Python 内部模块直接以多线程/后台协程方式调用训练主函数 `train_latency_model.main()`，彻底消除子进程拉起开销。

---

## 本地修复进展（本地验证通过）

调度器改用 `sys.executable`，通过 `shutil.which()` 按可用性附加 `nice`/`ionice`。只有训练成功才记录本周已完成；周日 03:00 后失败会按小时重试。线程改由 FastAPI 生命周期启动，并可通过 `AUTO_RETRAIN_ENABLED` 关闭，模块导入不再触发后台任务。测试已覆盖无 Linux 辅助命令时的回退路径及失败后保持待重试状态。

## 完成定义

- [x] 移除固定虚拟环境解释器路径，改用 `sys.executable`
- [x] 兼容无 `ionice` / `nice` 命令的环境
- [x] 失败不会错误标记完成，并可在当日重试
- [x] 后台线程不再于模块导入时启动，并提供显式启停配置
- [x] 同步更新本文档状态为 DONE，更新日期变更为完成当天
- [x] 同步更新 `docs/KNOWN-ISSUES.md` 看板条目为 DONE
