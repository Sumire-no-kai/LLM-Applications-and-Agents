# 大模型应用与 Agent：学习路线

整理于 2026-09-29，依据是 2025–2026 年的官方文档、工程博客和论文。产品和规范变化快，引用前请以出处的最新版本为准。

路线分两个主题：

- **Harness**：模型之外、把 LLM 变成可工作 agent 的全部部分。
- **RAG**：让模型基于外部资料回答。

两个主题互相支撑：

- 检索可以做成 agent 调用的工具；
- 长期记忆底层常常就是向量检索；
- 「多角色限制 skills」和「只检索用户有权看的文档」是同一类问题，都靠确定性的权限执行。

每个知识点写四项：**级**（基础 / 进阶 / 前沿）、**深**（要掌握到什么深度）、**问**（企业常见问法）、**源**（出处编号，Harness 部分记作 H1，RAG 部分记作 R1，见文末「来源」）。「未核实」表示只见于二手报道或搜索摘要，「判断」表示归纳出的结论而不是来源原话。

## 学习顺序

每个阶段都配一个动手练习，做完再写这一阶段的笔记。

1. **Agent loop 与最简 RAG**（Harness [M1](#m1harness-本体与-agent-loop)；RAG [M1](#m1rag-的定位)、[2.1](#21-端到端流程)、[2.3](#23-切块chunking)、[2.5](#25-embedding-模型)、[5.1](#51-上下文组装与-lost-in-the-middle)）
   - 不用框架，手写一个约 150 行的 agent loop：两个工具（`read_file`、`run_python`），加上 `max_turns` 和预算上限，工具异常以 `is_error` 返回。
   - 用 FAISS Flat 加一个 embedding API，给自己的课程 PDF 做一个带引用的最简 RAG，并把它接进上面的 loop 当工具。
   - 手工标 30 个问题，测 recall@5。

2. **向量检索内核**（RAG [M3](#m3向量检索内核重点)，重点）
   - 用 numpy 写暴力 kNN。
   - 在 SIFT1M 或 glove-100 上，用 FAISS 跑三种索引并画出 recall@10 与 QPS 的曲线，记录内存和构建时间：
     - IVF-Flat：调 nlist、nprobe；
     - IVF-PQ：调 m；
     - HNSW：调 M、efSearch。
   - 用约 200 行 Python 手写一个简化版 IVF 或 HNSW。
   - 在 pgvector 里构造一个只命中 10% 数据的过滤条件，复现「结果不足 k 条」，再打开 `iterative_scan` 对比。

3. **上下文工程与检索质量**（Harness [M2](#m2提示词工程上下文工程与-harness)；RAG [M4](#m4检索质量)、[7.1](#71-检索指标)）
   - 给 loop 加 token 计数：超过阈值时先清掉旧的工具结果，仍然超限再做 compaction。
   - 固定 system 前缀，对比 prompt cache 命中前后的成本。
   - 在 BEIR 的 SciFact 和 FiQA 上，比较 BM25、dense、hybrid（RRF）、hybrid 加 cross-encoder 四种方案的 nDCG@10 和 recall@100。

4. **工具、MCP、Skills、Subagent**（Harness [M3](#m3工具与-mcp)、[M4](#m4skillssubagents-与多-agent)）
   - 写一个 Streamable HTTP 的 MCP server：一个只读工具加一个写工具，接入自己的 loop。
   - 写一个 SKILL.md 加脚本，自己实现三级加载：启动时只注入 name 和 description。
   - 加一个只读的搜索 subagent。

5. **Hooks、沙箱、权限（两块共用）**（Harness [M5](#m5hooks-与生命周期)–[M7](#m7安全与访问控制)；RAG [8.3](#83-按权限检索与数据安全高频和-harness-74-是同一类问题)）
   - 写一个 PreToolUse hook，拦截 `rm -rf`、读取 `~/.ssh`、`curl` 白名单以外的域名，并写审计日志。
   - 用 bubblewrap 或 `docker run --network none` 来执行 `run_python`。
   - 实现 user、admin 两种角色：装配期按角色过滤 tools 和 skills，执行期再做一次策略校验。
   - RAG 这边给每个 chunk 带上 ACL，在向量库层做 pre-filter。
   - 做一个间接注入的 demo（网页里藏指令），再用「去掉外发工具」或 plan-then-execute 防住。

6. **记忆、持久执行、摄入与生成**（Harness [M8](#m8记忆)、[M9](#m9规划持久执行人工介入错误恢复)；RAG [2.2](#22-文档解析)、[2.4](#24-给-chunk-补上下文)、[M5](#m5生成)、[7.2](#72-生成指标与评测框架)、[7.3](#73-构建评测集)）
   - 实现一个 memory tool：按用户分 namespace、防路径穿越、TTL 过期，semantic 和 episodic 分开存。
   - 用 LangGraph 的 checkpointer 加 interrupt 实现「审批后继续」；写操作带幂等键，模拟崩溃后恢复。
   - 用 Docling 解析表格多的 PDF，比较 fixed、structure-aware、parent-child、contextual retrieval 四种切块方式。
   - 实现引用校验，并用 RAGAS 测 faithfulness。

7. **评估、观测、生产与前沿**（Harness [M10](#m10评估与可观测性)；RAG [M8](#m8生产)、[M6](#m6进阶与前沿)）
   - 准备 20 个 agent 任务，每个跑 5 次，计算 pass@1 和 pass^5；判分用 code grader 加 LLM judge。
   - 导出 OTel spans。
   - 把 RAG 做成多租户：用 content hash 做增量更新，并测删除后的一致性。
   - 用系统设计题收尾：「1000 万文档、5000 个租户的企业知识助手」。

## 常见问题

常见问法，以及每个问题对应的知识点（点编号可以跳过去）。

| # | 问题 | 知识点 |
|---|---|---|
| 1 | 介绍一下 harness | Harness [1.1](#11-harness-的定义与分层)–[1.3](#13-workflow-与-agent) |
| 2 | 提示词工程、上下文工程与 harness 有何关联 | Harness [2.1](#21-三者的关系)–[2.3](#23-管理上下文的手段) |
| 3 | 除了 prompt、context，harness 还有什么部分 | Harness [1.2](#12-agent-loop-与停止条件)，Harness [M3](#m3工具与-mcp)–[M10](#m10评估与可观测性) |
| 4 | 沙箱是什么 | Harness [6.1](#61-概念与动机)–[6.3](#63-网络出口与凭据隔离) |
| 5 | 如何控制访问安全 | Harness [7.1](#71-权限模式与审批)–[7.3](#73-最小权限秘钥与审计)，另见 Harness [3.4](#34-mcp-授权)、[5.1](#51-hooks)、[6.3](#63-网络出口与凭据隔离) |
| 6 | 多用户多角色下如何限制 skills 访问 | Harness [7.4](#74-多用户多角色限制-tools-和-skills)，另见 Harness [4.1](#41-agent-skills)、[3.4](#34-mcp-授权)、[5.1](#51-hooks) |
| 7 | 记忆模块：短期记忆之外还有什么 | Harness [8.1](#81-短期记忆)–[8.3](#83-存储写入检索遗忘与安全) |
| 8 | RAG 是什么，解决什么问题 | RAG [1.1](#11-rag-是什么解决什么问题)、[1.2](#12-rag微调与长上下文怎么选)、[5.2](#52-引用grounding-与-rag-prompt) |
| 9 | RAG 索引阶段的流程 | RAG [2.1](#21-端到端流程)–[2.6](#26-增量更新与删除)，另见 RAG [3.9](#39-更新删除分片与多租户)、[8.3](#83-按权限检索与数据安全高频和-harness-74-是同一类问题) |
| 10 | 向量库为什么能快速返回 top-k，算法原理 | RAG [3.1](#31-为什么需要-ann)–[3.8](#38-带过滤的检索高频) |

### 答题要点

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

## Harness

Harness 指模型之外、把 LLM 变成可工作 agent 的全部部分：agent loop、上下文管理、工具与 MCP、skills、hooks、沙箱、权限、记忆、持久执行、评估与观测。

### M1　Harness 本体与 agent loop

#### 1.1 Harness 的定义与分层
- **级**：基础
- **深**：
  - Agent = Model + Harness。harness 是模型之外的全部代码、配置和执行逻辑：system prompt、工具、沙箱、记忆、上下文管理、自检循环、子 agent 编排。
  - 分清三层：
    - harness / runtime：已经带好 loop、工具、权限和压缩，例如 Claude Code、Claude Agent SDK、Codex、Managed Agents。
    - framework：只提供图、状态、checkpoint 等原语，harness 要你自己拼，例如 LangGraph。
    - SDK：某个 harness 或 API 的编程接口。
  - 评测语境里的 agent harness，和 evaluation harness 不是一回事。
  - harness 的每个组件都编码了「模型自己做不到什么」的假设，模型升级后要重新检验这些假设。
- **问**：harness 和 LangGraph、OpenAI Agents SDK 是什么关系？同一个模型换一套 harness，分数为什么会变？
- **源**：H1 H2 H3 H4 H7

#### 1.2 Agent loop 与停止条件
- **级**：基础
- **深**：
  - 能手写这个循环：messages 加 tools 发给模型 → 模型返回 tool_use → harness 执行 → 把 tool_result 追加回去再调用模型 → 直到模型不再调工具（end_turn）为止。
  - 其他终止方式：`max_turns`、预算上限、`max_tokens`、refusal。
  - 被拒绝的工具调用也要以 tool_result 的形式回给模型。
  - 只读工具可以并行执行，有副作用的工具要串行。
- **问**：写出 loop 的伪代码。怎么防止死循环和成本失控？一次返回多个 tool call 时怎么执行？
- **源**：H5 H6

#### 1.3 Workflow 与 agent
- **级**：基础
- **深**：
  - workflow 是用预先写好的代码路径来编排 LLM；agent 是由 LLM 动态决定流程和用哪些工具。
  - 五种常见模式：prompt chaining、routing、parallelization、orchestrator-workers、evaluator-optimizer。
  - 先直接调 API，确实有收益时再加复杂度。
- **问**：什么样的任务不该做成 agent？
- **源**：H6

#### 1.4 长时程 harness
- **级**：进阶
- **深**：
  - initializer agent 先建好三样东西：feature 列表（JSON，初始全部标为 failing）、进度文件、git 提交。
  - 之后每轮只做一个 feature，并做端到端验证。
  - planner、generator、evaluator 分成三个角色，用来缓解模型评自己时的偏差。
  - 在部分模型上，清空上下文再加结构化交接，效果比 compaction 更好。
- **问**：让 agent 连续开发几个小时，状态怎么交接？怎么判定「完成」？
- **源**：H2 H7

### M2　提示词工程、上下文工程与 Harness

#### 2.1 三者的关系
- **级**：基础
- **深**：
  - prompt engineering：把指令本身写好。
  - context engineering：每一步都要决定哪些 token 进入窗口，包括指令、工具定义、历史、检索结果和记忆。它是 prompt engineering 在多轮 agent 场景下的延伸。
  - harness：把 context engineering 落地的执行系统，同时还负责行动、权限、状态和观测。
- **问**：原题 Q2。为什么 context engineering 不等于「写更长的 prompt」？
- **源**：H8 H11

#### 2.2 Context rot 与 attention budget
- **级**：基础→进阶
- **深**：
  - 输入越长性能越差，而且离窗口上限还很远时就开始下降。Chroma 测的 18 个模型全部如此，下降程度还受干扰项、needle 与问题相似度的影响。
  - 位置效应：lost in the middle，中间的信息最容易被忽略。
  - attention budget：token 之间是 n² 的两两关系，上下文越长，注意力摊得越薄。
- **问**：模型都有 1M 上下文了，还需要管理上下文吗？
- **源**：H8 H9 H10

#### 2.3 管理上下文的手段
- **级**：进阶
- **深**：
  - 四类手段：write、select、compress、isolate。
  - compaction 会丢掉早期指令，所以长期有效的规则要写进 CLAUDE.md / AGENTS.md，每次都重新注入。
  - 清理旧的工具结果。
  - just-in-time 检索：上下文里只留路径或 ID，需要时再读。
  - 结构化笔记；用 subagent 隔离上下文。
  - 工具结果做分页和截断。
  - 成本上：保持前缀稳定、只追加不改写，以提高 KV-cache 命中率。Manus 把命中率当作最重要的指标。
- **问**：compaction 会丢什么，怎么补救？怎样设计上下文才能提高缓存命中？
- **源**：H5 H8 H11 H12

### M3　工具与 MCP

#### 3.1 Function calling 与结构化输出
- **级**：基础
- **深**：
  - 工具由名称、描述和 JSON Schema 组成。模型只「提出」调用，真正执行的是 harness。
  - OpenAI 的 strict 模式要求 `additionalProperties:false`，并且所有字段都是 required。
  - schema 合法不等于业务合法，harness 仍要校验参数和权限。
- **问**：模型给出非法参数，或者编出一个不存在的工具名，harness 怎么处理？
- **源**：H13

#### 3.2 工具设计（ACI，agent-computer interface）
- **级**：进阶
- **深**：
  - 工具少而精，按服务做 namespacing。
  - 返回高信号、可读的标识，而不是一长串内部 ID。
  - 提供 `response_format`（concise / detailed），支持分页。
  - 错误信息要让模型知道下一步怎么做。
  - 用防呆设计防止误用，并用 eval 反复迭代工具描述。
- **问**：给 agent 设计一个 `search_logs` 工具，参数和返回值怎么定？
- **源**：H6 H14

#### 3.3 MCP 架构与传输
- **级**：基础→进阶
- **深**：
  - host、client、server 三方，基于 JSON-RPC 2.0。
  - server 提供 tools、resources、prompts；client 提供 elicitation。
  - 传输方式：stdio 和 Streamable HTTP；旧的 HTTP+SSE 已弃用。
  - 2026-07-28 版规范的变化（已对照官方博客核实）：
    - 核心改为无状态，取消了 `initialize` 握手和 `Mcp-Session-Id`；
    - 新增 Multi Round-Trip Requests：工具调用中途可以向用户要确认或缺失的参数；
    - 请求必须带 `Mcp-Method` 和 `Mcp-Name` 头，方便网关路由；
    - Tasks 移到扩展中；
    - Roots、Sampling、Logging 标为弃用，但至少还会保留 12 个月。
- **问**：MCP 和 function calling 是什么关系？stdio 和 Streamable HTTP 怎么选？
- **源**：H15 H16

#### 3.4 MCP 授权
- **级**：进阶
- **深**：
  - MCP server 的角色是 OAuth 2.1 resource server。客户端通过它的 Protected Resource Metadata（RFC 9728）找到授权服务器，授权时用 PKCE。
  - 用 RFC 8707 的 `resource` 参数绑定 token 的受众，server 必须校验这个 token 是签给自己的。
  - 禁止把用户的 token 直接转发给下游（token passthrough）。
  - 权限不够时返回 403 `insufficient_scope`，客户端据此发起提权授权（step-up）。
  - 客户端注册优先用 CIMD。
  - 要了解 confused deputy 这类攻击。
- **问**：MCP server 需要调用下游的 GitHub API，能不能直接转发用户的 token？
- **源**：H17 H18

#### 3.5 工具多了怎么选
- **级**：进阶／前沿
- **深**：
  - 工具定义本身就占上下文，工具一多，选择准确率也会下降。
  - 对策：
    - tool search：工具定义延迟加载；
    - programmatic tool calling：让模型写代码在沙箱里调用工具，只把过滤后的结果带回上下文；
    - 按角色裁剪工具集。
- **问**：接入 300 个工具后准确率下降、token 暴涨，怎么改？
- **源**：H5 H19 H20

### M4　Skills、Subagents 与多 agent

#### 4.1 Agent Skills
- **级**：进阶
- **深**：
  - 一个 skill 是一个目录：SKILL.md（YAML 里写 name 和 description，正文写指令），可以附带脚本和资源。
  - 三级按需加载（progressive disclosure）：
    - L1：元数据在启动时进入 system prompt，每个 skill 约 100 token；
    - L2：触发后才读取正文，控制在 5k token 以内；
    - L3：资源按需读取；脚本只把输出带回上下文。
  - 依赖文件系统和代码执行环境。
  - 2025-12 成为开放标准（agentskills.io），Codex 等产品已支持。
  - 区分三者：tool 是可以调用的接口；MCP 是连接外部系统的协议；skill 是按需加载的流程知识加脚本。
- **问**：skill 和 tool、MCP、system prompt 有什么区别？装了 100 个 skill，为什么不会撑爆上下文？
- **源**：H21 H22 H23

#### 4.2 Subagents
- **级**：进阶
- **深**：
  - 子 agent 有自己独立的上下文，只拿到父 agent 传来的 prompt 字符串，最后一条消息作为 tool result 返回给父 agent。
  - 可以单独限定它能用的 tools、model、权限模式。
  - 要设深度、并发和预算的上限。
- **问**：subagent 解决什么问题？什么时候用了反而更差？
- **源**：H24

#### 4.3 Orchestrator-worker、handoff、agent-as-tool、A2A
- **级**：进阶
- **深**：
  - Anthropic 的 Research 系统：lead agent 并行派出 3–5 个 subagent，效果比单个 Opus 4 高 90.2%，但消耗约为普通 chat 的 15 倍 token；token 用量能解释 BrowseComp 上 80% 的得分差异。
  - OpenAI Agents SDK：
    - handoff 以 `transfer_to_<agent>` 工具的形式出现，默认把全部历史交给下一个 agent，可以用 `input_filter` 裁剪；
    - `as_tool()` 不转移控制权，只是把另一个 agent 当工具调用。
  - 跨组织的 agent 互通用 A2A 协议，用 Agent Card 描述能力。
- **问**：handoff 和 agent-as-tool 有什么区别？多 agent 值不值这份成本？
- **源**：H25 H26 H27

### M5　Hooks 与生命周期

#### 5.1 Hooks
- **级**：进阶
- **深**：
  - hook 是挂在 loop 固定节点上的确定性代码，不占上下文。
  - 常见事件：SessionStart、UserPromptSubmit、PreToolUse、PermissionRequest、PostToolUse、PreCompact、Stop、SubagentStart/Stop。
  - PreToolUse 可以返回 allow、deny、ask；command 类型的 hook 退出码为 2 表示阻断。
  - 关键细节：hook 返回 allow，也绕不过 deny / ask 规则。
  - 典型用途：拦截危险命令、改写输入、自动格式化或跑 lint、写审计日志、注入上下文、在 Stop 时检查是否真的完成。
  - OpenAI 的对应机制是 input / output / tool guardrails（通过 tripwire 中断）；LangChain 1.x 叫 middleware（未核实）。
- **问**：为什么「禁止 rm -rf」要写成 hook，而不是写进 prompt？PostToolUse 能撤销已经执行的操作吗？
- **源**：H28 H29 H30

### M6　沙箱与隔离

#### 6.1 概念与动机
- **级**：基础
- **深**：
  - 沙箱是由操作系统或虚拟化强制执行的边界，限制命令及其子进程能读写哪些路径、能访问哪些网络、能用哪些系统调用和资源。
  - 为什么需要：
    - 假定模型会犯错、会被注入，用确定性的边界限制出事后的影响范围；
    - 减少审批疲劳：Anthropic 内部统计，权限提示因此减少了 84%。
  - 文件隔离和网络隔离缺一不可：没有网络隔离，SSH key 可能被外泄；没有文件隔离，系统配置可能被改掉。
- **问**：原题 Q4。只做文件隔离行不行？
- **源**：H31 H32

#### 6.2 隔离技术谱系
- **级**：进阶
- **深**：
  - 由弱到强：
    1. 进程级：macOS Seatbelt、Linux bubblewrap（namespaces）加 seccomp / Landlock。Claude Code 和 Codex 在本地用的就是这一层。
    2. 容器：和宿主共享内核。
    3. gVisor：在用户态实现一个应用内核，拦截系统调用。
    4. Firecracker microVM：基于 KVM，有独立的 guest kernel，E2B 等平台在用。
    5. 完整虚拟机。
  - Anthropic 各产品的选择：claude.ai 的代码执行用 gVisor；Claude Code 本地用 Seatbelt / bubblewrap；Cowork 用虚拟机。
  - 选型时权衡：隔离强度、启动时延、兼容性、GPU 支持、多租户。
- **问**：多租户 SaaS 要执行模型生成的代码，选 Docker、gVisor 还是 Firecracker？
- **源**：H32 H33 H34 H35

#### 6.3 网络出口与凭据隔离
- **级**：进阶
- **深**：
  - 网络出口走代理，按域名白名单放行。要能说出它的局限：
    - 代理默认不解密 TLS，存在 domain fronting 风险；
    - 放行 github.com 这类宽泛的域名，本身就是外泄通道；
    - 放行 docker.sock 这类 unix socket 可以提权；
    - 默认策略下仍然读得到 `~/.ssh`，要显式 deny。
  - 凭据放在沙箱外面，由代理代为签名，例如 Claude Code on the web 的 git 代理。
  - OpenAI Agents SDK 2026-04 的更新：把可信的 harness 和不可信的沙箱计算分开。
- **问**：agent 要 push 代码，但不能接触 SSH key，怎么设计？
- **源**：H31 H32 H33 H36

### M7　安全与访问控制

#### 7.1 权限模式与审批
- **级**：基础
- **深**：
  - 判定顺序：hooks → deny → ask → 权限模式 → allow → 回调。
  - deny 在任何模式下都生效；只写工具名的 deny 会把这个工具的定义直接从请求里移除。
  - 配置分层，最高是 managed 层；任何一层的 deny 都不能被其他层放行。
  - 权限模式从严到宽：default、acceptEdits、plan、auto（由分类器代为审批）、bypass。
  - Codex 把两个维度分开：sandbox mode 管「能做什么」，approval policy 管「什么时候要问」。
- **问**：原题 Q5。怎样避免审批疲劳，又不至于放任？
- **源**：H29 H35 H37 H38

#### 7.2 Prompt injection
- **级**：进阶→前沿
- **深**：
  - 直接注入：用户自己越狱。
  - 间接注入：恶意指令藏在网页、邮件、文件、工具结果、第三方 skill 或 MCP 描述里。
  - Lethal trifecta：私有数据、不可信内容、对外通信三者同时具备时，就可能发生外泄。
  - 分层防御：
    - 架构层：去掉 trifecta 中的一项；plan-then-execute；CaMeL（从可信查询中提取控制流，用 capability 限制数据流）；论文总结的六种防注入设计模式。
    - 环境层：沙箱和出口控制。
    - 检测层：用分类器扫描工具结果。
    - 人工审批。
  - 可参考 OWASP Top 10 for Agentic Applications 2026（逐条内容未核实）。
- **问**：邮件助手读到一封恶意邮件后把客户数据外发了，从架构上怎么防？
- **源**：H39 H40 H41 H42 H43

#### 7.3 最小权限、秘钥与审计
- **级**：基础
- **深**：
  - 工具、路径、域名一律用白名单。
  - 秘钥不进上下文、不进沙箱：清理环境变量、打码、由代理注入。
  - 审计要记下：谁、代表谁、调了什么、用什么参数、结果如何、由谁放行（规则、hook、人还是分类器）。
  - 可以用 OTel GenAI spans 表示，但这套约定目前还是 Development 状态。
- **问**：agent 要用第三方 API key，怎么做到模型看不到、也泄露不出去？
- **源**：H32 H44

#### 7.4 多用户多角色：限制 tools 和 skills
- **级**：进阶
- **深**：核心原则是授权由 harness 和工具层确定性地执行，prompt 里的说明只是说明。分四层讲：
  - **身份**：
    - 每个请求都带上 user、tenant、role（来自 IdP 签发的 token）。
    - 访问下游时用委托凭据：OAuth scopes，或者 RFC 8693 token exchange（能区分 delegation 和 impersonation）。
    - 不用共享的超级账号。
  - **装配期**：
    - 按角色构造本次会话能看到的 tools、skills 和 MCP servers。看不到就调不了，还省上下文。
    - 用 deny 规则按名字禁止具体的 skill。
    - API 上传的 skill 在整个 workspace 内共享，所以要把 workspace 当作租户边界。
  - **执行期**：
    - 由 PreToolUse hook 或策略引擎逐次判定：RBAC 看角色，ABAC 看主体、资源和环境属性（NIST SP 800-162）。
    - 下游资源服务器再按 token 的 scope 校验一次。
    - 注意：skill 的 `allowed-tools` 只是预先批准，不起限制作用；真正的限制要靠 deny 规则。
  - **治理**：
    - skill 上线前走审核清单，作者和审核人分开；锁定版本、做校验和，按角色打包。
    - memory、向量库、缓存、沙箱都按租户分区。
- **问**：原题 Q6。只在 system prompt 里写「普通用户不能用导出 skill」为什么不够？
- **源**：H17 H21 H29 H45 H46 H47 H48

### M8　记忆

#### 8.1 短期记忆
- **级**：基础
- **深**：
  - 当前线程的消息历史和工作状态，CoALA 称为 working memory。
  - 由 checkpointer 持久化，进程崩溃后可以恢复。
  - 同样会受 context rot 影响，需要压缩。
- **问**：短期记忆就等于 context window 吗？
- **源**：H49 H50

#### 8.2 长期记忆的类型
- **级**：基础
- **深**：
  - CoALA 分三类：
    - episodic：经历过什么；
    - semantic：事实知识；
    - procedural：怎么做，可能体现为权重、代码或 prompt。
  - LangGraph 里的对应：
    - semantic：用户的事实和画像；
    - episodic：过去成功的轨迹，拿来当 few-shot；
    - procedural：可以自我更新的 system prompt。
  - skills 和 AGENTS.md 也可以看作 procedural memory。
  - MemGPT / Letta 的分层：
    - core：常驻上下文的 block；
    - recall：可检索的对话历史；
    - archival：放在向量库里，要通过工具查询。
- **问**：原题 Q7。procedural memory 在 agent 里具体长什么样？
- **源**：H49 H50 H51 H52

#### 8.3 存储、写入、检索、遗忘与安全
- **级**：进阶
- **深**：
  - **存储**：
    - memory 文件：CLAUDE.md、自动记忆的 MEMORY.md；
    - Claude memory tool 在客户端执行 `/memories` 的读写；
    - 向量库；
    - 知识图谱：Zep / Graphiti 给每条事实记录有效时间；
    - Mem0：抽取 → 合并 → 检索。
  - **组织方式**：profile 是一份持续更新的文档，collection 是多条独立记录。
  - **写入**：在请求路径上同步写，或者后台异步写（例如 Letta 的 sleep-time agent）。
  - **检索**：Generative Agents 用「近因 + 重要性 + 相关性」打分，并做 reflection。
  - **遗忘**：TTL、去重合并、冲突时按时间覆盖。
  - **安全**：防路径穿越、过滤敏感信息、按租户隔离、防记忆投毒（被注入的内容写进了长期记忆）。
- **问**：设计用户偏好记忆：怎么判断该记什么？记错了怎么改？怎么防投毒？
- **源**：H49 H52 H53 H54 H55 H56 H57 H58

### M9　规划、持久执行、人工介入、错误恢复

#### 9.1 ReAct、plan-and-execute、reflection
- **级**：基础
- **深**：
  - ReAct：推理和行动 / 观察交替进行。
  - plan-and-execute：先出计划再执行，便于审批和隔离注入；缺点是计划僵化，需要重新规划。
  - Reflexion：把失败的反馈写成文字，存进 episodic memory。
  - 模型原生的推理能力变强之后，显式的 planner 组件可能变得多余。
- **问**：ReAct 和 plan-and-execute 各适合什么场景？
- **源**：H2 H59 H60 H61

#### 9.2 持久执行与人工介入（HITL）
- **级**：进阶
- **深**：
  - LangGraph：checkpointer 配合 `thread_id` 保存状态；`interrupt()` 暂停等人工输入，`Command(resume=...)` 继续。
  - Temporal：workflow 部分靠确定性重放恢复，I/O 放在 activity 里。
  - 有副作用的操作带幂等键，防止重试时重复执行。
  - Anthropic 的工程实践：从出错点恢复；用 rainbow deployment 避免部署打断正在运行的 agent。
- **问**：agent 执行到一半崩溃了，怎么恢复，又不重复下单？
- **源**：H5 H25 H62 H63

#### 9.3 错误恢复
- **级**：进阶
- **深**：
  - 工具出错时，以 `is_error` 的 tool_result 回给模型，让它自己纠正。
  - 区分可重试和不可重试的错误；用退避和熔断。
  - 设轮次和预算上限。
  - 用测试、lint 这类外部信号验证结果。
  - 控制流握在自己手里，保证随时能中断、序列化和恢复。
- **问**：工具连续超时，agent 应该怎么办？
- **源**：H5 H53 H64

### M10　评估与可观测性

#### 10.1 Agent evals
- **级**：进阶
- **深**：
  - 基本概念：task、trial、grader、transcript、outcome。
  - grader 分三类：代码判分、模型判分、人工判分。
  - pass@k 看能力，指 k 次里至少成功一次；pass^k 看可靠性，指 k 次全部成功。
  - 区分能力评测和回归评测。
  - 评的是 model 加 harness 的整体，优先检查环境的最终状态。
- **问**：给一个客服 agent 设计 eval。为什么要看 pass^k？
- **源**：H3

#### 10.2 基准及其局限
- **级**：进阶
- **深**：
  - τ-bench：按对话结束时的数据库状态判分，并提出了 pass^k。τ²-bench 进一步让用户也能操作环境（dual-control）。
  - SWE-bench Verified：OpenAI 以测试有缺陷、数据污染为由，已经不再报告这个基准的成绩。
  - SWE-bench Pro 的审计问题（未核实，原文打不开）。
  - 共同的局限：数据污染、测试缺陷、harness 差异、结果方差。
- **问**：某个模型 SWE-bench 分数很高，能说明它在你的业务里一定好用吗？
- **源**：H65 H66 H67 H68

#### 10.3 Tracing、成本与延迟
- **级**：基础
- **深**：
  - trace 是一棵 span 树：agent → 模型调用 → 工具调用，可以按 OTel GenAI 约定输出。
  - 成本量级：单 agent 约是普通 chat 的 4 倍 token，多 agent 约 15 倍。
  - 降本降延迟的手段：prompt caching、子任务用小模型、调低推理强度、并行调用工具。
- **问**：线上 agent 变慢变贵了，怎么定位？
- **源**：H5 H25 H44

### 术语尚未统一
- **harness**：
  - LangChain 的说法是「模型之外的一切」。
  - Anthropic 把 Agent SDK 和 Managed Agents 都叫 harness；在评测文章里，它和 scaffold 同义。
  - 「harness engineering」一般追溯到 2026 年初 Mitchell Hashimoto 的博文和 OpenAI 的 Codex 文章，谁最先提出有争议。
  - harness、runtime、scaffold、framework 之间的边界，各家说法不一。
- **context engineering**：Anthropic 认为它是 prompt engineering 的延伸，不是替代。
- **记忆**：三套分类并存——CoALA 的认知科学分法，Letta 的 core / recall / archival，以及产品里的「记住偏好」。
- **扩展点**：Claude Code 叫 hooks，OpenAI 叫 guardrails，LangChain 叫 middleware。
- **skill**：Anthropic 的 Agent Skills 专指这套 SKILL.md 开放标准；在别的框架里，skill 常常就是指 tool 或插件。
- **sandbox**：从操作系统的进程沙箱到 microVM 都叫 sandbox，回答时要说清隔离边界在哪一层。

## RAG

RAG（检索增强生成）让模型基于外部资料回答：从文档解析、切块、embedding 到向量检索内核、混合检索与重排，再到生成、评估和生产中的权限与新鲜度。

### M1　RAG 的定位

#### 1.1 RAG 是什么，解决什么问题
- **级**：基础
- **深**：
  - 流程是 retrieve → augment → generate，把参数记忆（模型本身学到的）和非参数记忆（外部资料）结合起来。
  - 原始论文（Lewis 2020）会联合训练 retriever 和 generator；今天工程上说的 RAG，一般只是把检索结果拼进 prompt。
  - 它解决的问题：知识截止日期、私有数据、减少幻觉（不能消除）、回答可引用可溯源、知识可以按时效和权限更新而不用重新训练。
  - 演进路线：Naive → Advanced → Modular。
- **问**：RAG 解决什么问题？有了 RAG 为什么还会幻觉？
- **源**：R1 R2 R6

#### 1.2 RAG、微调与长上下文怎么选
- **级**：进阶
- **深**：
  - 微调适合改行为、格式和风格，拿来注入新事实效果差。在新知识任务上，RAG 明显胜过微调。
  - 长上下文在资源充足时平均效果更好，但成本高。Self-Route 让模型自己判断走 RAG 还是长上下文，成本降了 39–65%。
  - Anthropic 的建议：知识库小于 20 万 token 时，直接整份放进 prompt。
  - 决策维度：数据量、更新频率、权限要求、是否需要引用、延迟和成本。
- **问**：什么时候该选微调？模型都有 1M 上下文了，还需要 RAG 吗？
- **源**：R3 R4 R5

### M2　摄入与索引

#### 2.1 端到端流程
- **级**：基础
- **深**：
  - 整条链路：
    1. 数据源 connector；
    2. 解析；
    3. 清洗、去重；
    4. 切块；
    5. 加 metadata：来源、标题路径、时间、ACL、租户；
    6. embedding；
    7. 同时写入向量索引和 BM25 倒排索引；
    8. 版本管理与增量同步。
  - query 和文档必须用同一个 embedding 模型、同一个版本。换模型就要全量重新 embed，再用双写或蓝绿索引切换。
- **问**：讲一下索引阶段的流程。要换 embedding 模型怎么办？
- **源**：R2 R6

#### 2.2 文档解析
- **级**：进阶
- **深**：
  - PDF 本质上是绘制指令，不是结构化文本。解析要做：版面分析、恢复阅读顺序、识别表格结构、扫描件 OCR。
  - 表格可以转成 Markdown 或 HTML，也可以存「表格摘要 + 原表」。
  - 解析错误是最常见的上游故障来源。
- **问**：PDF 里的表格怎么处理？扫描件怎么办？
- **源**：R7 R6

#### 2.3 切块（Chunking）
- **级**：基础→进阶
- **深**：
  - 几种主要策略：
    - 固定长度加 overlap：OpenAI file search 默认 800 token、overlap 400；
    - 递归切分：按分隔符一级级往下切；
    - 结构感知：按标题、Markdown 结构或代码 AST 切；
    - 语义切分：研究显示相对固定切分没有稳定收益；
    - parent-child：用小块检索，返回它所在的大块。
  - 块太小精确但缺上下文，块太大语义被稀释、还占 token。
- **问**：chunk size 怎么定？semantic chunking 值得做吗？
- **源**：R8 R9 R10

#### 2.4 给 chunk 补上下文
- **级**：前沿，已在落地
- **深**：
  - 问题：切出来的块丢了文档级的上下文，比如块里写「该公司」，但看不出是哪家公司。
  - Contextual Retrieval：用 LLM 为每块生成 50–100 token 的说明前缀，再做 embedding 和 BM25。
    - top-20 检索失败率依次下降：只做 contextual embedding 降 35%，加上 BM25 降 49%，再加 rerank 降 67%。
  - late chunking：先用长上下文模型对整篇文档编码，再按块做 pooling，不用调用 LLM。
- **问**：怎么解决 chunk 丢上下文的问题？late chunking 和 contextual retrieval 有什么区别？
- **源**：R5 R12 R13

#### 2.5 Embedding 模型
- **级**：进阶
- **深**：
  - 结构是 bi-encoder，用对比学习训练（InfoNCE），负样本来自同一批次加上难负样本。
  - 现代模型是多阶段训练：先大规模弱监督预训练，再加 LLM 合成数据，然后做高质量微调，最后合并模型。
  - 向量做 L2 归一化之后，cosine、点积、L2 的排序是等价的，因为 ‖q−x‖² = 2 − 2q·x。
  - Matryoshka：训练时对多个前缀维度同时算 loss，所以向量可以直接截短使用。
  - 选型可以先看 MTEB 榜单，但一定要在自己的数据上评测。
- **问**：embedding 模型是怎么训练的？为什么要归一化？Matryoshka 是什么？
- **源**：R14 R15 R16 R17 R18

#### 2.6 增量更新与删除
- **级**：进阶
- **深**：
  - 用内容 hash 跳过没变化的块。Cursor 用 Merkle tree 比对文件变化。
  - 维护「文档 → 块」的映射，删除和更新时级联处理。
  - upsert 等于先删除再插入。
- **问**：源文档更新或删除之后，索引怎么同步？
- **源**：R11 R44

### M3　向量检索内核（重点）

#### 3.1 为什么需要 ANN
- **级**：基础
- **深**：
  - 精确 kNN 每次查询的代价是 O(N·d)。1000 万条 768 维 float32 向量约 30GB，每次查询都要扫一遍，瓶颈在内存带宽。
  - 高维下 KD-tree 这类空间划分的剪枝会失效，也就是维度灾难。
  - ANN 的思路：少算距离、压缩向量，用小于 1 的召回率换速度。
  - 要分清两种 recall：ANN recall 是相对精确 kNN 而言；检索 recall 是相对人工标注的相关性而言。
- **问**：既然不可能逐个遍历，向量库是怎么快速取出 top-k 的？
- **源**：R19 R21

#### 3.2 IVF（倒排文件索引）
- **级**：基础
- **深**：
  - 建索引：用 k-means 训练 nlist 个质心，每个向量放进离它最近的那个质心的列表。
  - 查询：先和所有质心比距离，只扫描最近的 nprobe 个列表。
  - 代价约为 nlist·d + nprobe·(N/nlist)·d，所以 nlist 取 √N 量级最均衡。
  - 召回损失来自真正的近邻落在了相邻的列表里；调大 nprobe，召回率上升，速度下降。
  - 需要先训练，数据分布漂移后要重新训练。
  - 增删容易，适合磁盘和对象存储，这也是 Pinecone、turbopuffer 选用聚类索引的原因。
- **问**：IVF 的原理是什么？nprobe 调大会怎样？
- **源**：R20 R22 R48

#### 3.3 PQ、OPQ、IVF-PQ 与 ADC
- **级**：进阶
- **深**：
  - PQ（乘积量化）：把向量切成 m 段，每段用 k-means 训练 256 个码字，每段只存 1 字节的码字编号。768 维 float32 原本 3072 字节，m=96 时只要 96 字节，压缩 32 倍。
  - ADC（非对称距离计算）：query 保持原值不量化，先算出一张 m×256 的距离表，每个库向量的距离就是 m 次查表再相加。
  - OPQ：先学一个旋转矩阵，让各段的方差均衡。
  - IVF-PQ：对残差（x 减去所属质心）做 PQ，最后用原始向量精排。
- **问**：PQ 是怎么压缩的，又怎么快速算距离？为什么要用非对称距离？
- **源**：R23 R24 R19

#### 3.4 HNSW（必考）
- **级**：基础→进阶
- **深**：
  - 前身 NSW：在具有 small-world 性质的近邻图上做贪心路由。
  - 分层：每个节点的最高层数 = ⌊−ln(U)·mL⌋，所以层数呈指数衰减。上层稀疏、长边多，作用类似跳表。
  - 查询：先在上层贪心下降，到最底层再用大小为 efSearch 的候选堆做 beam search。
  - 插入：先按 efConstruction 找候选，再用启发式挑选 M 个「方向多样」的邻居。
  - 参数：
    - M：影响内存和召回；
    - efConstruction：影响建图质量和建图时间；
    - efSearch：查询时调节召回和延迟的旋钮，必须大于等于 k。
  - 内存约为 (d·4 + M·2·4) 字节/向量，原始向量必须常驻内存。
  - pgvector 的默认值：m=16、ef_construction=64、ef_search=40。
  - 缺点：内存占用大、建图慢、删除难、带过滤难。
- **问**：HNSW 为什么快？M 和 ef 怎么调？它和 IVF 怎么选？
- **源**：R25 R26 R20 R22

#### 3.5 DiskANN / Vamana（数据超出内存）
- **级**：进阶
- **深**：
  - 单层图，裁剪时保留长边，减少跳数，也就减少了读 SSD 的次数。
  - 内存里只放 PQ 压缩后的向量用于导航，全精度向量和邻接表放在 SSD 上，最后用全精度向量重排。
  - 单机 64GB 内存可以做十亿级检索。
  - 变体：FreshDiskANN 支持增删；Filtered-DiskANN 在建图时就考虑过滤标签。
- **问**：数据量超过内存了怎么办？
- **源**：R27 R28 R29

#### 3.6 ScaNN 与 LSH
- **级**：进阶（LSH 了解即可）
- **深**：
  - ScaNN：分区 → 各向异性量化 → 重排。核心洞见是：做内积检索时，量化误差中与数据点方向平行的那部分更伤结果，所以要重点惩罚这一部分。
  - LSH：让近的点以更高概率落进同一个桶，用多张哈希表换召回率。在主流向量库里很少用作默认索引。
- **问**：ScaNN 和 PQ 有什么不同？LSH 为什么在向量库里少见？
- **源**：R30 R31 R21

#### 3.7 标量量化、二值量化与 rescore
- **级**：进阶
- **深**：
  - int8 标量量化压缩 4 倍；二值量化只保留符号位，压缩 32 倍，距离用 XOR 加 popcount 算 Hamming 距离。
  - 用 oversampling（多取一些候选）加原始向量 rescore 把精度找回来。Hugging Face 实测，int8 加 rescore 能保留约 99% 的效果。
  - RaBitQ 给出了误差的理论上界。
  - Elasticsearch 的默认值（已核实）：9.1 起，384 维及以上的 float 向量默认 `bbq_hnsw`，更低维默认 `int8_hnsw`；9.4 起，在 license 允许时默认 `bbq_disk`。
- **问**：二值量化损失这么大，为什么还能用？rescore 怎么做？
- **源**：R32 R33 R34 R35 R36

#### 3.8 带过滤的检索（高频）
- **级**：进阶
- **深**：
  - pre-filter：先过滤，结果精确，但筛出的子集只能做近似暴力搜索。
  - post-filter：先检索再过滤，可能凑不够 k 条。例如过滤条件只命中 10%、ef_search=40 时，平均只剩 4 条。
  - in-filter：在图遍历时跳过不满足条件的点。选择率很低、或过滤条件和相似度无关时，图会「断开」。
  - 各家的解法：
    - Qdrant：按基数选择策略，并额外为 payload 建边；
    - Weaviate：1.34 起默认用 ACORN（已核实）；
    - pgvector 0.8：`iterative_scan`；
    - Filtered-DiskANN；
    - Pinecone 发表了专门的论文。
- **问**：为什么带 filter 的向量检索难？怎么保证返回 k 条而且结果正确？
- **源**：R22 R37 R38 R39 R40

#### 3.9 更新删除、分片与多租户
- **级**：进阶
- **深**：
  - HNSW 删除：直接删点会破坏图的连通性，通常打 tombstone，积累多了再修复或重建。FAISS 的 HNSW 不支持删除。
  - LSM 式写入：新数据先写入可以暴力扫描的小段，再在后台合并、建索引。
  - 分片：scatter-gather，各分片取 top-k 再合并，尾延迟取决于最慢的分片。
  - 多租户三种做法：每个租户一个 collection；共享索引加租户字段；大租户单独分片。
- **问**：HNSW 怎么删除？千万级文档、上万个租户怎么设计？
- **源**：R41 R42 R43 R44 R45 R46

#### 3.10 真实系统
- **级**：基础
- **深**：
  - FAISS：一个库，不是数据库，支持 Flat、IVF、PQ、HNSW，也支持 GPU。
  - pgvector：HNSW、IVFFlat。
  - Qdrant：HNSW，加上过滤和量化。
  - Weaviate：HNSW 加 ACORN。
  - Milvus：FLAT、IVF 系列、HNSW 系列、DISKANN、SCANN、IVF_RABITQ。
  - Elasticsearch / OpenSearch：基于 Lucene 或 Faiss 的 HNSW。
  - Pinecone：LSM slab 架构，大 slab 用 IVF。
  - turbopuffer：聚类索引，跑在对象存储上。
  - Vertex AI、AlloyDB：ScaNN。
  - Azure Cosmos DB：DiskANN。
- **问**：为什么选这个向量库，而不是直接用 pgvector？
- **源**：R19 R47 R44 R48 R50 R51 R52

### M4　检索质量

#### 4.1 稀疏与稠密检索，BM25
- **级**：基础
- **深**：
  - BM25 由三部分组成：IDF、词频饱和（参数 k1）、文档长度归一化（参数 b）。
  - BM25 擅长精确词、编号和罕见词；稠密检索擅长同义改写。
  - BEIR 显示：BM25 在零样本下很强，稠密模型跨领域泛化较弱。
- **问**：有了向量检索，为什么还要 BM25？
- **源**：R53

#### 4.2 学习型稀疏检索（SPLADE、ELSER）
- **级**：进阶
- **深**：用 MLM head 输出整个词表上的权重，自带词扩展，仍然走倒排索引，结果可解释。
- **问**：SPLADE 和 BM25 有什么区别？
- **源**：R54 R55

#### 4.3 混合检索与融合
- **级**：基础
- **深**：
  - RRF：得分 = Σ 1/(k + 排名)，k 取 60。只看名次，不需要校准两路分数的尺度。
  - 也可以把分数归一化后加权，例如 Weaviate 用 alpha 调节权重。
- **问**：为什么用 RRF，而不是把两路分数直接相加？
- **源**：R56 R57 R58

#### 4.4 重排（Rerank）
- **级**：基础→进阶
- **深**：
  - 两阶段：先高召回地取 50–200 条，再精排。
  - cross-encoder：把 query 和文档拼在一起编码，精度高，但每个候选都要单独算一遍。
  - ColBERT（late interaction）：每个 token 一个向量，对每个 query token 取与文档 token 的最大相似度再求和。文档侧可以预先计算，但存储量大。
- **问**：bi-encoder、cross-encoder、ColBERT 有什么区别？各自成本如何？
- **源**：R59 R60 R61 R15

#### 4.5 查询改写与路由
- **级**：进阶
- **深**：
  - 改写：把多轮对话里的问题改成独立完整的 query。
  - multi-query：一个问题生成多个 query，检索后用 RRF 融合。
  - HyDE：先让 LLM 写一个假设答案，再用它去检索。代价是多一次调用，还可能引入错误信息。
  - 问题分解：把复杂问题拆成子问题。
  - 路由：按意图分到不同的索引或工具。
- **问**：用户的问题很口语化，或者需要多跳推理，怎么办？
- **源**：R62 R63 R64

### M5　生成

#### 5.1 上下文组装与 lost in the middle
- **级**：基础
- **深**：
  - 去重，合并相邻块或扩展到父块，控制 token 预算。
  - 关键证据放在开头或结尾，因为中间的信息最容易被忽略。
  - 每块带上来源、标题和日期。
  - 上下文越长越容易出问题（context rot）。
- **问**：召回了 20 块，怎么放进 prompt？
- **源**：R65 R66

#### 5.2 引用、grounding 与 RAG prompt
- **级**：进阶
- **深**：
  - 给每块编号，要求模型逐句引用，事后再校验引用是否存在、是否真的支持这句话。
  - 检索不到答案时要能拒答。
  - 检索来的内容只当作数据，不能当作指令，否则会被间接注入。
- **问**：怎么让回答带上可靠的引用？检索到的文档里有恶意指令怎么办？
- **源**：R68 R78 R83

### M6　进阶与前沿

#### 6.1 Agentic RAG
- **级**：进阶→前沿
- **深**：
  - 检索变成一个工具，由 LLM 在循环中决定要不要检索、检索什么、什么时候停。
  - 工业实例：
    - Azure 的 agentic retrieval；
    - Anthropic 的 Research 系统；
    - Claude Code 直接用 grep / glob 做搜索，放弃了向量库；
    - Cursor 语义检索加 grep 并用，准确率提升 12.5%。
  - 结论（判断）：把混合检索做成 agent 可以调用的工具。
- **问**：Agentic RAG 和传统 RAG 有什么区别？代码库检索要不要做 embedding？
- **源**：R69 R64 R70 R71 R10 R72

#### 6.2 GraphRAG
- **级**：前沿
- **深**：
  - 流程：抽取实体和关系 → 建图 → 社区划分 → 生成分层摘要。
  - 能回答「整个语料库的主题是什么」这类全局问题。
  - 缺点是索引成本高。LazyGraphRAG 把索引成本降到原来的 0.1%。
  - RAPTOR 是另一种做法：递归聚类，生成摘要树。
- **问**：GraphRAG 能解决普通 RAG 解决不了的什么问题？代价是什么？
- **源**：R73 R74 R75

#### 6.3 多模态 RAG
- **级**：前沿
- **深**：两条路线：
  - 先解析、OCR、给图表写 caption，全部转成文本再检索；
  - 直接对页面截图做视觉 embedding，例如 ColPali。
- **问**：图表很多的 PDF 怎么检索？
- **源**：R76 R7

#### 6.4 2025–26 年的长上下文与 RAG
- **级**：进阶
- **深**：
  - 模型的有效上下文远小于标称长度。
  - 常见组合（判断）：先用 RAG 缩小范围，再用长上下文读整篇文档，配合 prompt caching 降低成本。
- **问**：同 1.2。
- **源**：R4 R66 R67

### M7　评估

#### 7.1 检索指标
- **级**：基础
- **深**：
  - recall@k：对 RAG 最关键，因为模型只看得到 top-k。
  - MRR：第一个相关结果排名的倒数。
  - nDCG：支持分级相关度，按 log 折扣，再除以理想排序下的 DCG。
- **问**：nDCG 怎么算？RAG 主要看哪个指标？
- **源**：R77 R53

#### 7.2 生成指标与评测框架
- **级**：进阶
- **深**：
  - faithfulness：把回答拆成若干条陈述，逐条判断是否被上下文支持。
  - 其他指标：answer relevancy、context precision / recall。
  - 用 LLM 当裁判前，要先和人工标注对齐。
  - 常用框架：RAGAS。
- **问**：怎么检测幻觉？LLM 当裁判可靠吗？
- **源**：R78

#### 7.3 构建评测集
- **级**：进阶
- **深**：
  - 从真实日志中分层抽样，覆盖无答案、多跳、权限敏感等类型。
  - 用 LLM 合成问题，再人工审核。
  - 解析、检索、重排、生成各自单独评估。
  - 建一套回归集放进 CI。
- **问**：没有标注数据，怎么评估 RAG？
- **源**：R6 R78

### M8　生产

#### 8.1 延迟、成本与缓存
- **级**：进阶
- **深**：
  - 生成通常占延迟和成本的大头（判断）。
  - 三层缓存：
    - embedding 按内容 hash 缓存；
    - 语义缓存：必须按租户和权限隔离；
    - prompt caching。
- **问**：RAG 又慢又贵，怎么优化？语义缓存有什么风险？
- **源**：R79 R80 R11

#### 8.2 新鲜度
- **级**：进阶
- **深**：
  - 用 CDC 或 webhook 做增量同步。
  - 写入后立即可见（例如 Pinecone 的 memtable）。
  - 按版本或时间过滤。
- **问**：新文档多久能被检索到？怎么保证？
- **源**：R44 R48

#### 8.3 按权限检索与数据安全（高频，和 Harness [7.4](#74-多用户多角色限制-tools-和-skills) 是同一类问题）
- **级**：进阶
- **深**：
  - 摄入时，把源系统的 ACL 同步到 chunk 的 metadata。
  - 查询时，用经过认证的身份在向量库层做 pre-filter，不能靠 LLM「不要说出来」。
  - 权限关系复杂时，用细粒度授权服务（SpiceDB、OpenFGA）。
  - 权限变更要同步到索引。
  - embedding 本身也是敏感数据：vec2text 能还原 92% 的 32-token 文本。
  - 知识库可能被投毒（PoisonedRAG）。
  - OWASP LLM08:2025「Vector and Embedding Weaknesses」（已核实）。
- **问**：怎么保证用户只检索到自己有权看的文档？为什么 post-filter 不够？
- **源**：R81 R82 R83 R84

#### 8.4 可观测性与失败模式
- **级**：进阶
- **深**：
  - 每个阶段都要 trace：query、改写结果、召回的 id 和分数、重排分数、prompt、回答、引用、用户反馈。
  - 常见失败：
    - 解析丢了表格；
    - 切块把证据切断了；
    - query 和文档的 embedding 版本不一致；
    - 精确词没有命中；
    - 过滤过度；
    - 索引过期；
    - 权限错误；
    - lost in the middle；
    - 文档互相冲突；
    - 引用错误；
    - prompt 注入。
- **问**：线上回答错了，怎么定位是哪一环的问题？
- **源**：R85 R6

### 工业界在用的与偏学术的
- **主流在用**：
  - HNSW 是默认索引；
  - 量化加 rescore 已经是默认配置；
  - 云原生、对象存储场景用聚类索引；
  - DiskANN、ScaNN；
  - 带过滤检索的工程化方案；
  - 混合检索加 RRF 加重排；
  - 给 chunk 补上下文；
  - agentic retrieval；
  - 按权限裁剪结果。
- **偏学术或小众**（判断）：
  - 纯 LSH；
  - Self-RAG / CRAG：思路被吸收了，但工业界用通用 LLM 的 agent loop 来实现；
  - 完整的 GraphRAG：成本高，适合全局性问题；
  - 语义切分：收益不稳定；
  - HyDE、RAPTOR 是可选技巧；
  - ColPali 在视觉文档场景正在升温。

## 来源

### Harness

H1 https://www.langchain.com/blog/the-anatomy-of-an-agent-harness  
H2 https://www.anthropic.com/engineering/harness-design-long-running-apps  
H3 https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents  
H4 https://platform.claude.com/docs/en/managed-agents/overview  
H5 https://code.claude.com/docs/en/agent-sdk/agent-loop  
H6 https://www.anthropic.com/engineering/building-effective-agents  
H7 https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents  
H8 https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents  
H9 https://www.trychroma.com/research/context-rot  
H10 https://arxiv.org/abs/2307.03172  
H11 https://www.langchain.com/blog/context-engineering-for-agents  
H12 https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus  
H13 https://developers.openai.com/api/docs/guides/structured-outputs ；https://developers.openai.com/api/docs/guides/function-calling  
H14 https://www.anthropic.com/engineering/writing-tools-for-agents  
H15 https://blog.modelcontextprotocol.io/posts/2026-07-28/  
H16 https://modelcontextprotocol.io/specification/2026-07-28  
H17 https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization  
H18 https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices  
H19 https://www.anthropic.com/engineering/advanced-tool-use  
H20 https://www.anthropic.com/engineering/code-execution-with-mcp  
H21 https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview  
H22 https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills  
H23 https://agentskills.io ；https://developers.openai.com/codex/skills  
H24 https://code.claude.com/docs/en/agent-sdk/subagents  
H25 https://www.anthropic.com/engineering/multi-agent-research-system  
H26 https://openai.github.io/openai-agents-python/handoffs/  
H27 https://a2a-protocol.org/latest/specification/  
H28 https://code.claude.com/docs/en/hooks  
H29 https://code.claude.com/docs/en/agent-sdk/permissions  
H30 https://openai.github.io/openai-agents-python/guardrails/  
H31 https://www.anthropic.com/engineering/claude-code-sandboxing  
H32 https://code.claude.com/docs/en/sandboxing  
H33 https://www.anthropic.com/engineering/how-we-contain-claude  
H34 https://fly.io/learn/firecracker-vs-gvisor/  
H35 https://learn.chatgpt.com/docs/sandboxing  
H36 https://openai.com/index/the-next-evolution-of-the-agents-sdk/ （OpenAI 原文 403，内容据二手报道）  
H37 https://code.claude.com/docs/en/permissions  
H38 https://claude.com/blog/auto-mode  
H39 https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/  
H40 https://arxiv.org/abs/2503.18813 （CaMeL）  
H41 https://arxiv.org/abs/2506.08837  
H42 https://www.anthropic.com/news/prompt-injection-defenses  
H43 https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/  
H44 https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md  
H45 https://platform.claude.com/docs/en/agents-and-tools/agent-skills/enterprise  
H46 https://code.claude.com/docs/en/skills  
H47 https://www.rfc-editor.org/info/rfc8693/  
H48 https://csrc.nist.gov/pubs/sp/800/162/upd2/final  
H49 https://docs.langchain.com/oss/python/concepts/memory  
H50 https://arxiv.org/pdf/2309.02427 （CoALA）  
H51 https://arxiv.org/abs/2310.08560 （MemGPT）  
H52 https://docs.letta.com/guides/agents/memory-blocks/  
H53 https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool  
H54 https://arxiv.org/abs/2304.03442 （Generative Agents）  
H55 https://arxiv.org/abs/2501.13956 （Zep）  
H56 https://arxiv.org/pdf/2504.19413 （Mem0）  
H57 https://platform.claude.com/docs/en/managed-agents/memory  
H58 https://code.claude.com/docs/en/memory  
H59 https://arxiv.org/pdf/2210.03629 （ReAct）  
H60 https://arxiv.org/abs/2305.04091 （Plan-and-Solve）  
H61 https://arxiv.org/abs/2303.11366 （Reflexion）  
H62 https://docs.langchain.com/oss/python/langgraph/interrupts  
H63 https://temporal.io/blog/of-course-you-can-build-dynamic-ai-agents-with-temporal  
H64 https://www.humanlayer.dev/blog/12-factor-agents  
H65 https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/  
H66 https://openai.com/index/separating-signal-from-noise-coding-evaluations/ （原文 403，未核实）  
H67 https://arxiv.org/abs/2406.12045 （τ-bench）  
H68 https://arxiv.org/abs/2506.07982 （τ²-bench）  

### RAG

R1 https://arxiv.org/abs/2005.11401  
R2 https://arxiv.org/abs/2312.10997  
R3 https://arxiv.org/abs/2312.05934  
R4 https://arxiv.org/abs/2407.16833  
R5 https://www.anthropic.com/engineering/contextual-retrieval  
R6 https://arxiv.org/abs/2401.05856  
R7 https://arxiv.org/abs/2408.09869 （Docling）  
R8 https://platform.openai.com/docs/guides/retrieval  
R9 https://arxiv.org/abs/2410.13070  
R10 https://cursor.com/blog/semsearch  
R11 https://cursor.com/blog/secure-codebase-indexing  
R12 https://arxiv.org/abs/2409.04701 （late chunking）  
R13 https://blog.voyageai.com/2025/07/23/voyage-context-3/  
R14 https://arxiv.org/abs/2004.04906 （DPR）  
R15 https://arxiv.org/abs/2506.05176 （Qwen3 Embedding）  
R16 https://arxiv.org/abs/2205.13147 （Matryoshka）  
R17 https://openai.com/index/new-embedding-models-and-api-updates/  
R18 https://arxiv.org/abs/2210.07316 （MTEB）  
R19 https://arxiv.org/abs/2401.08281 （FAISS）  
R20 https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index  
R21 https://theoryofcomputing.org/articles/v008a014/ （LSH）  
R22 https://github.com/pgvector/pgvector  
R23 https://pubmed.ncbi.nlm.nih.gov/21088323/ （PQ）  
R24 https://openaccess.thecvf.com/content_cvpr_2013/papers/Ge_Optimized_Product_Quantization_2013_CVPR_paper.pdf （OPQ）  
R25 https://publications.hse.ru/pubs/share/folder/x5p6h7thif/128296059.pdf （NSW）  
R26 https://arxiv.org/abs/1603.09320 （HNSW）  
R27 https://proceedings.neurips.cc/paper_files/paper/2019/hash/09853c7fb1d3f8ee67a61b6bf4a7f8e6-Abstract.html （DiskANN）  
R28 https://arxiv.org/abs/2105.09613 （FreshDiskANN）  
R29 https://dl.acm.org/doi/10.1145/3543507.3583552 （Filtered-DiskANN）  
R30 https://arxiv.org/abs/1908.10396 （ScaNN）  
R31 https://docs.cloud.google.com/vertex-ai/docs/vector-search/overview  
R32 https://arxiv.org/abs/2405.12497 （RaBitQ）  
R33 https://huggingface.co/blog/embedding-quantization  
R34 https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/dense-vector  
R35 https://www.elastic.co/search-labs/blog/better-binary-quantization-lucene-elasticsearch  
R36 https://qdrant.tech/documentation/manage-data/quantization/  
R37 https://arxiv.org/abs/2403.04871 （ACORN）  
R38 https://weaviate.io/blog/weaviate-1-34-release ；https://weaviate.io/blog/speed-up-filtered-vector-search  
R39 https://qdrant.tech/articles/vector-search-filtering/  
R40 https://www.pinecone.io/research/accurate-and-efficient-metadata-filtering-in-pinecones-serverless-vector-database/  
R41 https://github.com/nmslib/hnswlib  
R42 https://qdrant.tech/documentation/concepts/optimizer/  
R43 https://www.elastic.co/search-labs/blog/hnsw-graphs-speed-up-merging  
R44 https://www.pinecone.io/learn/slab-architecture/  
R45 https://qdrant.tech/documentation/manage-data/multitenancy/  
R46 https://milvus.io/docs/multi_tenancy.md  
R47 https://milvus.io/docs/index-explained.md  
R48 https://turbopuffer.com/docs/architecture  
R50 https://docs.opensearch.org/latest/mappings/supported-field-types/knn-methods-engines/  
R51 https://devblogs.microsoft.com/cosmosdb/diskann-in-azure-cosmos-db-for-mongodb/  
R52 https://docs.cloud.google.com/alloydb/docs/ai/create-scann-index  
R53 https://arxiv.org/abs/2104.08663 （BEIR）  
R54 https://arxiv.org/abs/2107.05720 （SPLADE）  
R55 https://www.elastic.co/docs/explore-analyze/machine-learning/nlp/ml-nlp-elser  
R56 https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf （RRF）  
R57 https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion  
R58 https://docs.weaviate.io/weaviate/concepts/search/hybrid-search  
R59 https://arxiv.org/abs/1901.04085  
R60 https://arxiv.org/abs/2004.12832 ；https://arxiv.org/abs/2112.01488 （ColBERT / v2）  
R61 Cohere Rerank 4（二手报道，未核实）  
R62 https://arxiv.org/abs/2212.10496 （HyDE）  
R63 https://arxiv.org/abs/2305.14283  
R64 https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-overview  
R65 https://arxiv.org/abs/2307.03172  
R66 https://www.trychroma.com/research/context-rot  
R67 https://arxiv.org/abs/2502.05167 （NoLiMa）  
R68 https://platform.claude.com/docs/en/build-with-claude/citations  
R69 https://arxiv.org/abs/2501.09136  
R70 https://www.anthropic.com/engineering/multi-agent-research-system  
R71 Boris Cherny 关于 Claude Code 使用 agentic search 的公开说明（X 帖子）  
R72 https://arxiv.org/abs/2310.11511 ；https://arxiv.org/abs/2401.15884 （Self-RAG / CRAG）  
R73 https://arxiv.org/abs/2404.16130 （GraphRAG）  
R74 https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/  
R75 https://arxiv.org/abs/2401.18059 （RAPTOR）  
R76 https://arxiv.org/abs/2407.01449 （ColPali）  
R77 https://dl.acm.org/doi/10.1145/582415.582418 （nDCG）  
R78 https://arxiv.org/abs/2309.15217 ；https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/ （RAGAS）  
R79 https://platform.claude.com/docs/en/about-claude/pricing  
R80 https://redis.io/docs/latest/develop/ai/context-engine/langcache/concepts/  
R81 https://learn.microsoft.com/en-us/azure/search/search-document-level-access-overview  
R82 https://www.pinecone.io/learn/rag-access-control/ ；https://authzed.com/docs/spicedb/ops/secure-rag-pipelines  
R83 https://genai.owasp.org/llmrisk/llm08-excessive-agency/ （页面实际标题为 LLM08:2025 Vector and Embedding Weaknesses）  
R84 https://arxiv.org/abs/2310.06816 （vec2text）；https://arxiv.org/abs/2402.07867 （PoisonedRAG）  
R85 https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/  
