# LLM Applications and Agents / 大模型应用与 Agent

This repository collects what I learn about building applications on large language models: the agent harness around a model, and retrieval-augmented generation (RAG). Each note starts from a real question, explains the mechanism behind it, and records what I tested.

这里记录我系统学习大模型应用开发时整理的笔记，分两个主题：让模型变成可工作 agent 的 **Harness**，以及让模型基于外部资料回答的 **RAG**。每篇笔记从一个实际问题出发，讲清背后的原理，并记录动手验证的结果。

## Topics / 主题

- [Harness](Harness/README.md)：agent loop、上下文工程、工具与 MCP、skills、hooks、沙箱、权限、记忆、持久执行、评估与观测。
- [RAG](RAG/README.md)：解析与切块、embedding、向量检索内核（IVF、PQ、HNSW、DiskANN）、混合检索与重排、生成、评估与生产。

每个主题的 README 是该主题的学习路线：知识点、要掌握的深度、常见问法和出处。

## Notes / 笔记

暂无。笔记会按主题放在对应目录下，写好后列在这里。

## 从问题出发 / Starting questions

这些是学习的起点，也是常见的面试问法。每题对应到主题 README 里的知识点。

| # | 问题 | 知识点 |
|---|---|---|
| 1 | 介绍一下 harness | Harness 1.1–1.3 |
| 2 | 提示词工程、上下文工程与 harness 有何关联 | Harness 2.1–2.3 |
| 3 | 除了 prompt、context，harness 还有什么部分 | Harness 1.2，Harness M3–M10 |
| 4 | 沙箱是什么 | Harness 6.1–6.3 |
| 5 | 如何控制访问安全 | Harness 7.1–7.3，另见 Harness 3.4、5.1、6.3 |
| 6 | 多用户多角色下如何限制 skills 访问 | Harness 7.4，另见 Harness 4.1、3.4、5.1 |
| 7 | 记忆模块：短期记忆之外还有什么 | Harness 8.1–8.3 |
| 8 | RAG 是什么，解决什么问题 | RAG 1.1、1.2、5.2 |
| 9 | RAG 索引阶段的流程 | RAG 2.1–2.6，另见 RAG 3.9、8.3 |
| 10 | 向量库为什么能快速返回 top-k，算法原理 | RAG 3.1–3.8 |

### 答题骨架（面试时可直接展开）

**Q1 介绍 harness**
1. 定义：Agent = Model + Harness。
2. agent loop 与停止条件。
3. 组件清单：工具、skills、hooks、沙箱、权限、记忆、状态、评估与观测。
4. 为什么重要：同一个模型换一套 harness，效果差别很大；每个组件都隐含着「模型自己做不到什么」的假设，模型升级后要重新检验。

**Q2 三者的关系**
- prompt 管「写什么」；
- context 管「每一步往上下文里放什么」；
- harness 管「由谁来放、怎么执行」。

**Q5 访问安全**
1. 身份。
2. 最小权限。
3. 确定性执行点：deny 规则、hook、沙箱。
4. 注入防御。
5. 人工审批。
6. 审计。

**Q6 多角色限制 skills**
1. 身份与委托凭据。
2. 装配期：按角色过滤可用的 tools、skills。
3. 执行期：策略逐次复核。
4. 下游资源服务器按 scope 再校验一次。
5. skill 的治理与租户隔离。

**Q7 记忆**
1. 短期记忆：working memory，也就是线程状态。
2. 长期记忆的三类：episodic、semantic、procedural。
3. 存储形态：文件、向量、图。
4. 写入、检索、遗忘。
5. 安全与隔离。

**Q10 向量检索**
1. 用同一个 embedding 模型把 query 编码。
2. 根据 filter 的基数制定查询计划。
3. 在 ANN 索引里找候选：HNSW 在顶层贪心下降，到 layer0 用 efSearch 做 beam search；IVF 则只扫 nprobe 个 cell。
4. 用压缩向量算近似距离。
5. 用原始向量 rescore。
6. 取 top-k；分布式时各分片取 top-k 再合并。

