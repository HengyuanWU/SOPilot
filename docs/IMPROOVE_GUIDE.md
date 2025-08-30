# Prompt Hub 改造（统一存储｜版本管理｜前端编辑）

---

## 1. Prompt 中心化与前端可视化编辑（Prompt Hub）

> 遵循三原则：**不回退/不兼容旧实现、优先官方实践、可插拔解耦**。本节仅修改 Prompt 方案；其余章节不动。你已否决 DB 方案——本节改为 **YAML 作为唯一事实来源（SoT）**，结合 Git 做版本管理与回滚。

### 1.1 结论（YAML 方案总览）

* **存储介质**：YAML 文件（Git 版本化）。
* **组织方式**：`/backend/src/app/domain/prompts/` 为根，按 Agent/Workflow/Locale 分层；所有运行期读取均来自 YAML，内存带时间戳热缓存。
* **版本化与回滚**：依赖 Git（commit 即版本）。支持在前端查看历史提交并回滚到某次提交（通过后端暴露 `git` 子命令封装）。
* **绑定模型**：通过独立的 `prompt_bindings.yaml` 将 **Agent/Workflow/Locale** → **Prompt 文件** 与 **模型名/参数** 进行声明式绑定，可即时生效。

### 1.2 目录结构（MVP）

```
backend/src/app/domain/prompts/
├── agents/
│   ├── researcher.subchapter.zh.yaml
│   ├── planner.zh.yaml
│   ├── writer.zh.yaml
│   ├── validator.zh.yaml
│   └── kg_builder.zh.yaml
├── workflows/
│   └── textbook.zh.yaml          #（可选）工作流级通用提示
├── prompt_bindings.yaml          # 绑定表（见 1.4）
└── schema.json                   # JSON Schema（前端/后端双端校验）
```

### 1.3 文件格式（与主流提供商对齐）

```yaml
# 示例：agents/researcher.subchapter.zh.yaml
id: researcher.subchapter.zh
agent: researcher
locale: zh
version: 1          # 仅作语义展示；真实版本由 Git 管
messages:
  - role: system
    content: |
      你是一位专业的教材研究员。请仅针对给定的子章节进行研究输出。
  - role: user
    content: |
      教材主题：{{ topic }}
      子章节标题：{{ subchapter_title }}
      子章节大纲：
      {{ subchapter_outline | default('(无补充大纲)') }}

      请输出：
      1) 子章节关键词（8-12个，逗号分隔）
      2) 子章节研究总结（300-600字）
      3) 关键概念（3-6个，逗号分隔）

      输出格式（严格遵守）：
      ## 子章节关键词
      关键词1, 关键词2, 关键词3, ...

      ## 子章节研究总结
      [详细的研究总结]

      ## 关键概念
      概念1, 概念2, 概念3, ...
meta:
  temperature: 0.7
  max_tokens: 1500
  placeholders: [topic, subchapter_title, subchapter_outline]
```

> 与 Dify/OpenAI Chat 接口保持一致的 **多段 messages**（system/user/...），比单字符串更标准。

### 1.4 绑定与模型选择（可被用户修改）

```yaml
# backend/src/app/domain/prompts/prompt_bindings.yaml
# 将 Agent/Workflow/Locale 绑定到具体 YAML + 模型名和参数覆盖
bindings:
  - target_type: agent            # agent | workflow | global
    target_id: researcher         # agent:researcher
    locale: zh
    prompt_file: agents/researcher.subchapter.zh.yaml
    model_ref: siliconflow:Qwen/Qwen3-Coder-30B-A3B-Instruct
    params:
      temperature: 0.6
      max_tokens: 1500

  - target_type: workflow
    target_id: textbook
    locale: zh
    prompt_file: workflows/textbook.zh.yaml
    model_ref: openai:gpt-4o-mini
    params: {}
```

* **模型名可更改**：前端在绑定面板即可切换 `provider:model`，同时覆盖参数。
* **优先级**：`agent` > `workflow` > `global`，命中第一条即用。

### 1.5 后端服务（只读 YAML + 写回 + Git 封装）

