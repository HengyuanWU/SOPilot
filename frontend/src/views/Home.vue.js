import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useRunsStore } from '../store/runs';
import { getWorkflows } from '../services/api';
const runs = useRunsStore();
const router = useRouter();
// 状态管理
const loading = ref(false);
const isSubmitting = ref(false);
const runId = ref(null);
const workflows = ref([]);
const selectedWorkflow = ref(null);
const formData = ref({
    topic: '',
    language: '中文',
    chapter_count: 8
});
// 计算属性
const workflowFields = computed(() => {
    if (!selectedWorkflow.value?.input_schema?.properties)
        return {};
    const fields = { ...selectedWorkflow.value.input_schema.properties };
    // 移除已经在基本参数中处理的字段
    delete fields.topic;
    return fields;
});
// 工具函数
function isRequired(fieldName) {
    return selectedWorkflow.value?.input_schema?.required?.includes(fieldName) || false;
}
function toggleArrayValue(fieldName, value) {
    if (!formData.value[fieldName]) {
        formData.value[fieldName] = [];
    }
    const arr = formData.value[fieldName];
    const index = arr.indexOf(value);
    if (index > -1) {
        arr.splice(index, 1);
    }
    else {
        arr.push(value);
    }
}
// 工作流相关函数
function selectWorkflow(workflow) {
    selectedWorkflow.value = workflow;
    // 重置表单数据并应用默认值
    formData.value = {
        topic: formData.value.topic || '',
        language: '中文',
        chapter_count: 8
    };
    // 应用工作流Schema中的默认值
    if (workflow.input_schema?.properties) {
        Object.entries(workflow.input_schema.properties).forEach(([key, field]) => {
            if (field.default !== undefined) {
                formData.value[key] = field.default;
            }
        });
    }
}
async function loadWorkflows() {
    try {
        loading.value = true;
        workflows.value = await getWorkflows();
        // 默认选择第一个工作流（通常是textbook）
        if (workflows.value.length > 0) {
            selectWorkflow(workflows.value[0]);
        }
    }
    catch (error) {
        console.error('Failed to load workflows:', error);
    }
    finally {
        loading.value = false;
    }
}
async function onSubmit() {
    if (!selectedWorkflow.value)
        return;
    try {
        isSubmitting.value = true;
        // 准备提交数据
        const payload = {
            topic: formData.value.topic,
            language: formData.value.language || '中文',
            chapter_count: formData.value.chapter_count || 8,
            workflow_id: selectedWorkflow.value.id
        };
        // 添加工作流特定参数
        const workflowParams = {};
        Object.keys(workflowFields.value).forEach(key => {
            if (formData.value[key] !== undefined) {
                workflowParams[key] = formData.value[key];
            }
        });
        if (Object.keys(workflowParams).length > 0) {
            payload.workflow_params = workflowParams;
        }
        const created = await runs.createRun(payload);
        runId.value = created.id;
        router.push({ name: 'run-detail', params: { id: created.id } });
    }
    catch (error) {
        console.error('Failed to create run:', error);
        alert('创建运行失败，请重试');
    }
    finally {
        isSubmitting.value = false;
    }
}
// 生命周期
onMounted(() => {
    loadWorkflows();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['workflow-selector']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-card']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-card']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-card']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-card']} */ ;
