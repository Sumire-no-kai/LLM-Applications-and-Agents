# LLM Applications and Agents / 大模型应用与 Agent

This repository collects what I learn about building applications on large language models: the agent harness around a model, and retrieval-augmented generation (RAG). Each note starts from a real question, explains the mechanism behind it, and records what I tested.

这里记录我系统学习大模型应用开发时整理的笔记，分两个主题：让模型变成可工作 agent 的 **Harness**，以及让模型基于外部资料回答的 **RAG**。每篇笔记从一个实际问题出发，讲清背后的原理，并记录动手验证的结果。

## Roadmap / 学习路线

[ROADMAP.md](ROADMAP.md) is the study roadmap for both topics: the order to learn them in, what each knowledge point covers and how deep to go, common questions, and sources.

[ROADMAP.md](ROADMAP.md) 是两个主题的整体学习路线：学习顺序、每个知识点学什么和学到多深、常见问题，以及出处。

## Topics / 主题

- [Harness](Harness/README.md)：agent loop、上下文工程、工具与 MCP、skills、hooks、沙箱、权限、记忆、持久执行、评估与观测。
- [RAG](RAG/README.md)：解析与切块、embedding、向量检索内核（IVF、PQ、HNSW、DiskANN）、混合检索与重排、生成、评估与生产。

笔记按主题放在对应目录下，每个目录的 README 列出这个主题的笔记。

## Language / 语言

The study notes are written primarily in Chinese.

学习笔记以中文为主。