* `GET  /api/v1/prompts`：扫描目录，返回 Prompt 元数据（id/路径/locale/最后修改时间）。
* `GET  /api/v1/prompts/:path`：读取 YAML 内容（含 messages/meta）。
* `PUT  /api/v1/prompts/:path`：**保存**（写回 YAML，校验 `schema.json`，并执行 `git add/commit`）。
* `POST /api/v1/prompts/validate`：渲染校验（传变量，返回渲染后的 messages 与缺失变量）。
* `GET  /api/v1/prompt-bindings`：读取 `prompt_bindings.yaml`。
* `PUT  /api/v1/prompt-bindings`：保存绑定（写回 + commit）。
* `GET  /api/v1/prompts/history?path=...`：返回该文件 Git 历史（hash、author、date、message）。
* `POST /api/v1/prompts/rollback`：回滚到指定 commit（受保护：需额外确认参数）。

**实现要点**：

* YAML 解析：`ruamel.yaml`（保留注释与顺序）或 `PyYAML` + Round-trip writer。
* 热缓存：`mtime` + `LRU`；保存后刷新缓存。
* 安全：只允许访问 `prompts/` 子树；路径白名单校验。

### 1.6 LLM 客户端重构（配合 YAML 方案）

> 仍采用 **LLMRouter + ProviderAdapter**（工程化提升），但 **Prompt 来源改为 YAML**。

```
backend/src/app/infrastructure/llm/
├── router.py          # LLMRouter：统一 messages 调用、重试/超时/错误语义
├── adapters/
│   ├── openai.py
│   ├── siliconflow.py
│   └── deepseek.py
└── types.py
```

**Agent 调用规范：**

```python
# 1) 解析绑定
binding = prompt_service.resolve_binding(target_type='agent', target_id='researcher', locale='zh')
# 2) 读取并渲染 YAML（Jinja2 占位符）
messages, meta = prompt_service.render_yaml(binding.prompt_file, variables)
# 3) 发送至 LLMRouter
resp = llm_router.generate(
    provider=binding.provider,     # 从 model_ref 解析
    model=binding.model,
    messages=messages,
    temperature=binding.params.get('temperature', meta.get('temperature', 0.7)),
    max_tokens=binding.params.get('max_tokens', meta.get('max_tokens', 1500)),
    timeout=binding.params.get('timeout', 300),
    tags={"agent":"researcher","run_id":run_id}
)
```

* **替换旧函数**：废弃 `llm_call/llm_call_via_facade`，避免单字符串调用路径（Breaking Change）。

### 1.7 前端「Prompt Studio」（三栏，无弹窗地狱）

**路由**：`/prompts`

**布局（3-pane）**：

1. 左侧：文件树/搜索（Agent/Workflow/Locale 过滤）
2. 中间：编辑器（Monaco）—Tab：`messages` 与 `meta`；下方 Diff
3. 右侧：变量区（自动解析 `{{var}}` → 表单生成）、**模型选择器**（provider+model 搜索下拉）、绑定发布区（选择 agent/workflow/locale 并保存到 `prompt_bindings.yaml`）、预览区（实时渲染 messages）

**关键交互**：

* 「保存」→ `PUT /prompts/:path`（写回 YAML + git commit）
* 「发布到绑定」→ `PUT /prompt-bindings`
* 「查看历史」→ `GET /prompts/history?path=...`（显示提交列表，可一键回滚→ `POST /prompts/rollback`）
* 「试运行」→ `/prompts/validate` + 临时 `llm_router.generate(dry_run=true)`

### 1.8 迁移步骤（只改 Prompt 相关）

1. **抽取硬编码**：将 `app/domain/agents/**` 内所有内嵌 Prompt（如 `subchapter_prompt_template`）搬到 `agents/*.yaml`（格式如 1.3）。
2. **替换调用点**：节点改为 `prompt_service.resolve_binding()` → `render_yaml()` → `llm_router.generate()`。
3. **移除旧接口**：删除 `llm_call/llm_call_via_facade`，统一走 Router。
4. **前端落地**：新增 `/prompts` 页面与三栏交互；在绑定面板即可修改**模型名**与温度/MaxTokens（满足你第 3、4、5 点）。
5. **校验与示例**：提供 `schema.json` 与示例变量集（topic、subchapter\_title、subchapter\_outline）。

### 1.9 验收清单（Prompt Hub 专属）