/** @type {__VLS_StyleScopedClasses['dynamic-form']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-label']} */ ;
/** @type {__VLS_StyleScopedClasses['page']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-cards']} */ ;
/** @type {__VLS_StyleScopedClasses['dynamic-form']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
if (__VLS_ctx.workflows.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "workflow-selector" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "workflow-cards" },
    });
    for (const [workflow] of __VLS_getVForSourceType((__VLS_ctx.workflows))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.workflows.length > 0))
                        return;
                    __VLS_ctx.selectWorkflow(workflow);
                } },
            key: (workflow.id),
            ...{ class: (['workflow-card', { active: __VLS_ctx.selectedWorkflow?.id === workflow.id }]) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        (workflow.name);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (workflow.description);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "workflow-tags" },
        });
        for (const [tag] of __VLS_getVForSourceType((workflow.tags))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                key: (tag),
                ...{ class: "tag" },
            });
            (tag);
        }
    }
}
if (__VLS_ctx.selectedWorkflow) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.form, __VLS_intrinsicElements.form)({
        ...{ onSubmit: (__VLS_ctx.onSubmit) },
        ...{ class: "dynamic-form" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-group" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        placeholder: "请输入主题",
        required: true,
    });
    (__VLS_ctx.formData.topic);
    for (const [field, key] of __VLS_getVForSourceType((__VLS_ctx.workflowFields))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (key),
            ...{ class: "form-group" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
        (field.title || key);
        if (field.type === 'string' && !field.enum) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
                type: (field.ui_widget === 'textarea' ? 'text' : 'text'),
                placeholder: (field.ui_placeholder || field.description),
                required: (__VLS_ctx.isRequired(String(key))),
            });
            (__VLS_ctx.formData[key]);
        }
        else if (field.type === 'string' && field.enum) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
                value: (__VLS_ctx.formData[key]),
                required: (__VLS_ctx.isRequired(String(key))),
            });
            for (const [option] of __VLS_getVForSourceType((field.enum))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                    key: (option),
                    value: (option),
                });
                (option);
            }
        }
        else if (field.type === 'integer' || field.type === 'number') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
                type: "number",
                min: (field.minimum),
                max: (field.maximum),
                required: (__VLS_ctx.isRequired(String(key))),
            });
            (__VLS_ctx.formData[key]);
        }
        else if (field.type === 'boolean') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
                type: "checkbox",
            });
            (__VLS_ctx.formData[key]);
        }
        else if (field.type === 'array' && field.items?.enum) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "checkbox-group" },
            });
            for (const [option] of __VLS_getVForSourceType((field.items.enum))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
                    key: (option),
                    ...{ class: "checkbox-label" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
                    ...{ onChange: (...[$event]) => {
                            if (!(__VLS_ctx.selectedWorkflow))
                                return;
                            if (!!(field.type === 'string' && !field.enum))
                                return;
                            if (!!(field.type === 'string' && field.enum))
                                return;
                            if (!!(field.type === 'integer' || field.type === 'number'))
                                return;
                            if (!!(field.type === 'boolean'))
                                return;
                            if (!(field.type === 'array' && field.items?.enum))
                                return;
                            __VLS_ctx.toggleArrayValue(String(key), option);
                        } },
                    type: "checkbox",
                    value: (option),
                    checked: (__VLS_ctx.formData[key]?.includes(option)),
                });
                (option);
            }
        }
        if (field.description) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({
                ...{ class: "field-description" },
            });
            (field.description);
        }
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        type: "submit",
        disabled: (!__VLS_ctx.selectedWorkflow || __VLS_ctx.isSubmitting),
    });
    (__VLS_ctx.isSubmitting ? '创建中...' : '创建运行');
}
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading" },
    });
}
if (__VLS_ctx.runId) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    const __VLS_0 = {}.RouterLink;
    /** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
        to: ({ name: 'run-detail', params: { id: __VLS_ctx.runId } }),
    }));
    const __VLS_2 = __VLS_1({
        to: ({ name: 'run-detail', params: { id: __VLS_ctx.runId } }),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    __VLS_3.slots.default;
    (__VLS_ctx.runId);
    var __VLS_3;
}
/** @type {__VLS_StyleScopedClasses['page']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-selector']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-cards']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-tags']} */ ;
/** @type {__VLS_StyleScopedClasses['tag']} */ ;
/** @type {__VLS_StyleScopedClasses['dynamic-form']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-group']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-label']} */ ;
/** @type {__VLS_StyleScopedClasses['field-description']} */ ;
/** @type {__VLS_StyleScopedClasses['loading']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            loading: loading,
            isSubmitting: isSubmitting,
            runId: runId,
            workflows: workflows,
            selectedWorkflow: selectedWorkflow,
            formData: formData,
            workflowFields: workflowFields,
            isRequired: isRequired,
            toggleArrayValue: toggleArrayValue,
            selectWorkflow: selectWorkflow,
            onSubmit: onSubmit,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
