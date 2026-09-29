# Harness：学习路线

Harness 指模型之外、把 LLM 变成可工作 agent 的全部部分：agent loop、上下文管理、工具与 MCP、skills、hooks、沙箱、权限、记忆、持久执行、评估与观测。

每个知识点写四项：**级**（基础 / 进阶 / 前沿）、**深**（要掌握到什么深度）、**问**（企业常见问法）、**源**（出处编号，见文末）。「未核实」表示只见于二手报道或搜索摘要，「判断」表示归纳出的结论而不是来源原话。整理于 2026-09-29，产品和规范变化快，引用前请以出处的最新版本为准。

## M1　Harness 本体与 agent loop

**1.1 Harness 的定义与分层**
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

**1.2 Agent loop 与停止条件**
- **级**：基础
- **深**：
  - 能手写这个循环：messages 加 tools 发给模型 → 模型返回 tool_use → harness 执行 → 把 tool_result 追加回去再调用模型 → 直到模型不再调工具（end_turn）为止。
  - 其他终止方式：`max_turns`、预算上限、`max_tokens`、refusal。
  - 被拒绝的工具调用也要以 tool_result 的形式回给模型。
  - 只读工具可以并行执行，有副作用的工具要串行。
- **问**：写出 loop 的伪代码。怎么防止死循环和成本失控？一次返回多个 tool call 时怎么执行？
- **源**：H5 H6

**1.3 Workflow 与 agent**
- **级**：基础
- **深**：
  - workflow 是用预先写好的代码路径来编排 LLM；agent 是由 LLM 动态决定流程和用哪些工具。
  - 五种常见模式：prompt chaining、routing、parallelization、orchestrator-workers、evaluator-optimizer。
  - 先直接调 API，确实有收益时再加复杂度。
- **问**：什么样的任务不该做成 agent？
- **源**：H6

**1.4 长时程 harness**
- **级**：进阶
- **深**：
  - initializer agent 先建好三样东西：feature 列表（JSON，初始全部标为 failing）、进度文件、git 提交。
  - 之后每轮只做一个 feature，并做端到端验证。
  - planner、generator、evaluator 分成三个角色，用来缓解模型评自己时的偏差。
  - 在部分模型上，清空上下文再加结构化交接，效果比 compaction 更好。
- **问**：让 agent 连续开发几个小时，状态怎么交接？怎么判定「完成」？
- **源**：H2 H7

## M2　提示词工程、上下文工程与 Harness

**2.1 三者的关系**
- **级**：基础
- **深**：
  - prompt engineering：把指令本身写好。
  - context engineering：每一步都要决定哪些 token 进入窗口，包括指令、工具定义、历史、检索结果和记忆。它是 prompt engineering 在多轮 agent 场景下的延伸。
  - harness：把 context engineering 落地的执行系统，同时还负责行动、权限、状态和观测。
- **问**：原题 Q2。为什么 context engineering 不等于「写更长的 prompt」？
- **源**：H8 H11

**2.2 Context rot 与 attention budget**
- **级**：基础→进阶
- **深**：
  - 输入越长性能越差，而且离窗口上限还很远时就开始下降。Chroma 测的 18 个模型全部如此，下降程度还受干扰项、needle 与问题相似度的影响。
  - 位置效应：lost in the middle，中间的信息最容易被忽略。
  - attention budget：token 之间是 n² 的两两关系，上下文越长，注意力摊得越薄。
- **问**：模型都有 1M 上下文了，还需要管理上下文吗？
- **源**：H8 H9 H10

**2.3 管理上下文的手段**
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

## M3　工具与 MCP

**3.1 Function calling 与结构化输出**
- **级**：基础
- **深**：
  - 工具由名称、描述和 JSON Schema 组成。模型只「提出」调用，真正执行的是 harness。
  - OpenAI 的 strict 模式要求 `additionalProperties:false`，并且所有字段都是 required。
  - schema 合法不等于业务合法，harness 仍要校验参数和权限。
- **问**：模型给出非法参数，或者编出一个不存在的工具名，harness 怎么处理？
- **源**：H13

**3.2 工具设计（ACI，agent-computer interface）**
- **级**：进阶
- **深**：
  - 工具少而精，按服务做 namespacing。
  - 返回高信号、可读的标识，而不是一长串内部 ID。
  - 提供 `response_format`（concise / detailed），支持分页。
  - 错误信息要让模型知道下一步怎么做。
  - 用防呆设计防止误用，并用 eval 反复迭代工具描述。
