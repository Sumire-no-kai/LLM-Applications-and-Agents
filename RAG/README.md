# RAG：学习路线

RAG（检索增强生成）让模型基于外部资料回答：从文档解析、切块、embedding 到向量检索内核、混合检索与重排，再到生成、评估和生产中的权限与新鲜度。

每个知识点写四项：**级**（基础 / 进阶 / 前沿）、**深**（要掌握到什么深度）、**问**（企业常见问法）、**源**（出处编号，见文末）。「未核实」表示只见于二手报道或搜索摘要，「判断」表示归纳出的结论而不是来源原话。整理于 2026-09-29，产品和规范变化快，引用前请以出处的最新版本为准。

## M1　RAG 的定位

### 1.1 RAG 是什么，解决什么问题
- **级**：基础
- **深**：
  - 流程是 retrieve → augment → generate，把参数记忆（模型本身学到的）和非参数记忆（外部资料）结合起来。
  - 原始论文（Lewis 2020）会联合训练 retriever 和 generator；今天工程上说的 RAG，一般只是把检索结果拼进 prompt。
  - 它解决的问题：知识截止日期、私有数据、减少幻觉（不能消除）、回答可引用可溯源、知识可以按时效和权限更新而不用重新训练。
  - 演进路线：Naive → Advanced → Modular。
- **问**：RAG 解决什么问题？有了 RAG 为什么还会幻觉？
- **源**：R1 R2 R6

### 1.2 RAG、微调与长上下文怎么选
- **级**：进阶
- **深**：
  - 微调适合改行为、格式和风格，拿来注入新事实效果差。在新知识任务上，RAG 明显胜过微调。
  - 长上下文在资源充足时平均效果更好，但成本高。Self-Route 让模型自己判断走 RAG 还是长上下文，成本降了 39–65%。
  - Anthropic 的建议：知识库小于 20 万 token 时，直接整份放进 prompt。
  - 决策维度：数据量、更新频率、权限要求、是否需要引用、延迟和成本。
- **问**：什么时候该选微调？模型都有 1M 上下文了，还需要 RAG 吗？
- **源**：R3 R4 R5

## M2　摄入与索引

### 2.1 端到端流程
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

### 2.2 文档解析
- **级**：进阶
- **深**：
  - PDF 本质上是绘制指令，不是结构化文本。解析要做：版面分析、恢复阅读顺序、识别表格结构、扫描件 OCR。
  - 表格可以转成 Markdown 或 HTML，也可以存「表格摘要 + 原表」。
  - 解析错误是最常见的上游故障来源。
- **问**：PDF 里的表格怎么处理？扫描件怎么办？
- **源**：R7 R6

### 2.3 切块（Chunking）
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

### 2.4 给 chunk 补上下文
- **级**：前沿，已在落地
- **深**：
  - 问题：切出来的块丢了文档级的上下文，比如块里写「该公司」，但看不出是哪家公司。
  - Contextual Retrieval：用 LLM 为每块生成 50–100 token 的说明前缀，再做 embedding 和 BM25。
    - top-20 检索失败率依次下降：只做 contextual embedding 降 35%，加上 BM25 降 49%，再加 rerank 降 67%。
  - late chunking：先用长上下文模型对整篇文档编码，再按块做 pooling，不用调用 LLM。
- **问**：怎么解决 chunk 丢上下文的问题？late chunking 和 contextual retrieval 有什么区别？
- **源**：R5 R12 R13

### 2.5 Embedding 模型
- **级**：进阶
- **深**：
  - 结构是 bi-encoder，用对比学习训练（InfoNCE），负样本来自同一批次加上难负样本。
  - 现代模型是多阶段训练：先大规模弱监督预训练，再加 LLM 合成数据，然后做高质量微调，最后合并模型。
  - 向量做 L2 归一化之后，cosine、点积、L2 的排序是等价的，因为 ‖q−x‖² = 2 − 2q·x。
  - Matryoshka：训练时对多个前缀维度同时算 loss，所以向量可以直接截短使用。
  - 选型可以先看 MTEB 榜单，但一定要在自己的数据上评测。