* [ ] YAML Schema 校验（前后端一致）
* [ ] Prompt 文件热缓存（mtime 触发）
* [ ] 绑定解析与优先级（agent > workflow > global）
* [ ] LLMRouter 三提供商适配（OpenAI/SiliconFlow/DeepSeek）
* [ ] 前端三栏交互（编辑/发布/历史/预览/试运行）
* [ ] 迁移脚本完成（硬编码 → YAML）

1.10 后端骨架代码

backend/src/app/services/prompt_service.py

from pathlib import Path
import yaml, jinja2, time
from typing import Dict, Any, List, Tuple


class PromptService:
    def __init__(self, base_dir: str):
        self.base = Path(base_dir)
        self.cache: Dict[str, Tuple[float, Any]] = {}
        self.jinja_env = jinja2.Environment()


    def _load(self, rel_path: str) -> dict:
        path = self.base / rel_path
        mtime = path.stat().st_mtime
        cached = self.cache.get(rel_path)
        if not cached or cached[0] < mtime:
            data = yaml.safe_load(path.read_text(encoding='utf-8'))
            self.cache[rel_path] = (mtime, data)
        return self.cache[rel_path][1]


    def render_yaml(self, rel_path: str, variables: Dict[str, Any]) -> Tuple[List[dict], dict]:
        data = self._load(rel_path)
        messages = []
        for m in data.get('messages', []):
            template = self.jinja_env.from_string(m['content'])
            messages.append({"role": m['role'], "content": template.render(**variables)})
        return messages, data.get('meta', {})


    def resolve_binding(self, target_type: str, target_id: str, locale: str) -> dict:
        bindings = yaml.safe_load((self.base / 'prompt_bindings.yaml').read_text())
        for b in bindings['bindings']:
            if b['target_type']==target_type and b['target_id']==target_id and b['locale']==locale:
                provider, model = b['model_ref'].split(':',1)
                return {**b, 'provider':provider, 'model':model}
        raise ValueError(f"No binding found for {target_type}:{target_id}@{locale}")

backend/src/app/infrastructure/llm/router.py

from typing import List, Dict
from .types import LLMMessage, LLMResponse
from .adapters import openai, siliconflow, deepseek


class LLMRouter:
    def generate(self, provider: str, model: str, messages: List[Dict], temperature: float=0.7, max_tokens: int=1024, timeout: int=300, tags: Dict[str,str]=None):
        if provider=="openai":
            return openai.chat(model, messages, temperature, max_tokens, timeout)
        if provider=="siliconflow":
            return siliconflow.chat(model, messages, temperature, max_tokens, timeout)
        if provider=="deepseek":
            return deepseek.chat(model, messages, temperature, max_tokens, timeout)
        raise ValueError(f"Unsupported provider {provider}")
1.11 前端骨架代码

frontend/src/views/PromptStudio.vue

<template>
  <div class="prompt-studio">
    <aside class="sidebar">
      <ul>
        <li v-for="f in files" :key="f.id" @click="selectFile(f)">{{ f.id }}</li>
      </ul>
    </aside>
    <main class="editor">
      <MonacoEditor v-model="yamlContent" language="yaml" />
      <button @click="save">保存</button>
    </main>
    <aside class="right-panel">
      <div>
        <label>变量</label>
        <div v-for="v in placeholders" :key="v">{{v}}: <input v-model="vars[v]" /></div>
      </div>
      <div>
        <label>模型</label>
        <select v-model="binding.model_ref">
          <option v-for="m in models" :value="m">{{m}}</option>
        </select>
      </div>
      <button @click="preview">预览</button>
    </aside>
  </div>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import MonacoEditor from 'vue-monaco-editor'
const files = ref([])
const yamlContent = ref('')
const placeholders = ref([])
const vars = ref({})
const models = ref(["siliconflow:Qwen/Qwen3-Coder-30B-A3B-Instruct","openai:gpt-4o-mini"])
const binding = ref({model_ref:""})
function selectFile(f:any){/*load via API*/}
function save(){/*PUT /api/v1/prompts/:path*/}
function preview(){/*POST /api/v1/prompts/validate*/}
</script>
1.12 Seed 脚本

scripts/seed_prompts.py

import os, yaml


