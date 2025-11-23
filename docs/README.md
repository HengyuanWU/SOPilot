# SOPilot 项目文档中心

> **欢迎使用 SOPilot 项目文档**  
> 本文档中心提供了完整的技术文档、使用指南和最佳实践。

---

## 📚 文档导航

### 🚀 快速开始

| 文档 | 说明 | 适用人群 |
|-----|------|---------|
| [项目架构文档](项目架构文档.md) | 项目整体架构和技术栈 | 所有人 |
| [快速配置指南](QUICK_CONFIG_GUIDE.md) | 快速配置和启动项目 | 新手 |
| [前后端集成](FRONTEND_BACKEND_INTEGRATION.md) | 前后端集成说明 | 全栈开发者 |

### 🤖 核心技术

#### LangChain & RAG

| 文档 | 说明 | 版本 |
|-----|------|------|
| [LangChain 集成完整指南](LangChain_Integration.md) | LangChain RAG 集成的完整文档 | v1.0 ✅ |

**快速链接**:
- [快速测试](LangChain_Integration.md#快速开始) - 一键运行测试
- [架构设计](LangChain_Integration.md#架构概览) - 了解系统架构
- [使用指南](LangChain_Integration.md#使用指南) - 学习如何使用
- [故障排查](LangChain_Integration.md#故障排查) - 解决常见问题

#### 知识图谱 (Knowledge Graph)

| 文档 | 说明 | 版本 |
|-----|------|------|
| [知识图谱完整指南](KG_Knowledge_Graph_Guide.md) | Neo4j + Neomodel 知识图谱系统 | v1.0 ✅ |
| [Neo4j 教材知识图谱](真·Neo4j%20教材%20→%20知识图谱.md) | 教材到知识图谱的转换 | - |

**快速链接**:
- [架构设计](KG_Knowledge_Graph_Guide.md#架构设计) - KG 架构说明
- [Neo4j 集成](KG_Knowledge_Graph_Guide.md#neo4j-集成) - Neo4j 使用指南
- [Neomodel 迁移](KG_Knowledge_Graph_Guide.md#neomodel-迁移) - ORM 迁移文档
- [性能优化](KG_Knowledge_Graph_Guide.md#性能优化) - 优化建议

#### Embedding 系统

| 文档 | 说明 | 版本 |
|-----|------|------|
| [Embedding 系统完整指南](Embedding_System_Guide.md) | 文本嵌入和向量化系统 | v1.0 ✅ |

**快速链接**:
- [架构设计](Embedding_System_Guide.md#架构设计) - Embedding 架构
- [缓存机制](Embedding_System_Guide.md#缓存机制) - 缓存策略
- [性能优化](Embedding_System_Guide.md#性能优化) - 性能调优
- [使用指南](Embedding_System_Guide.md#使用指南) - 使用示例

#### RAG 数据库架构

| 文档 | 说明 | 版本 |
|-----|------|------|
| [RAG 数据库架构](RAG_DATABASE_ARCHITECTURE.md) | RAG 系统的数据库设计 | - |

### 🛠️ 开发指南

| 文档 | 说明 |
|-----|------|
| [文档存储规范](DOCUMENT_STORAGE_GUIDELINES.md) | 文档编写和存储规范 |
| [Improove 指南](IMPROOVE_GUIDE.md) | Improove 功能使用指南 |
| [Improove 修复日志](IMPROOVE_GUIDE_FIX_CHANGELOG.md) | Improove 修复记录 |

---

## 🎯 按场景查找文档

### 场景 1: 我想快速开始使用项目

1. 阅读 [项目架构文档](项目架构文档.md) 了解整体
2. 参考 [快速配置指南](QUICK_CONFIG_GUIDE.md) 进行配置
3. 运行 `run_docker_test.bat` 验证环境

### 场景 2: 我想了解 RAG 系统

1. 阅读 [LangChain 集成完整指南](LangChain_Integration.md)
2. 查看 [Embedding 系统完整指南](Embedding_System_Guide.md)
3. 参考 [RAG 数据库架构](RAG_DATABASE_ARCHITECTURE.md)

### 场景 3: 我想使用知识图谱

1. 阅读 [知识图谱完整指南](KG_Knowledge_Graph_Guide.md)
2. 查看 [Neo4j 教材知识图谱](真·Neo4j%20教材%20→%20知识图谱.md)
3. 参考架构文档中的 KG 部分

### 场景 4: 我遇到了问题

1. 查看对应功能的"故障排查"部分：
   - [LangChain 故障排查](LangChain_Integration.md#故障排查)
   - [KG 故障排查](KG_Knowledge_Graph_Guide.md#故障排查)
   - [Embedding 故障排查](Embedding_System_Guide.md#故障排查)
2. 检查 Docker 日志
3. 查看相关的配置文档

### 场景 5: 我想优化性能

1. [Embedding 性能优化](Embedding_System_Guide.md#性能优化)
2. [KG 性能优化](KG_Knowledge_Graph_Guide.md#性能优化)
3. 查看各个组件的最佳实践部分

---

## 📊 文档结构

```
docs/
├── README.md                          # 本文档 - 文档中心索引
│
├── 🚀 快速开始
│   ├── 项目架构文档.md
│   ├── QUICK_CONFIG_GUIDE.md
│   └── FRONTEND_BACKEND_INTEGRATION.md
│
├── 🤖 核心技术
│   ├── LangChain_Integration.md       # LangChain RAG 完整指南
│   ├── KG_Knowledge_Graph_Guide.md    # 知识图谱完整指南
│   ├── Embedding_System_Guide.md      # Embedding 系统指南
│   ├── RAG_DATABASE_ARCHITECTURE.md
│   └── 真·Neo4j 教材 → 知识图谱.md
│
└── 🛠️ 开发指南
    ├── DOCUMENT_STORAGE_GUIDELINES.md
    ├── IMPROOVE_GUIDE.md
    └── IMPROOVE_GUIDE_FIX_CHANGELOG.md
```

---

## 📝 文档版本

| 文档 | 版本 | 更新日期 | 状态 |
|-----|------|---------|------|
| LangChain 集成完整指南 | 1.0 | 2025-10-22 | ✅ 最新 |
| 知识图谱完整指南 | 1.0 | 2025-10-22 | ✅ 最新 |
| Embedding 系统指南 | 1.0 | 2025-10-22 | ✅ 最新 |
| 项目架构文档 | - | - | ✅ 稳定 |
| RAG 数据库架构 | - | - | ✅ 稳定 |

---

## 🔍 搜索技巧

### 按技术栈

- **LangChain**: 查看 [LangChain 集成完整指南](LangChain_Integration.md)
- **Neo4j**: 查看 [知识图谱完整指南](KG_Knowledge_Graph_Guide.md)
- **Qdrant**: 查看 [LangChain 集成完整指南](LangChain_Integration.md) 和 [Embedding 系统指南](Embedding_System_Guide.md)
- **OpenAI**: 查看 [Embedding 系统指南](Embedding_System_Guide.md)

### 按功能

- **文本嵌入**: [Embedding 系统指南](Embedding_System_Guide.md)
- **向量检索**: [LangChain 集成完整指南](LangChain_Integration.md)
- **知识图谱**: [知识图谱完整指南](KG_Knowledge_Graph_Guide.md)
- **RAG Pipeline**: [LangChain 集成完整指南](LangChain_Integration.md)

### 按任务

- **安装配置**: [快速配置指南](QUICK_CONFIG_GUIDE.md)
- **运行测试**: [LangChain 集成完整指南](LangChain_Integration.md#测试指南)
- **性能优化**: 查看各个系统指南的"性能优化"章节
- **故障排查**: 查看各个系统指南的"故障排查"章节

---

## 💡 贡献指南

### 文档更新

更新文档时请遵循以下原则：

1. ✅ 保持文档结构清晰
2. ✅ 提供完整的代码示例
3. ✅ 包含故障排查部分
4. ✅ 更新版本号和日期
5. ✅ 更新本索引文档

### 文档规范

参考 [文档存储规范](DOCUMENT_STORAGE_GUIDELINES.md)。

---

## 📞 获取帮助

1. 先查看对应文档的"故障排查"部分
2. 检查 Docker 容器日志
3. 查看相关配置文件
4. 联系项目维护者

---

## 🎓 学习路径

### 初级（了解项目）

1. [项目架构文档](项目架构文档.md)
2. [快速配置指南](QUICK_CONFIG_GUIDE.md)
3. 运行测试脚本验证环境

### 中级（使用功能）

1. [LangChain 集成完整指南](LangChain_Integration.md)
2. [Embedding 系统指南](Embedding_System_Guide.md)
3. [知识图谱完整指南](KG_Knowledge_Graph_Guide.md)

### 高级（深入开发）

1. 阅读源代码
2. 查看各个系统的"最佳实践"部分
3. 参与性能优化和功能开发

---

## 📅 更新日志

### 2025-10-22

- ✅ 创建文档中心索引
- ✅ 整合 LangChain RAG 相关文档
- ✅ 整合知识图谱相关文档
- ✅ 整合 Embedding 相关文档
- ✅ 清理重复和过时文档

---

**文档维护者**: SOPilot Team  
**最后更新**: 2025-10-22  
**文档版本**: 1.0