- **问**：embedding 模型是怎么训练的？为什么要归一化？Matryoshka 是什么？
- **源**：R14 R15 R16 R17 R18

### 2.6 增量更新与删除
- **级**：进阶
- **深**：
  - 用内容 hash 跳过没变化的块。Cursor 用 Merkle tree 比对文件变化。
  - 维护「文档 → 块」的映射，删除和更新时级联处理。
  - upsert 等于先删除再插入。
- **问**：源文档更新或删除之后，索引怎么同步？
- **源**：R11 R44

## M3　向量检索内核（重点，对应面试题 10）

### 3.1 为什么需要 ANN
- **级**：基础
- **深**：
  - 精确 kNN 每次查询的代价是 O(N·d)。1000 万条 768 维 float32 向量约 30GB，每次查询都要扫一遍，瓶颈在内存带宽。
  - 高维下 KD-tree 这类空间划分的剪枝会失效，也就是维度灾难。
  - ANN 的思路：少算距离、压缩向量，用小于 1 的召回率换速度。
  - 要分清两种 recall：ANN recall 是相对精确 kNN 而言；检索 recall 是相对人工标注的相关性而言。
- **问**：既然不可能逐个遍历，向量库是怎么快速取出 top-k 的？
- **源**：R19 R21

### 3.2 IVF（倒排文件索引）
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

### 3.3 PQ、OPQ、IVF-PQ 与 ADC
- **级**：进阶
- **深**：
  - PQ（乘积量化）：把向量切成 m 段，每段用 k-means 训练 256 个码字，每段只存 1 字节的码字编号。768 维 float32 原本 3072 字节，m=96 时只要 96 字节，压缩 32 倍。
  - ADC（非对称距离计算）：query 保持原值不量化，先算出一张 m×256 的距离表，每个库向量的距离就是 m 次查表再相加。
  - OPQ：先学一个旋转矩阵，让各段的方差均衡。
  - IVF-PQ：对残差（x 减去所属质心）做 PQ，最后用原始向量精排。
- **问**：PQ 是怎么压缩的，又怎么快速算距离？为什么要用非对称距离？
- **源**：R23 R24 R19

### 3.4 HNSW（必考）
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

### 3.5 DiskANN / Vamana（数据超出内存）
- **级**：进阶
- **深**：
  - 单层图，裁剪时保留长边，减少跳数，也就减少了读 SSD 的次数。
  - 内存里只放 PQ 压缩后的向量用于导航，全精度向量和邻接表放在 SSD 上，最后用全精度向量重排。
  - 单机 64GB 内存可以做十亿级检索。
  - 变体：FreshDiskANN 支持增删；Filtered-DiskANN 在建图时就考虑过滤标签。
- **问**：数据量超过内存了怎么办？
- **源**：R27 R28 R29

### 3.6 ScaNN 与 LSH
- **级**：进阶（LSH 了解即可）
- **深**：
  - ScaNN：分区 → 各向异性量化 → 重排。核心洞见是：做内积检索时，量化误差中与数据点方向平行的那部分更伤结果，所以要重点惩罚这一部分。
  - LSH：让近的点以更高概率落进同一个桶，用多张哈希表换召回率。在主流向量库里很少用作默认索引。
- **问**：ScaNN 和 PQ 有什么不同？LSH 为什么在向量库里少见？
- **源**：R30 R31 R21

### 3.7 标量量化、二值量化与 rescore
- **级**：进阶
- **深**：
  - int8 标量量化压缩 4 倍；二值量化只保留符号位，压缩 32 倍，距离用 XOR 加 popcount 算 Hamming 距离。
  - 用 oversampling（多取一些候选）加原始向量 rescore 把精度找回来。Hugging Face 实测，int8 加 rescore 能保留约 99% 的效果。
  - RaBitQ 给出了误差的理论上界。
  - Elasticsearch 的默认值（已核实）：9.1 起，384 维及以上的 float 向量默认 `bbq_hnsw`，更低维默认 `int8_hnsw`；9.4 起，在 license 允许时默认 `bbq_disk`。
