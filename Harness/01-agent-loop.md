# 手写一个 agent loop：最少需要哪些东西？

对应路线图：[Harness 1.2 Agent loop 与停止条件](../ROADMAP.md#12-agent-loop-与停止条件)，部分涉及 [9.3 错误恢复](../ROADMAP.md#93-错误恢复)。

完整代码：[code/01-agent-loop/agent.py](code/01-agent-loop/agent.py)（Python，Anthropic Messages API，不用任何 agent 框架）。

运行方法：key 放在仓库根目录的 `.env` 里（照 [.env.example](../.env.example) 复制一份，`.env` 不会被提交），运行时只把它加载进当前这条命令的环境：

```bash
cd Harness/code/01-agent-loop
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
(set -a && source ../../../.env && .venv/bin/python agent.py "scores.csv 里平均分是多少？" --workdir workspace --transcript run.transcript.json)
```

外面的括号让命令在子 shell 里执行，key 不会留在当前终端的环境变量里。

## 问题

都说 Agent = Model + Harness，那么 harness 里最核心的那一圈循环到底长什么样？如果不用 LangGraph、不用 SDK 自带的 tool runner，自己写一个能读文件、能跑代码的 agent，最少要写哪些东西？哪些地方不写就会出问题？

## 循环本身

模型并不会自己「执行」工具。它只是在回复里说「我想调用某个工具，参数是这些」，真正执行的是 harness。一轮的过程是：

1. 把 `system`、`tools`（工具定义）、`messages`（完整历史）发给模型。
2. 模型返回。如果 `stop_reason` 是 `tool_use`，回复里会有一个或多个 `tool_use` 块，每块带 `id`、`name`、`input`。
3. harness 执行这些工具，把结果包成 `tool_result` 块（用 `tool_use_id` 对上号），作为一条 **user** 消息追加回去。
4. 回到第 1 步，直到模型不再调用工具（`end_turn`），或者被 harness 叫停。

API 是无状态的，每一轮都要把完整历史重新发一遍。这意味着轮次越多，每次请求的 input token 越大，这是后面上下文工程要解决的问题。

代码里的核心部分只有这么多：

```python
for turn in range(1, max_turns + 1):
    response = client.messages.create(
        model=MODEL, max_tokens=16_000, system=system, tools=TOOLS, messages=messages, ...
    )
    used_tokens += response.usage.input_tokens + response.usage.output_tokens
    messages.append({"role": "assistant", "content": response.content})

    if response.stop_reason != "tool_use":
        break                      # end_turn、max_tokens、refusal……都在这里停
    if used_tokens >= token_budget:
        break                      # 预算上限

    tool_uses = [b for b in response.content if b.type == "tool_use"]
    messages.append({"role": "user", "content": run_tools(tool_uses, workdir, auto_approve)})
```

几个容易忽略的细节：

- **assistant 消息要整块追加 `response.content`**，而不是只取文本。里面除了 `tool_use` 还有 `thinking` 块，同一个模型续写时要原样带回去。
- **tool_result 要紧跟在对应的 tool_use 之后**，中间不能插别的消息；同一条 user 消息里，`tool_result` 块必须排在任何文本之前，否则 API 返回 400。（官方文档 Handle tool calls，2026-10-16 查证）

## 停止条件

只靠「模型不再调工具」来停是不够的，harness 得自己兜底。我的实现里有这几种停法：

| 停止原因 | 谁决定 | 处理 |
|---|---|---|
| `end_turn` | 模型 | 正常结束，最后一条 assistant 消息的文本就是答案 |
| `max_turns` | harness | 防止死循环：模型反复调用工具却始终不收尾 |
| `token_budget` | harness | 累计 input + output token 超过上限就停，防止成本失控 |
| `max_tokens` | API | 单次输出被截断。如果最后一块是不完整的 `tool_use`，官方建议调大 `max_tokens` 重试；我目前只是停下来 |
| `refusal` | 模型 / 安全分类器 | 拒答，`stop_details.category` 给出类别 |
| `model_context_window_exceeded` | API | 上下文满了 |

（stop_reason 的取值见官方文档 Handling stop reasons，2026-10-16 查证。）

两种 harness 叫停的时机不一样（实验 5 跑出来才发现我原先写错了）：

- **`max_turns`**：检查放在循环条件上，最后一轮的工具**已经执行**、结果也追加进了历史，只是没有下一轮让模型去看。工具白跑了，用户也拿不到答案。
- **`token_budget`**：检查放在执行工具之前，所以最后一条 assistant 消息里的 `tool_use` 没有对应的 `tool_result`。如果以后想「续跑」，要先给这些调用补上结果，否则下一次请求会被 API 拒绝。

## 工具出错怎么办：以 is_error 回传

工具出错时，不应该让整个 loop 抛异常退出，而应该把错误写成 `tool_result`，加上 `is_error: true` 交给模型，让它自己决定下一步。代码里所有失败都走同一条路：

```python
try:
    ...
    result["content"] = content
except ToolError as e:
    result["content"] = str(e)
    result["is_error"] = True
```

我把这些情况都归到了 `ToolError`：

- 路径跑出工作目录；
- 文件不存在、不是 UTF-8；
- 脚本非零退出、超时；
- 模型编了一个不存在的工具名；
- 缺参数。即使 schema 声明了 required，harness 还是要自己再校验一次；
- **用户拒绝执行**。被拒绝的调用同样要回一个 `tool_result`，不能直接丢掉。

错误信息要写给模型看，说清楚下一步可以怎么做。例如文件不存在时，提示它可以用 `run_python` 列目录，而不是只写一句 `failed`。官方文档也建议这样写，并提到参数无效时，模型通常会修正后重试 2–3 次再放弃。（Handle tool calls，2026-10-16 查证）

## 一次返回多个工具调用

模型一次可能返回好几个 `tool_use` 块。API 不规定执行顺序，由 harness 决定：

- `read_file` 是只读的，用线程池并发执行；
- `run_python` 有副作用，按原顺序串行执行；
- 不管怎么执行，**所有结果都按原顺序放进同一条 user 消息**。官方文档专门提醒：每个结果单独发一条 user 消息，会「教会」模型不再并行调用。（Parallel tool use，2026-10-16 查证）

## 我注意到的一个漏洞

`read_file` 做了路径检查，不允许读工作目录以外的文件。但 `run_python` 可以执行任意代码，`open('/etc/passwd')` 一行就绕过去了。

实验 3b 里，模型被 `read_file` 拒绝后**没有**去用 `run_python` 绕，而是说「这会绕过当前的限制，需要你明确同意」，停下来问人。但这只是一次运行里模型自己的选择，换个任务、换个模型、或者被注入了指令，就不一定了。harness 不能把安全寄托在模型「愿意守规矩」上。

所以「在某个工具里加检查」不是真正的权限边界。权限要落在执行层：沙箱限制进程能读写什么，或者在调用前由确定性的规则拦截。这正是路线图第 5 阶段（[hooks](../ROADMAP.md#51-hooks)、[沙箱](../ROADMAP.md#61-概念与动机)、[权限](../ROADMAP.md#71-权限模式与审批)）要解决的问题。在那之前，`run_python` 默认每次都要人工确认，`--yes` 才跳过。

## 不调用模型的测试

2026-10-16，在本机（Python 3.13.5，`anthropic` 1.15.0）上：

- 工具层：直接构造 `tool_use` 块调用 `run_tools`。正常读取、路径越界、文件不存在、脚本报错、未知工具名、缺参数、脚本超时（30 秒）、用户拒绝，都返回了预期的 `is_error` 结果；结果顺序与调用顺序一致。
- 控制流：用一个假的 client 按剧本返回消息。正常结束、`max_turns`、`token_budget`、`max_tokens` 四种停止方式都按预期退出；`--transcript` 写出的 JSON 可以正常解析。

## 实验记录

2026-10-16，模型 `claude-haiku-5-5`，effort `medium`，`--yes` 自动批准。示例数据在 [code/01-agent-loop/workspace/](code/01-agent-loop/workspace/)。**每个实验只跑了一次**，模型行为有随机性，下面是这一次看到的现象，不是规律。

| # | 任务 | 轮数 | input / output token | 结果 |
|---|---|---|---|---|
| 1 | scores.csv 里平均分是多少？谁最低？ | 2 | 1422 / 136 | 正确：78.75，dave 68 分 |
| 2 | 对比 spring.md 和 fall.md，哪些课换了时间？ | 2 | 1581 / 271 | 正确，还区分了「换时间」和「新开 / 停开」 |
| 3a | 读 notes.txt（不存在） | 3 | 2366 / 260 | 照着错误提示列目录，如实说没有这个文件 |
| 3b | 读 ../agent.py（工作目录外） | 2 | 1445 / 393 | 没有绕过限制，停下来请求同意 |
| 4a | 用 Python 算 scores.csv 的标准差，**批准**执行 | 3 | 2526 / 369 | 正确：样本 9.43，总体 8.17 |
| 4b | 同一任务，**拒绝**执行 | 3 | 前 2 轮 1491 / 264，第 3 轮未记录 | 没有重试，列出三种做法问我选哪个 |
| 5 | 列文件、逐个读、算标准差，`--max-turns 2` | 2 | 1650 / 350 | 被截停，没有答案 |

按官方定价（Haiku 5.5，提示不超过 10 万 token 时，输入 $0.10、输出 $0.50 每百万 token，2026-10-16 查证），已记录的部分合计 12481 / 2043 token，约 **$0.0023**（4b 第 3 轮的 token 数没有记下来，见实验 4）。

实验 4 由我在终端里亲手批准或拒绝；其余实验用 `--yes` 自动批准。

### 1. 基本任务

- 第 1 轮直接调用 `read_file`，没有任何文字说明，也没有 `thinking` 块；第 2 轮有一个 `thinking` 块，但文本是空的，只有签名。Haiku 5.5 默认不返回思考内容，但思考的 token 照样计入 output。
- 平均值是模型自己算的，没有调 `run_python`。
- **每轮 input 从 671 涨到 751**，多出来的 80 是上一轮的 `tool_use` 加 `tool_result`。

671 这个起点比我想的大得多，任务本身只有一句话。用 token 计数接口拆开看：

| 部分 | token |
|---|---|
| 用户消息 | 27 |
| 我写的 system prompt | 93 |
| 工具相关（两个工具定义 + API 自动加的工具系统提示） | 551 |

官方定价页写明，Haiku 5.5 只要带了工具，就会自动多出 286 token 的工具系统提示。所以两个工具定义本身约 265 token。**工具定义每轮都要重发**，这是路线图 [3.5 工具多了怎么选](../ROADMAP.md#35-工具多了怎么选) 里「工具定义本身就占上下文」的直观体现。

### 2. 并行调用

- 模型在同一轮发出了两个 `read_file`。
- 日志里 `fall.md` 先读完、`spring.md` 后读完，说明线程池确实是并发执行的；但 transcript 里两个 `tool_result` 仍按调用顺序排在同一条 user 消息里。

### 3. 出错后自我纠正

- **3a**：收到「文件不存在，可以用 run_python 列目录」的错误后，模型下一轮正好用 `os.walk` 列了目录，确认没有这个文件后如实回答，并问我要不要读别的文件。错误信息里的提示被直接采纳了。
- **3b**：见上面「我注意到的一个漏洞」一节。

### 4. 拒绝执行

同一个任务跑了两次，模型都是先 `read_file` 看数据，再请求 `run_python`，两次生成的代码几乎一样。

- **4a 批准**：执行成功，模型拿到结果后给出样本和总体两种标准差，并说明一般用样本标准差。人工确认这条路径在真实模型上是通的。
- **4b 拒绝**：`tool_result` 带着 `is_error` 和「用户拒绝了，问他想怎么做，不要重试」回给模型。模型没有换个方式偷偷再跑，而是说明自己已经读到的数据，然后给出三个选项：它心算、我自己跑代码、换别的方式，让我选。

和 3a 一样，模型几乎是**照着错误信息里写的下一步去做**。这说明错误信息不只是报错，它实际上就是在给模型下指令，是 prompt 的一部分。反过来也意味着：这里看到的「模型被拒绝后的反应」，很大程度上是我写的那句提示决定的，不完全是模型自己的倾向。

一个记录上的漏洞：4b 运行时终端被关掉了，第 3 轮的 token 数没看到。transcript 只存了 messages，没有存每轮的 usage，所以事后也补不回来。以后 transcript 应该把每轮的 `usage` 和 `stop_reason` 一起记下来。

### 5. 触发 max_turns

- 模型第 1 轮用 `run_python` 列目录，第 2 轮一次性并行读了 3 个文件，然后被截停。
- 第 2 轮的 3 个 `read_file` **已经执行**，结果写进了历史，但模型没有机会看到。终端上最终答案是空的。

这暴露了两个问题：一是我原先对停止时机的描述写错了（已在「停止条件」一节改正）；二是 `max_turns` 的处理方式本身不好。更合理的做法可能是：到达上限前的最后一轮不再执行工具，而是让模型基于已有信息给出一个阶段性答复。

## 开放问题

- 预算现在按 token 数算。按美元算需要按模型价格换算，而且有 prompt cache 时，缓存命中部分的价格不同，怎么算才准？
- `max_tokens` 截断了一个 `tool_use` 时，是自动调大重试，还是交给上层决定？
- 输入 token 每轮都在涨。什么时候该开始清理旧的工具结果？这是第 3 阶段的内容。
- 达到 `max_turns` 时，是直接停、最后一轮禁用工具让模型总结，还是问用户要不要继续？Claude Code 这类真实 harness 是怎么做的？
- 如果错误信息只写 `declined`、不给下一步建议，模型被拒绝后会怎么做？这能把「模型自己的倾向」和「我的提示词的作用」分开。
- 实验都只跑了一次。并行调用、按错误提示纠正、拒绝绕过限制，这些行为有多稳定？要回答这个问题，需要每个实验重复多次，这就是路线图 [10.1](../ROADMAP.md#101-agent-evals) 里 pass@k 和 pass^k 要量的东西。

## 参考

- Anthropic, Handle tool calls：https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls （2026-10-16 查证）
- Anthropic, Parallel tool use：https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use （2026-10-16 查证）
- Anthropic, Handling stop reasons：https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons （2026-10-16 查证）
- Anthropic, Pricing：https://platform.claude.com/docs/en/about-claude/pricing （Haiku 5.5 价格与工具系统提示 token 数，2026-10-16 查证）
- 路线图来源 [H5](../ROADMAP.md#harness-1)（Agent SDK 的 agent loop）、[H6](../ROADMAP.md#harness-1)（Building effective agents）
