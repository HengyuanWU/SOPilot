# 知识图谱节点去重合并文档说明

## 📚 文档结构

### 1. [KG_Consolidation_Plan.md](./KG_Consolidation_Plan.md)
**文档类型**：问题分析与理论设计文档

**内容**：
- 问题现象观察与根因分析
- 系统架构与流程梳理
- 理论解决方案设计（`merge_graphs` 算法）
- 现有 BookMerger 的局限性分析

**适用人群**：
- 架构师（理解系统问题）
- 技术负责人（评审方案）
- 新加入团队的开发者（了解背景）

**特点**：
- ✅ 包含问题诊断
- ✅ 包含理论算法设计
- ❌ **不包含**具体实施代码
- ❌ **不包含**部署步骤

---

### 2. [KG_Consolidation_Implementation_Guide.md](./KG_Consolidation_Implementation_Guide.md) ⭐
**文档类型**：开发实施指南（主文档）

**内容**：
- 符合项目技术栈的实施方案（FastAPI + neomodel + Neo4j）
- 集成步骤（修改哪些文件、在哪里插入代码）
- 关键算法伪代码（指导思路，非完整实现）
- 测试验证步骤（单元测试、集成测试、Cypher 验证查询）
- 性能优化建议
- 部署检查清单

**适用人群**：
- 后端开发工程师（直接实施）
- 测试工程师（设计测试用例）
- DevOps（了解部署要求）

**特点**：
- ✅ 遵循项目规范（所有 Cypher 通过 `Neo4jStore`）
- ✅ 提供实施思路和伪代码
- ✅ 包含详细的集成步骤
- ✅ 包含测试验证方法
- ❌ **不直接提供**完整代码实现（避免"代替开发"）

---

## 🎯 核心修正点

### 修正前的问题
1. **技术栈偏离**：
   - ❌ 文档包含 770 行完整代码，直接使用纯 Cypher
   - ❌ 未遵循项目的 neomodel 规范
   - ❌ 未使用 `Neo4jStore` 统一网关

2. **文档定位错误**：
   - ❌ 混淆了"指导文档"和"代码实现"
   - ❌ 开发者只需复制粘贴，失去了思考和理解的机会

3. **与现有架构脱节**：
   - ❌ 创建全新组件，而非增强现有 `BookMerger`
   - ❌ 未考虑已有的 `KGStore`、`Neo4jStore` 等组件

### 修正后的改进
1. **符合技术栈**：
   - ✅ 所有 Cypher 通过 `Neo4jStore.run_cypher()` 执行
   - ✅ 批量事务使用 `Neo4jStore.run_tx()`
   - ✅ 参考现有 `store.py` 的实现模式

2. **正确的文档定位**：
   - ✅ 提供**实施思路**和**关键伪代码**
   - ✅ 指导开发者在哪个文件、哪个位置、做什么修改
   - ✅ 留给开发者实现的空间（根据项目实际调整）

3. **与现有架构融合**：
   - ✅ 扩展 `BookMerger` 而非创建新模块
   - ✅ 复用 `Neo4jStore` 统一网关
   - ✅ 遵循批量事务模式（参考 `KG_TX_BATCH_SIZE`）

---

## 🚀 如何使用这些文档

### 对于架构师 / 技术负责人
1. 阅读 [`KG_Consolidation_Plan.md`](./KG_Consolidation_Plan.md) 了解问题背景
2. 评审 [`KG_Consolidation_Implementation_Guide.md`](./KG_Consolidation_Implementation_Guide.md) 中的技术方案
3. 决定是否采纳该方案

### 对于后端开发工程师
1. **跳过** `KG_Consolidation_Plan.md`（仅背景材料）
2. **重点阅读** [`KG_Consolidation_Implementation_Guide.md`](./KG_Consolidation_Implementation_Guide.md)
3. 按照以下步骤实施：
   - 第 3 节：实施步骤（明确修改哪些文件）
   - 第 4 节：集成要点（遵循项目规范）
   - 第 5 节：测试验证（确保质量）
   - 第 7 节：部署检查清单（上线前核对）

### 对于测试工程师
1. 阅读 [`KG_Consolidation_Implementation_Guide.md`](./KG_Consolidation_Implementation_Guide.md) 第 5 节
2. 设计测试用例：
   - 单元测试（节点映射、分组逻辑）
   - 集成测试（端到端验证）
   - Cypher 验证查询（数据正确性）
3. 性能测试（1000 节点合并 < 30 秒）

---

## 📋 关键技术决策

### 1. 使用 neomodel 还是纯 Cypher？
**决策**：混合使用
- **节点查询**：优先 Cypher（通过 `Neo4jStore.run_cypher`），性能更好
- **节点操作**：使用 MERGE Cypher（参考 `store.py`），幂等性强
- **批量事务**：使用 `Neo4jStore.run_tx()`（项目统一接口）

### 2. 扩展 BookMerger 还是创建新模块？
**决策**：扩展 `BookMerger`
- **原因**：
  - `BookMerger` 已负责整书合并，职责契合
  - 避免模块碎片化
  - 代码集中，易于维护

### 3. 节点去重策略？
**决策**：按 `name.lower()` 完全匹配，选择 ID 最小的作为 canonical
- **原因**：
  - 简单高效，满足当前需求
  - 未来可扩展为基于 embedding 的相似度匹配

### 4. 失败处理策略？
**决策**：节点合并失败不阻塞整体流程
- **原因**：
  - 节点合并是**优化步骤**，非核心功能
  - 失败后仍然有冗余节点，但不影响查询（只是冗余）
  - 关系聚合仍然正常执行

---

## ⚠️ 重要提醒

1. **不要直接复制文档中的代码**
   - 文档提供的是**伪代码**和**思路指导**
   - 实际实现需根据项目规范调整

2. **必须遵循项目规范**
   - 所有 Cypher 查询必须通过 `Neo4jStore` 执行
   - 不能直接使用 `neo4j-driver` 或 `py2neo`
   - 批量事务使用 `Neo4jStore.run_tx()`

3. **测试充分后再部署**
   - 单元测试覆盖核心逻辑
   - 集成测试验证端到端流程
   - 在测试环境验证后再上生产

4. **备份 Neo4j 数据库**
   - 节点删除是不可逆操作
   - 生产环境执行前务必备份

---

## 📞 联系与反馈

如有疑问或建议，请：
1. 查阅项目规范：`docs/IMPROOVE_GUIDE.md`
2. 参考现有代码：`backend/src/app/domain/kg/`
3. 联系技术负责人

---

**最后更新**：2024-01-XX  
**文档状态**：已修订（符合项目技术栈）