- **问**：二值量化损失这么大，为什么还能用？rescore 怎么做？
- **源**：R32 R33 R34 R35 R36

### 3.8 带过滤的检索（高频）
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

### 3.9 更新删除、分片与多租户
- **级**：进阶
- **深**：
  - HNSW 删除：直接删点会破坏图的连通性，通常打 tombstone，积累多了再修复或重建。FAISS 的 HNSW 不支持删除。
  - LSM 式写入：新数据先写入可以暴力扫描的小段，再在后台合并、建索引。
  - 分片：scatter-gather，各分片取 top-k 再合并，尾延迟取决于最慢的分片。
  - 多租户三种做法：每个租户一个 collection；共享索引加租户字段；大租户单独分片。
- **问**：HNSW 怎么删除？千万级文档、上万个租户怎么设计？
- **源**：R41 R42 R43 R44 R45 R46

### 3.10 真实系统
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

## M4　检索质量

### 4.1 稀疏与稠密检索，BM25
- **级**：基础
- **深**：
  - BM25 由三部分组成：IDF、词频饱和（参数 k1）、文档长度归一化（参数 b）。
  - BM25 擅长精确词、编号和罕见词；稠密检索擅长同义改写。
  - BEIR 显示：BM25 在零样本下很强，稠密模型跨领域泛化较弱。
- **问**：有了向量检索，为什么还要 BM25？
- **源**：R53

### 4.2 学习型稀疏检索（SPLADE、ELSER）
- **级**：进阶
- **深**：用 MLM head 输出整个词表上的权重，自带词扩展，仍然走倒排索引，结果可解释。
- **问**：SPLADE 和 BM25 有什么区别？
- **源**：R54 R55

### 4.3 混合检索与融合
- **级**：基础
- **深**：
  - RRF：得分 = Σ 1/(k + 排名)，k 取 60。只看名次，不需要校准两路分数的尺度。
  - 也可以把分数归一化后加权，例如 Weaviate 用 alpha 调节权重。
- **问**：为什么用 RRF，而不是把两路分数直接相加？
- **源**：R56 R57 R58

### 4.4 重排（Rerank）
- **级**：基础→进阶
- **深**：
  - 两阶段：先高召回地取 50–200 条，再精排。
  - cross-encoder：把 query 和文档拼在一起编码，精度高，但每个候选都要单独算一遍。
  - ColBERT（late interaction）：每个 token 一个向量，对每个 query token 取与文档 token 的最大相似度再求和。文档侧可以预先计算，但存储量大。
- **问**：bi-encoder、cross-encoder、ColBERT 有什么区别？各自成本如何？
- **源**：R59 R60 R61 R15

### 4.5 查询改写与路由
- **级**：进阶
- **深**：
  - 改写：把多轮对话里的问题改成独立完整的 query。
  - multi-query：一个问题生成多个 query，检索后用 RRF 融合。
  - HyDE：先让 LLM 写一个假设答案，再用它去检索。代价是多一次调用，还可能引入错误信息。
  - 问题分解：把复杂问题拆成子问题。
  - 路由：按意图分到不同的索引或工具。
- **问**：用户的问题很口语化，或者需要多跳推理，怎么办？
- **源**：R62 R63 R64

## M5　生成

### 5.1 上下文组装与 lost in the middle
- **级**：基础
- **深**：
  - 去重，合并相邻块或扩展到父块，控制 token 预算。
  - 关键证据放在开头或结尾，因为中间的信息最容易被忽略。
  - 每块带上来源、标题和日期。
  - 上下文越长越容易出问题（context rot）。
- **问**：召回了 20 块，怎么放进 prompt？
- **源**：R65 R66