PROMPTS = {
"agents/researcher.subchapter.zh.yaml": {
'id': 'researcher.subchapter.zh',
'agent': 'researcher',
'locale': 'zh',
'messages': [
{"role":"system", "content":"你是一位专业的教材研究员。请仅针对给定的子章节进行研究输出。"},
{"role":"user", "content": "教材主题：{{topic}}\n子章节标题：{{subchapter_title}}\n子章节大纲：\n{{subchapter_outline | default('(无补充大纲)')}}..."}
],
'meta': {"temperature":0.7,"max_tokens":1500}
}
}


for path, data in PROMPTS.items():
full_path = os.path.join("backend/src/app/domain/prompts", path)
os.makedirs(os.path.dirname(full_path), exist_ok=True)
with open(full_path, 'w', encoding='utf-8') as f:
yaml.dump(data, f, allow_unicode=True, sort_keys=False)
print("Seed prompts written.")
---

## 1.13. 改造方案

### 1.13.1 存储介质

* **MVP**：YAML 文件存储（Git 管理，开发人员可直接修改，支持 CI/CD 回滚）。
* **未来**：迁移至 DB（PostgreSQL + SQLAlchemy），支持多用户权限与历史审计。

### 1.13.2 目录结构

```
backend/src/app/domain/prompts/
├── registry.py              # Prompt Registry API
├── schemas.py               # Pydantic 模型
└── agents/
    ├── researcher.zh.yaml   # 研究员 Prompt
    ├── writer.zh.yaml       # 写作 Prompt
    ├── validator.zh.yaml    # 验证 Prompt
    └── ...
```

### 1.13.3 YAML 文件示例

```yaml
id: researcher.zh
agent: researcher
language: zh
version: 1
fields:
  system: |
    你是一位专业的教材研究员……
  user: |
    教材主题: {{ topic }}\n子章节标题: {{ subchapter_title }}\n子章节大纲: {{ subchapter_outline }}
params:
  model: Qwen/Qwen3-Coder-30B-A3B-Instruct
  max_tokens: 1500
  temperature: 0.7
```

### 1.13.4 Prompt Registry

* 加载 YAML → Pydantic 校验 → 缓存 → 提供给 Agent 使用。
* 通过 `PromptRegistry.get(agent, lang)` 获取 Prompt 与参数。
* 版本号自增，支持 `PATCH` 更新（自动生成新版本）。

### 1.13.5 LLM Client 改造

* 修改 `llm_call` 接口，支持 **Prompt + Params 统一对象**：

```python
@dataclass
class PromptConfig:
    text: str
    model: str
    max_tokens: int
    temperature: float
    provider: str

def llm_call(prompt_cfg: PromptConfig) -> str:
    request = LLMRequest(
        provider=prompt_cfg.provider,
        model=prompt_cfg.model,
        messages=[{"role": "user", "content": prompt_cfg.text}],
        temperature=prompt_cfg.temperature,
        max_tokens=prompt_cfg.max_tokens,
    )
    return facade.call(request)["content"]
```

---

## 1.14. 前端改造

### 1.14.1 新增页面

* `PromptStudio.vue`：集中管理所有 Agent Prompt。
* 功能：

  * 列表查看（Agent/语言/模型名/版本）
  * 点击进入详情编辑（支持多段编辑：system/user/tool）
  * 一键修改模型名（与 Prompt 一起保存）
  * 版本回滚（选择旧版本恢复）

### 1.14.2 交互设计

* 非弹窗，而是**表格 + 详情面板**：

  * 左侧列表：Agent/Prompt 列表
  * 右侧面板：YAML/表单编辑器
* 编辑器支持 YAML 直改或表单改（切换 Tab）
* 支持“校验”按钮，调用 `POST /api/v1/prompts/validate` 返回渲染结果。

---

## 1.15. API 合同

* `GET /api/v1/prompts`：列出所有 Prompt
* `GET /api/v1/prompts/{id}`：获取 Prompt 详情
* `PUT /api/v1/prompts/{id}`：更新 Prompt，生成新版本
* `POST /api/v1/prompts/validate`：校验变量渲染
* `GET /api/v1/prompts/{id}/history`：返回版本历史（YAML commit 或 DB 记录）

---

## 1.16. 用户体验目标

