# Harness

Harness 指模型之外、把 LLM 变成可工作 agent 的全部部分：agent loop、上下文管理、工具与 MCP、skills、hooks、沙箱、权限、记忆、持久执行、评估与观测。

学习路线见 [ROADMAP.md](../ROADMAP.md#harness) 的 Harness 部分。

## 笔记

- [手写一个 agent loop：最少需要哪些东西？](01-agent-loop.md)：不用框架写约 200 行的 loop，讲清停止条件、工具错误以 `is_error` 回传、多个工具调用怎么执行。
