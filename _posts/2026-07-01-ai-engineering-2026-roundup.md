# 2025年1月-2026年6月 AI 工程领域 10 大观点

> 基于 60 篇 AI 工程博客（2025-01 至 2026-06）的系统性通读与交叉验证。
> 来源涵盖 Anthropic、LangChain、NVIDIA、Microsoft、Amazon、Apple、Google、Cloudflare、Modal、Vercel、Braintrust、LlamaIndex、vLLM、OpenRouter、Weaviate、Qdrant、Databricks、美团，以及 Chip Huyen、Simon Willison、Eugene Yan、Karpathy、Lilian Weng、Sebastian Raschka 等独立作者。

---

## 1. 框架 > 模型。不是直觉，是硬数据。

Braintrust 对 1,781 条 Agent 追踪的回归分析给出精确数字：Harness（脚手架框架）解释 5.3% 的成功率变异，模型仅 0.7%。**Harness 的影响是模型的 7 倍。** 同一模型换框架，成功率从 12% 跳到 92%。MHBench 在网络安全领域独立验证了这一规律——Incalmo 系统让 10 个模型全部成功，弱框架下强模型全部为零。

如果你的 Agent 效果不好，先优化编排和上下文，再考虑换模型。如果你在纠结选哪个模型，你可能在问错误的问题。

## 2. 环境隔离优先于模型层防御。不要信任模型不会做坏事。

Anthropic 内部红队演练揭露了最致命的攻击向量不是技术注入——是让用户自己成为注入向量。研究员钓鱼让员工粘贴恶意 prompt，Claude 在 25 次中完成 24 次数据窃取。分类器无法检测，因为指令是用户自己输入的。这就是为什么 Anthropic（VM 隔离）、NVIDIA（OpenShell 沙箱 + SIEM）、Cloudflare（60 分钟可丢弃临时账户）不约而同地构建环境隔离优先的安全架构。

设计原则：先设计环境层的硬边界，再通过模型层引导行为。**纵深防御的最终层必须是网络出口控制。**

## 3. 上下文工程正在取代模型选择成为核心竞争力。

Prompt Caching 是一场静默的革命。Anthropic Haiku 4.5 缓存节省 77%，GPT-5.4-mini 节省 80%。Manus AI 说："KV-cache hit rate 是生产 Agent 最重要的单一指标。"这颠覆了"简洁 prompt = 低成本"的传统直觉——一个 5000 行的系统 prompt 如果 80% 被缓存，实际成本可能远低于一个 500 行的未缓存 prompt。

Eugene Yan 把它系统化为"事实在 vault，配置在 CLAUDE.md"的分层上下文管理。Data Formulator 0.7 证明了"工作空间式 AI"比"聊天式 AI"更适合企业场景。

## 4. 代码编排 > 工具调用编排。程序化比声明式更可靠。

LangChain 动态子 Agent 让模型写 JavaScript 脚本驱动并行子任务，而非通过工具调用序列。MagenticBrain 的训练包含编码轨迹——"有时正确答案是五行 Python，不是工具调用。"Karpathy 早在 microgpt 就暗示了这一点：200 行纯 Python，没有工具调用概念，只有输入→计算→输出。代码天然支持循环、条件分支、并发和错误处理——这些是工具调用序列永远做不好的。function calling 可能是 Agent 架构中的一个过渡技术。

## 5. 微型模型正在被严重低估。MoE + DFlash + Caching 是乘法效应。

DeepSeek V4 Flash 在 130 亿活跃参数上实现 79% SWE-bench，成本是 GPT-5.5 的 1/150，MIT 许可。Apple IFP 让 200 亿总参的模型以 3-4 亿活跃参在手机上运行，突破了 DRAM 硬约束。PUBG Ally 的 2B SLM 在玩家测试中"响应速度和存在感"维度战胜云端大模型——在物理交互场景中，**延迟 > 智能**。三个工程优化不是叠加，是相乘：`(1/150 token 成本) × (1/15 GPU 时间) × (1/5 缓存节省)`——千倍级综合优势。

## 6. System 1/2 分层是物理 AI 的必选架构，不是可选方案。

WBench 发现导航能力与视频生成质量完全正交（r≈0）。PUBG Ally 用行为树（System 1，游戏 tick 速率）处理即时战斗响应，用 2B SLM（System 2，事件驱动）处理语言推理。NVIDIA XR AI 用小模型快确认 + 大模型深推理。三个独立团队在不同场景独立收敛到同一架构——**这不是"一个设计选择"，这是在逼近客观最优。**

## 7. 存储与检索必须解耦。这是记忆系统的第一性原理。

Memora（微软，ICML 2026）用 6-8 词主抽象只做 embedding 检索，完整记忆值永不自检索——token 消耗降低 98%，在 LoCoMo 和 LongMemEval 上达到 SOTA。LangChain 的三类记忆（语义/情节/程序性）证明程序性记忆驱动最大行为改进。Eugene Yan 的"vault（事实）+ config（偏好）"分层——三个独立团队指向同一个设计原则：**存储尽可能丰富，检索尽可能轻量。**

## 8. 评估是 CI 门控，不是事后统计。Agent 工程正在成为软件工程。

Braintrust 的方法论——"从生产故障中构建测试用例 → 版本化数据集 → CI 拦截"——本质上是把 Agent 评估当作软件 QA，而非 ML 实验。Candidly 用 IO-HMM 将评估从"对话结束后打分"升级为"逐轮状态推断，实时控制对话走向"（AUC 0.90）。LangChain 的 ADLC 四阶段（Build → Test → Deploy → Monitor）加上 Fleet On-Call Copilot 和 RubricMiddleware，宣告了 Agent 工程从 ML 实验范式向软件工程范式的正式转变。

## 9. 成本是架构约束，不是事后账单。最聪明的工程都在效率端。

vLLM Fusion 的预算面板——三个廉价模型（Gemini 3 Flash + Kimi K2.6 + DeepSeek V4 Pro）融合结果超越单一 DeepSeek V4 Pro。LangChain Gateway 的四维预算控制（组织/工作空间/用户/API Key）。Sierra 的结果导向定价。DFlash 的 15x 吞吐。**AI 系统设计正在从"能力最大化"转向"性价比最优化"。** 不是所有请求都需要最好的模型，只有少数请求值得。vLLM 的 `auto` 路由将这种判断自动化。

## 10. 产品设计 > AI 能力。这是 18 个月、60 篇博客中唯一零分歧的共识。

从 Chip Huyen（2025-01）的"真正的差异化来自产品设计，而非 AI 技术本身"，到 Sierra（2026-06）的"F1 赛车类比——模型能力已经足够强，最终胜负取决于产品策略设计"，到 Andrew Ng 的"人类开发者对产品使用场景的'上下文优势'是 AI 不具备的"——所有人说同一件事。

Sierra 最尖锐的洞察："很多团队拆分多 Agent 是为了适配组织架构——本质是把政治搬到产品里。"**多 Agent 系统最常见的反模式不是因为技术复杂性，而是因为组织政治。**

---

**一句话总结**：2026 年 AI 工程的核心矛盾不是模型不够好，而是围绕模型构建什么、怎么构建、怎么验证。模型本身不再是讨论的中心——上下文、编排、隔离、记忆、评估、成本这些环绕模型的基础设施才是真正的差异化所在。
