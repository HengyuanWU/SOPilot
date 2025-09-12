import { api } from '../services/api.ts';
import yaml from 'js-yaml';
export default (await import('vue')).defineComponent({
    name: 'PromptStudio',
    data() {
        return {
            prompts: [],
            selectedPrompt: null,
            editingPrompt: null,
            searchQuery: '',
            editMode: 'form', // 'form' | 'yaml'
            yamlContent: '',
            validating: false,
            saving: false,
            validationResult: null
        };
    },
    computed: {
        filteredPrompts() {
            if (!this.searchQuery)
                return this.prompts;
            const query = this.searchQuery.toLowerCase();
            return this.prompts.filter(p => p.agent.toLowerCase().includes(query) ||
                p.locale.toLowerCase().includes(query));
        },
        systemMessage: {
            get() {
                const messages = this.editingPrompt?.messages || [];
                const systemMsg = messages.find(m => m.role === 'system');
                return systemMsg?.content || '';
            },
            set(value) {
                if (!this.editingPrompt?.messages)
                    return;
                const messages = this.editingPrompt.messages;
                const systemIndex = messages.findIndex(m => m.role === 'system');
                if (systemIndex >= 0) {
                    messages[systemIndex].content = value;
                }
                else {
                    messages.unshift({ role: 'system', content: value });
                }
            }
        },
        userMessage: {
            get() {
                const messages = this.editingPrompt?.messages || [];
                const userMsg = messages.find(m => m.role === 'user');
                return userMsg?.content || '';
            },
            set(value) {
                if (!this.editingPrompt?.messages)
                    return;
                const messages = this.editingPrompt.messages;
                const userIndex = messages.findIndex(m => m.role === 'user');
                if (userIndex >= 0) {
                    messages[userIndex].content = value;
                }
                else {
                    messages.push({ role: 'user', content: value });
                }
            }
        }
    },
    async mounted() {
        await this.loadPrompts();
    },
    methods: {
        async loadPrompts() {
            try {
                const response = await api.get('/api/v1/prompts/');
                this.prompts = response.data;
            }
            catch (error) {
                console.error('加载Prompt列表失败:', error);
                this.$message?.error('加载Prompt列表失败');
            }
        },
        async refreshPrompts() {
            await this.loadPrompts();
            this.$message?.success('Prompt列表已刷新');
        },
        async selectPrompt(prompt) {
            this.selectedPrompt = prompt;
            this.validationResult = null;
            try {
                const response = await api.get(`/api/v1/prompts/${prompt.path}`);
                this.editingPrompt = JSON.parse(JSON.stringify(response.data));
                // 确保meta对象存在
                if (!this.editingPrompt.meta) {
                    this.editingPrompt.meta = {};
                }
                this.yamlContent = yaml.dump(this.editingPrompt, {
                    defaultFlowStyle: false,
                    allowUnicode: true
                });
            }
            catch (error) {
                console.error('加载Prompt详情失败:', error);
                this.$message?.error('加载Prompt详情失败');
            }
        },
        async validatePrompt() {
            if (!this.editingPrompt)
                return;
            this.validating = true;
            this.validationResult = null;
            try {
                let promptData = this.editingPrompt;
                // 如果是YAML模式，先解析YAML
                if (this.editMode === 'yaml') {
                    promptData = yaml.load(this.yamlContent);
                }
                const response = await api.post('/api/v1/prompts/validate', promptData);
                this.validationResult = { success: true, data: response.data };
                this.$message?.success('Prompt校验通过');
            }
            catch (error) {
                this.validationResult = {
                    success: false,
                    error: error.response?.data?.detail || error.message
                };
                this.$message?.error('Prompt校验失败');
            }
            finally {
                this.validating = false;
            }
        },
        async savePrompt() {
            if (!this.editingPrompt)
                return;
            this.saving = true;
            try {
                let promptData = this.editingPrompt;
                // 如果是YAML模式，先解析YAML
                if (this.editMode === 'yaml') {
                    promptData = yaml.load(this.yamlContent);
                }
                await api.put(`/api/v1/prompts/${this.selectedPrompt.path}`, promptData);
                this.$message?.success('Prompt保存成功');
                // 刷新列表
                await this.loadPrompts();
                // 更新选中的prompt
                const updated = this.prompts.find(p => p.path === this.selectedPrompt.path);
                if (updated) {
                    this.selectedPrompt = updated;
                }
            }
            catch (error) {
                console.error('保存Prompt失败:', error);
                this.$message?.error('保存Prompt失败: ' + (error.response?.data?.detail || error.message));
            }
            finally {
                this.saving = false;
            }
        }
    },
    watch: {
        editingPrompt: {
            handler(newVal) {
                if (newVal && this.editMode === 'form') {
                    // 当表单模式下数据变化时，同步更新YAML
                    this.yamlContent = yaml.dump(newVal, {
                        defaultFlowStyle: false,
                        allowUnicode: true
                    });
                }
            },
            deep: true
        },
        editMode(newMode) {
            if (newMode === 'yaml' && this.editingPrompt) {
                // 切换到YAML模式时，从表单数据生成YAML
                this.yamlContent = yaml.dump(this.editingPrompt, {
                    defaultFlowStyle: false,
                    allowUnicode: true
                });
            }
            else if (newMode === 'form' && this.yamlContent) {
                // 切换到表单模式时，从YAML解析数据
                try {
                    this.editingPrompt = yaml.load(this.yamlContent);
                }
                catch (error) {
                    console.error('YAML解析失败:', error);
                    this.$message?.error('YAML格式错误');
                }
            }
        }
    }
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['studio-header']} */ ;
/** @type {__VLS_StyleScopedClasses['studio-header']} */ ;
/** @type {__VLS_StyleScopedClasses['list-header']} */ ;
/** @type {__VLS_StyleScopedClasses['refresh-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['search-input']} */ ;
/** @type {__VLS_StyleScopedClasses['prompt-item']} */ ;
/** @type {__VLS_StyleScopedClasses['prompt-item']} */ ;
/** @type {__VLS_StyleScopedClasses['status-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['no-selection']} */ ;
/** @type {__VLS_StyleScopedClasses['editor-header']} */ ;
/** @type {__VLS_StyleScopedClasses['validate-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['validate-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['save-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['save-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['validate-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['save-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['tab']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['form-section']} */ ;
/** @type {__VLS_StyleScopedClasses['form-section']} */ ;
/** @type {__VLS_StyleScopedClasses['form-section']} */ ;
/** @type {__VLS_StyleScopedClasses['message-textarea']} */ ;
/** @type {__VLS_StyleScopedClasses['message-textarea']} */ ;
/** @type {__VLS_StyleScopedClasses['yaml-textarea']} */ ;
/** @type {__VLS_StyleScopedClasses['validation-result']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "prompt-studio" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "studio-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "studio-layout" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "prompt-list" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "list-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.refreshPrompts) },
    ...{ class: "refresh-btn" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
    ...{ class: "icon-refresh" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "search-box" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
    value: (__VLS_ctx.searchQuery),
    type: "text",
    placeholder: "搜索Agent或语言...",
    ...{ class: "search-input" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "prompt-items" },
});
for (const [prompt] of __VLS_getVForSourceType((__VLS_ctx.filteredPrompts))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.selectPrompt(prompt);
            } },
        key: (prompt.id),
        ...{ class: (['prompt-item', { active: __VLS_ctx.selectedPrompt?.id === prompt.id }]) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "prompt-info" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "prompt-title" },
    });
    (prompt.agent);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "prompt-meta" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "locale" },
    });
    (prompt.locale);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "version" },
    });
    (prompt.version);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "model-info" },
    });
    (prompt.model || '未配置');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "status-indicator" },
        ...{ class: (prompt.status || 'active') },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "edit-panel" },
});
if (!__VLS_ctx.selectedPrompt) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "no-selection" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "icon-prompt" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "editor-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "editor-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    (__VLS_ctx.selectedPrompt.agent);
    (__VLS_ctx.selectedPrompt.locale);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "editor-actions" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.validatePrompt) },
        ...{ class: "validate-btn" },
        disabled: (__VLS_ctx.validating),
    });
    (__VLS_ctx.validating ? '校验中...' : '校验');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.savePrompt) },
        ...{ class: "save-btn" },
        disabled: (__VLS_ctx.saving),
    });
    (__VLS_ctx.saving ? '保存中...' : '保存');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "edit-tabs" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(!__VLS_ctx.selectedPrompt))
                    return;
                __VLS_ctx.editMode = 'form';
            } },
        ...{ class: (['tab', { active: __VLS_ctx.editMode === 'form' }]) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(!__VLS_ctx.selectedPrompt))
                    return;
                __VLS_ctx.editMode = 'yaml';
            } },
        ...{ class: (['tab', { active: __VLS_ctx.editMode === 'yaml' }]) },
    });
    if (__VLS_ctx.editMode === 'form') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "form-editor" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "form-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
            value: (__VLS_ctx.editingPrompt.agent),
            type: "text",
            readonly: true,
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "form-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
            value: (__VLS_ctx.editingPrompt.locale),
            type: "text",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "form-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
            value: (__VLS_ctx.editingPrompt.model),
            type: "text",
            placeholder: "例: siliconflow:Qwen/Qwen3-Coder-30B-A3B-Instruct",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "form-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.textarea, __VLS_intrinsicElements.textarea)({
            value: (__VLS_ctx.systemMessage),
            ...{ class: "message-textarea" },
            placeholder: "系统提示词...",
            rows: "4",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "form-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.textarea, __VLS_intrinsicElements.textarea)({
            value: (__VLS_ctx.userMessage),
            ...{ class: "message-textarea" },
            placeholder: "用户提示词模板（支持{{变量}}）...",
            rows: "6",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "form-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "param-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "param-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
            type: "number",
            step: "0.1",
            min: "0",
            max: "2",
        });
        (__VLS_ctx.editingPrompt.meta.temperature);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "param-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
            type: "number",
            min: "1",
        });
        (__VLS_ctx.editingPrompt.meta.max_tokens);
    }
    if (__VLS_ctx.editMode === 'yaml') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "yaml-editor" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.textarea, __VLS_intrinsicElements.textarea)({
            value: (__VLS_ctx.yamlContent),
            ...{ class: "yaml-textarea" },
            placeholder: "YAML内容...",
            rows: "20",
        });
    }
    if (__VLS_ctx.validationResult) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "validation-result" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        if (__VLS_ctx.validationResult.success) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "validation-success" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                ...{ class: "icon-check" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "validation-error" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                ...{ class: "icon-error" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.validationResult.error);
        }
    }
}
/** @type {__VLS_StyleScopedClasses['prompt-studio']} */ ;
/** @type {__VLS_StyleScopedClasses['studio-header']} */ ;
/** @type {__VLS_StyleScopedClasses['studio-layout']} */ ;
/** @type {__VLS_StyleScopedClasses['prompt-list']} */ ;
/** @type {__VLS_StyleScopedClasses['list-header']} */ ;
/** @type {__VLS_StyleScopedClasses['refresh-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-refresh']} */ ;
/** @type {__VLS_StyleScopedClasses['search-box']} */ ;
/** @type {__VLS_StyleScopedClasses['search-input']} */ ;
/** @type {__VLS_StyleScopedClasses['prompt-items']} */ ;
/** @type {__VLS_StyleScopedClasses['prompt-info']} */ ;
/** @type {__VLS_StyleScopedClasses['prompt-title']} */ ;
/** @type {__VLS_StyleScopedClasses['prompt-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['locale']} */ ;
/** @type {__VLS_StyleScopedClasses['version']} */ ;
/** @type {__VLS_StyleScopedClasses['model-info']} */ ;
/** @type {__VLS_StyleScopedClasses['status-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['edit-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['no-selection']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-prompt']} */ ;
/** @type {__VLS_StyleScopedClasses['editor-container']} */ ;
/** @type {__VLS_StyleScopedClasses['editor-header']} */ ;
/** @type {__VLS_StyleScopedClasses['editor-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['validate-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['save-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['edit-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['form-editor']} */ ;
/** @type {__VLS_StyleScopedClasses['form-section']} */ ;
/** @type {__VLS_StyleScopedClasses['form-section']} */ ;
/** @type {__VLS_StyleScopedClasses['form-section']} */ ;
/** @type {__VLS_StyleScopedClasses['form-section']} */ ;
/** @type {__VLS_StyleScopedClasses['message-textarea']} */ ;
/** @type {__VLS_StyleScopedClasses['form-section']} */ ;
/** @type {__VLS_StyleScopedClasses['message-textarea']} */ ;
/** @type {__VLS_StyleScopedClasses['form-section']} */ ;
/** @type {__VLS_StyleScopedClasses['param-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['param-item']} */ ;
/** @type {__VLS_StyleScopedClasses['param-item']} */ ;
/** @type {__VLS_StyleScopedClasses['yaml-editor']} */ ;
/** @type {__VLS_StyleScopedClasses['yaml-textarea']} */ ;
/** @type {__VLS_StyleScopedClasses['validation-result']} */ ;
/** @type {__VLS_StyleScopedClasses['validation-success']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-check']} */ ;
/** @type {__VLS_StyleScopedClasses['validation-error']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-error']} */ ;
var __VLS_dollars;
let __VLS_self;