* 用户在前端可 **同时修改 Prompt 与模型名**，避免两地修改。
* 提供版本回滚，避免误改造成系统异常。
* 不使用弹窗式逐条修改，而是**集中工作台式编辑体验**。

---

## 1.17. 开发任务清单

* [ ] 新建 `domain/prompts/` 与 YAML 文件
* [ ] 实现 PromptRegistry（加载、缓存、更新）
* [ ] 改造 `llm_call` 支持 PromptConfig
* [ ] API：`GET/PUT prompts`、`POST validate`、`GET history`
* [ ] 前端 PromptStudio 页面（表格+详情面板）
* [ ] 支持 Prompt 与模型参数一并编辑保存

---

## 2. 多工作流支持（Workflow Registry + 选择器）

### 2.1 目录与发现机制

```
backend/src/app/domain/workflows/
├── registry.py                 # 统一注册：枚举/动态发现工作流
├── textbook/                   # 既有工作流（保留）
│   └── graph.py                # get_workflow() 暴露入口
└── quiz_maker/                 # 示例：新工作流（可选）
    └── graph.py                # get_workflow()
```

* **约定**：每个工作流子包必须导出：

  * `get_workflow() -> Graph`
  * `get_metadata() -> {id, name, description, input_schema, ui_schema}`

### 2.2 API 合同

* `GET /api/v1/workflows`：枚举可用工作流（含输入 Schema，用于动态表单）
* `POST /api/v1/runs` 新增参数：`workflow_id`（默认 `textbook` 以兼容旧前端）

### 2.3 前端改造

* 首页增加 **工作流选择卡片**：

  * 路由：`/workflows`（或首页即展示）
  * 选择后根据 `input_schema` 动态渲染表单（如：章节数/语言等）

---

## 3. RAG 集成（知识库/检索管线/节点注入）

### 3.1 放置目录（代码 & 数据）

```
# 代码
backend/src/app/infrastructure/rag/
├── chunker.py           # 文档分块（Markdown/HTML/PDF/纯文本）
├── embedder.py          # 向量化（默认：BGE small；后续可换）
├── index_faiss.py       # 索引器（FAISS MVP）
├── retriever.py         # top-k 检索 + 重排（可接 bge-reranker）
└── pipeline.py          # 统一对外：ingest/index/retrieve

# 数据
knowledge_base/
├── raw/                 # 原始上传文档（保持原文件）
├── chunks/              # 解析/切片后的中间件（JSONL）
└── index/               # 向量索引（FAISS 文件）
```

* Docker 卷：将 `knowledge_base/` 挂载到后端容器 `/app/knowledge_base`。

### 3.2 API 合同（知识库管理）

* `GET  /api/v1/rag/docs`：列出已上传文档（文件名/大小/更新时间/索引状态）
* `POST /api/v1/rag/docs`：上传文档（多文件）
* `DELETE /api/v1/rag/docs/{name}`：删除文档
* `POST /api/v1/rag/reindex`：重建索引（可增量）
* `POST /api/v1/rag/test_retrieval`：给定 query，返回 top-k 命中文档片段（调试用）

### 3.3 在工作流中的使用点

* **researcher 节点**：将用户主题/子章节标题作为 query，拼接 `retriever.top_k` 结果进上下文（带来源标注）
* **writer 节点**：可选：将命中片段作为“引用材料”输入到 Prompt（要求引用格式化输出）
* **validator 节点**（可选）：对关键断言进行反向检索核验，生成“证据充分度”分。

### 3.4 前端（Knowledge Base）

```
frontend/src/views/KnowledgeBase.vue
```

* 支持：文件上传/删除、索引状态展示、样例检索预览（query → 片段列表）
* 运行创建页：新增复选框“启用 RAG”与参数（top\_k、是否重排）

### 3.5 参数与默认值（MVP）

* `chunk_size = 800`，`chunk_overlap = 120`
* `top_k = 4`，`score_threshold = 0.2`
* 嵌入：`BAAI/bge-small-zh-v1.5`（或同级开源）


---

````markdown
## 3. RAG 集成（知识库/检索管线/节点注入）