- **问**：给 agent 设计一个 `search_logs` 工具，参数和返回值怎么定？
- **源**：H6 H14

**3.3 MCP 架构与传输**
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

**3.4 MCP 授权**
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

**3.5 工具多了怎么选**
- **级**：进阶／前沿
- **深**：
  - 工具定义本身就占上下文，工具一多，选择准确率也会下降。
  - 对策：
    - tool search：工具定义延迟加载；
    - programmatic tool calling：让模型写代码在沙箱里调用工具，只把过滤后的结果带回上下文；
    - 按角色裁剪工具集。
- **问**：接入 300 个工具后准确率下降、token 暴涨，怎么改？
- **源**：H5 H19 H20

## M4　Skills、Subagents 与多 agent

**4.1 Agent Skills**
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

**4.2 Subagents**
- **级**：进阶
- **深**：
  - 子 agent 有自己独立的上下文，只拿到父 agent 传来的 prompt 字符串，最后一条消息作为 tool result 返回给父 agent。
  - 可以单独限定它能用的 tools、model、权限模式。
  - 要设深度、并发和预算的上限。
- **问**：subagent 解决什么问题？什么时候用了反而更差？
- **源**：H24

**4.3 Orchestrator-worker、handoff、agent-as-tool、A2A**
- **级**：进阶
- **深**：
  - Anthropic 的 Research 系统：lead agent 并行派出 3–5 个 subagent，效果比单个 Opus 4 高 90.2%，但消耗约为普通 chat 的 15 倍 token；token 用量能解释 BrowseComp 上 80% 的得分差异。
  - OpenAI Agents SDK：
    - handoff 以 `transfer_to_<agent>` 工具的形式出现，默认把全部历史交给下一个 agent，可以用 `input_filter` 裁剪；
    - `as_tool()` 不转移控制权，只是把另一个 agent 当工具调用。
  - 跨组织的 agent 互通用 A2A 协议，用 Agent Card 描述能力。
- **问**：handoff 和 agent-as-tool 有什么区别？多 agent 值不值这份成本？
- **源**：H25 H26 H27

## M5　Hooks 与生命周期

**5.1 Hooks**
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

## M6　沙箱与隔离

**6.1 概念与动机**
- **级**：基础
- **深**：
  - 沙箱是由操作系统或虚拟化强制执行的边界，限制命令及其子进程能读写哪些路径、能访问哪些网络、能用哪些系统调用和资源。
  - 为什么需要：
    - 假定模型会犯错、会被注入，用确定性的边界限制出事后的影响范围；
    - 减少审批疲劳：Anthropic 内部统计，权限提示因此减少了 84%。
  - 文件隔离和网络隔离缺一不可：没有网络隔离，SSH key 可能被外泄；没有文件隔离，系统配置可能被改掉。
- **问**：原题 Q4。只做文件隔离行不行？
- **源**：H31 H32

**6.2 隔离技术谱系**
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

**6.3 网络出口与凭据隔离**
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

## M7　安全与访问控制

**7.1 权限模式与审批**
- **级**：基础
- **深**：
  - 判定顺序：hooks → deny → ask → 权限模式 → allow → 回调。
  - deny 在任何模式下都生效；只写工具名的 deny 会把这个工具的定义直接从请求里移除。
  - 配置分层，最高是 managed 层；任何一层的 deny 都不能被其他层放行。
  - 权限模式从严到宽：default、acceptEdits、plan、auto（由分类器代为审批）、bypass。
  - Codex 把两个维度分开：sandbox mode 管「能做什么」，approval policy 管「什么时候要问」。
- **问**：原题 Q5。怎样避免审批疲劳，又不至于放任？
- **源**：H29 H35 H37 H38

**7.2 Prompt injection**
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

**7.3 最小权限、秘钥与审计**
- **级**：基础
- **深**：
  - 工具、路径、域名一律用白名单。
  - 秘钥不进上下文、不进沙箱：清理环境变量、打码、由代理注入。
  - 审计要记下：谁、代表谁、调了什么、用什么参数、结果如何、由谁放行（规则、hook、人还是分类器）。
  - 可以用 OTel GenAI spans 表示，但这套约定目前还是 Development 状态。