最后讲 recall、延迟、内存三者的权衡，以及对应的参数。

## 学习顺序 / Study plan

每个阶段都配一个动手练习，做完再写这一阶段的笔记。

1. **Agent loop 与最简 RAG**（Harness M1；RAG M1、2.1、2.3、2.5、5.1）
   - 不用框架，手写一个约 150 行的 agent loop：两个工具（`read_file`、`run_python`），加上 `max_turns` 和预算上限，工具异常以 `is_error` 返回。
   - 用 FAISS Flat 加一个 embedding API，给自己的课程 PDF 做一个带引用的最简 RAG，并把它接进上面的 loop 当工具。
   - 手工标 30 个问题，测 recall@5。

2. **向量检索内核**（RAG M3，重点）
   - 用 numpy 写暴力 kNN。
   - 在 SIFT1M 或 glove-100 上，用 FAISS 跑三种索引并画出 recall@10 与 QPS 的曲线，记录内存和构建时间：
     - IVF-Flat：调 nlist、nprobe；
     - IVF-PQ：调 m；
     - HNSW：调 M、efSearch。
   - 用约 200 行 Python 手写一个简化版 IVF 或 HNSW。
   - 在 pgvector 里构造一个只命中 10% 数据的过滤条件，复现「结果不足 k 条」，再打开 `iterative_scan` 对比。

3. **上下文工程与检索质量**（Harness M2；RAG M4、7.1）
   - 给 loop 加 token 计数：超过阈值时先清掉旧的工具结果，仍然超限再做 compaction。
   - 固定 system 前缀，对比 prompt cache 命中前后的成本。
   - 在 BEIR 的 SciFact 和 FiQA 上，比较 BM25、dense、hybrid（RRF）、hybrid 加 cross-encoder 四种方案的 nDCG@10 和 recall@100。

4. **工具、MCP、Skills、Subagent**（Harness M3、M4）
   - 写一个 Streamable HTTP 的 MCP server：一个只读工具加一个写工具，接入自己的 loop。
   - 写一个 SKILL.md 加脚本，自己实现三级加载：启动时只注入 name 和 description。
   - 加一个只读的搜索 subagent。

5. **Hooks、沙箱、权限（两块共用）**（Harness M5–M7；RAG 8.3）
   - 写一个 PreToolUse hook，拦截 `rm -rf`、读取 `~/.ssh`、`curl` 白名单以外的域名，并写审计日志。
   - 用 bubblewrap 或 `docker run --network none` 来执行 `run_python`。
   - 实现 user、admin 两种角色：装配期按角色过滤 tools 和 skills，执行期再做一次策略校验。
   - RAG 这边给每个 chunk 带上 ACL，在向量库层做 pre-filter。
   - 做一个间接注入的 demo（网页里藏指令），再用「去掉外发工具」或 plan-then-execute 防住。

6. **记忆、持久执行、摄入与生成**（Harness M8、M9；RAG 2.2、2.4、M5、7.2、7.3）
   - 实现一个 memory tool：按用户分 namespace、防路径穿越、TTL 过期，semantic 和 episodic 分开存。
   - 用 LangGraph 的 checkpointer 加 interrupt 实现「审批后继续」；写操作带幂等键，模拟崩溃后恢复。
   - 用 Docling 解析表格多的 PDF，比较 fixed、structure-aware、parent-child、contextual retrieval 四种切块方式。
   - 实现引用校验，并用 RAGAS 测 faithfulness。

7. **评估、观测、生产与前沿**（Harness M10；RAG M8、M6）
   - 准备 20 个 agent 任务，每个跑 5 次，计算 pass@1 和 pass^5；判分用 code grader 加 LLM judge。
   - 导出 OTel spans。
   - 把 RAG 做成多租户：用 content hash 做增量更新，并测删除后的一致性。
   - 用系统设计题收尾：「1000 万文档、5000 个租户的企业知识助手」。

## Language / 语言

The study notes are written primarily in Chinese.

学习笔记以中文为主。