### 5.2 引用、grounding 与 RAG prompt
- **级**：进阶
- **深**：
  - 给每块编号，要求模型逐句引用，事后再校验引用是否存在、是否真的支持这句话。
  - 检索不到答案时要能拒答。
  - 检索来的内容只当作数据，不能当作指令，否则会被间接注入。
- **问**：怎么让回答带上可靠的引用？检索到的文档里有恶意指令怎么办？
- **源**：R68 R78 R83

## M6　进阶与前沿

### 6.1 Agentic RAG
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

### 6.2 GraphRAG
- **级**：前沿
- **深**：
  - 流程：抽取实体和关系 → 建图 → 社区划分 → 生成分层摘要。
  - 能回答「整个语料库的主题是什么」这类全局问题。
  - 缺点是索引成本高。LazyGraphRAG 把索引成本降到原来的 0.1%。
  - RAPTOR 是另一种做法：递归聚类，生成摘要树。
- **问**：GraphRAG 能解决普通 RAG 解决不了的什么问题？代价是什么？
- **源**：R73 R74 R75

### 6.3 多模态 RAG
- **级**：前沿
- **深**：两条路线：
  - 先解析、OCR、给图表写 caption，全部转成文本再检索；
  - 直接对页面截图做视觉 embedding，例如 ColPali。
- **问**：图表很多的 PDF 怎么检索？
- **源**：R76 R7

### 6.4 2025–26 年的长上下文与 RAG
- **级**：进阶
- **深**：
  - 模型的有效上下文远小于标称长度。
  - 常见组合（判断）：先用 RAG 缩小范围，再用长上下文读整篇文档，配合 prompt caching 降低成本。
- **问**：同 1.2。
- **源**：R4 R66 R67

## M7　评估

### 7.1 检索指标
- **级**：基础
- **深**：
  - recall@k：对 RAG 最关键，因为模型只看得到 top-k。
  - MRR：第一个相关结果排名的倒数。
  - nDCG：支持分级相关度，按 log 折扣，再除以理想排序下的 DCG。
- **问**：nDCG 怎么算？RAG 主要看哪个指标？
- **源**：R77 R53

### 7.2 生成指标与评测框架
- **级**：进阶
- **深**：
  - faithfulness：把回答拆成若干条陈述，逐条判断是否被上下文支持。
  - 其他指标：answer relevancy、context precision / recall。
  - 用 LLM 当裁判前，要先和人工标注对齐。
  - 常用框架：RAGAS。
- **问**：怎么检测幻觉？LLM 当裁判可靠吗？
- **源**：R78

### 7.3 构建评测集
- **级**：进阶
- **深**：
  - 从真实日志中分层抽样，覆盖无答案、多跳、权限敏感等类型。
  - 用 LLM 合成问题，再人工审核。
  - 解析、检索、重排、生成各自单独评估。
  - 建一套回归集放进 CI。
- **问**：没有标注数据，怎么评估 RAG？
- **源**：R6 R78

## M8　生产

### 8.1 延迟、成本与缓存
- **级**：进阶
- **深**：
  - 生成通常占延迟和成本的大头（判断）。
  - 三层缓存：
    - embedding 按内容 hash 缓存；
    - 语义缓存：必须按租户和权限隔离；
    - prompt caching。
- **问**：RAG 又慢又贵，怎么优化？语义缓存有什么风险？
- **源**：R79 R80 R11

### 8.2 新鲜度
- **级**：进阶
- **深**：
  - 用 CDC 或 webhook 做增量同步。
  - 写入后立即可见（例如 Pinecone 的 memtable）。
  - 按版本或时间过滤。
- **问**：新文档多久能被检索到？怎么保证？
- **源**：R44 R48

### 8.3 按权限检索与数据安全（高频，和 [Harness 7.4](../Harness/README.md) 是同一类问题）
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

### 8.4 可观测性与失败模式
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

## 工业界在用的与偏学术的
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