### 3.1 数据存储结构
**知识库目录结构：**
```plaintext
knowledge_base/
├── raw/                 # 原始上传文档（保持原文件）
├── chunks/              # 解析/切片后的中间件（JSONL）
└── index/               # 向量索引（FAISS 文件）
````


### 3.2 Docker 卷挂载

* **Docker 卷挂载**是将宿主机的目录（如 `knowledge_base/`）映射到 Docker 容器中。这样做的好处是容器内部可以方便地访问宿主机上的数据，数据不会丢失。
* 宿主机的 `knowledge_base/` 可以挂载到容器的 `/app/knowledge_base` 路径中，确保容器启动时可以读取和写入宿主机的数据。

**Docker Compose 配置示例：**

```yaml
volumes:
  - ./knowledge_base:/app/knowledge_base
```

这样设置后，宿主机的 `./knowledge_base` 目录将挂载到容器中的 `/app/knowledge_base`，容器内的服务可以直接访问和处理该目录下的数据。

实际开发中，将宿主机的项目根目录下的`knowledge_base`挂载，勿挂载其他目录导致找不到目录


### 3.3 嵌入与重排模型调用

#### 3.3.1 嵌入模型与重排模型调用方式：

我们可以将现有的 `llm_call` 客户端进行扩展，使其支持调用 **嵌入模型** 和 **重排模型**。

**方案：**

* **嵌入模型**：使用 `llm_call` 发送文本数据，将其转化为向量，并返回结果。
* **重排模型**：将查询嵌入和文档嵌入传递给重排模型，按相似度对文档进行重排。

**示例代码：**

```python
class MultiModelClient:
    def __init__(self, provider: str = "siliconflow"):
        self.provider = provider
        self.llm_service = LLMService(provider)

    def call_agent(self, agent_name: str, prompt: str) -> str:
        """调用特定的 Agent 进行推理"""
        return self.llm_service.llm_call(prompt, agent_name=agent_name)
    
    def generate_embeddings(self, texts: List[str]) -> List[float]:
        """调用嵌入模型生成文本向量"""
        prompt = f"请将以下文本转化为向量：\n" + "\n".join(texts)
        return self.llm_service.llm_call(prompt, api_type="embedding", agent_name="embedding-agent")

    def rerank_results(self, query_embeddings: List[float], doc_embeddings: List[float], top_k: int = 4, score_threshold: float = 0.2) -> List[Dict]:
        """调用重排模型重新排序检索结果"""
        prompt = f"根据以下嵌入向量，对文档进行重排：query: {query_embeddings}, documents: {doc_embeddings}, top_k: {top_k}, threshold: {score_threshold}"
        return self.llm_service.llm_call(prompt, api_type="reranking", agent_name="rerank-agent")
```

### 3.4 数据存储与向量索引

1. **raw**：保存原始上传的文档文件（例如 PDF、Word 或 TXT）。
2. **chunks**：将原始文档切片成多个部分，存储为 JSONL 格式，便于检索与向量化。
3. **index**：使用 FAISS 等库存储文档的向量索引，进行高效的相似度检索。

**向量索引的存储**：

* 使用 FAISS 或其他类似的库进行向量化处理，然后将其存储在 `index/` 目录下。
* 文档的嵌入向量会存储在此目录中，供检索系统使用。

**FAISS 索引示例**：

```python
import faiss
import numpy as np

# 创建一个 FAISS 索引
index = faiss.IndexFlatL2(embedding_dim)  # embedding_dim是向量的维度

# 将嵌入向量添加到 FAISS 索引中
index.add(np.array(embeddings, dtype=np.float32))

# 检索与查询向量最相似的 top_k 文档
top_k = 4
distances, indices = index.search(np.array(query_vector, dtype=np.float32), top_k)
```

### 3.5 前端展示与知识库

前端展示当前知识库已有文档，并允许用户上传、删除文档，同时展示文档的检索结果。

**前端页面**：

* **上传文档**：允许用户上传 PDF 或文本文件，后端会解析并切片文档，将其转化为向量并索引。
* **检索文档**：用户输入查询，系统会根据查询的文本向量，从 FAISS 索引中检索最相关的文档。

**前端与后端交互**：

* 用户上传文档 → 调用后端接口进行文档解析与向量化
* 用户查询 → 调用后端的检索接口，获取相关文档及其得分。