- **问**：agent 要用第三方 API key，怎么做到模型看不到、也泄露不出去？
- **源**：H32 H44

**7.4 多用户多角色：限制 tools 和 skills**
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

## M8　记忆

**8.1 短期记忆**
- **级**：基础
- **深**：
  - 当前线程的消息历史和工作状态，CoALA 称为 working memory。
  - 由 checkpointer 持久化，进程崩溃后可以恢复。
  - 同样会受 context rot 影响，需要压缩。
- **问**：短期记忆就等于 context window 吗？
- **源**：H49 H50

**8.2 长期记忆的类型**
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

**8.3 存储、写入、检索、遗忘与安全**
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

## M9　规划、持久执行、人工介入、错误恢复

**9.1 ReAct、plan-and-execute、reflection**
- **级**：基础
- **深**：
  - ReAct：推理和行动 / 观察交替进行。
  - plan-and-execute：先出计划再执行，便于审批和隔离注入；缺点是计划僵化，需要重新规划。
  - Reflexion：把失败的反馈写成文字，存进 episodic memory。
  - 模型原生的推理能力变强之后，显式的 planner 组件可能变得多余。
- **问**：ReAct 和 plan-and-execute 各适合什么场景？
- **源**：H2 H59 H60 H61

**9.2 持久执行与人工介入（HITL）**
- **级**：进阶
- **深**：
  - LangGraph：checkpointer 配合 `thread_id` 保存状态；`interrupt()` 暂停等人工输入，`Command(resume=...)` 继续。
  - Temporal：workflow 部分靠确定性重放恢复，I/O 放在 activity 里。
  - 有副作用的操作带幂等键，防止重试时重复执行。
  - Anthropic 的工程实践：从出错点恢复；用 rainbow deployment 避免部署打断正在运行的 agent。
- **问**：agent 执行到一半崩溃了，怎么恢复，又不重复下单？
- **源**：H5 H25 H62 H63

**9.3 错误恢复**
- **级**：进阶
- **深**：
  - 工具出错时，以 `is_error` 的 tool_result 回给模型，让它自己纠正。
  - 区分可重试和不可重试的错误；用退避和熔断。
  - 设轮次和预算上限。
  - 用测试、lint 这类外部信号验证结果。
  - 控制流握在自己手里，保证随时能中断、序列化和恢复。
- **问**：工具连续超时，agent 应该怎么办？
- **源**：H5 H53 H64

## M10　评估与可观测性

**10.1 Agent evals**
- **级**：进阶
- **深**：
  - 基本概念：task、trial、grader、transcript、outcome。
  - grader 分三类：代码判分、模型判分、人工判分。
  - pass@k 看能力，指 k 次里至少成功一次；pass^k 看可靠性，指 k 次全部成功。
  - 区分能力评测和回归评测。
  - 评的是 model 加 harness 的整体，优先检查环境的最终状态。
- **问**：给一个客服 agent 设计 eval。为什么要看 pass^k？
- **源**：H3

**10.2 基准及其局限**
- **级**：进阶
- **深**：
  - τ-bench：按对话结束时的数据库状态判分，并提出了 pass^k。τ²-bench 进一步让用户也能操作环境（dual-control）。
  - SWE-bench Verified：OpenAI 以测试有缺陷、数据污染为由，已经不再报告这个基准的成绩。
  - SWE-bench Pro 的审计问题（未核实，原文打不开）。
  - 共同的局限：数据污染、测试缺陷、harness 差异、结果方差。
- **问**：某个模型 SWE-bench 分数很高，能说明它在你的业务里一定好用吗？
- **源**：H65 H66 H67 H68

**10.3 Tracing、成本与延迟**
- **级**：基础
- **深**：
  - trace 是一棵 span 树：agent → 模型调用 → 工具调用，可以按 OTel GenAI 约定输出。
  - 成本量级：单 agent 约是普通 chat 的 4 倍 token，多 agent 约 15 倍。
  - 降本降延迟的手段：prompt caching、子任务用小模型、调低推理强度、并行调用工具。
- **问**：线上 agent 变慢变贵了，怎么定位？
- **源**：H5 H25 H44

## 术语尚未统一（面试时可以主动点明）
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

## 来源

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
