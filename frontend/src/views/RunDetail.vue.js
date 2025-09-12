import { onMounted, computed, ref } from 'vue';
import { useRoute } from 'vue-router';
import { useRunsStore } from '../store/runs';
import { getRunArtifacts, downloadRunFile, downloadRunArchive } from '../services/api';
import RunConsole from '../components/RunConsole.vue';
import KgGraph from '../components/KgGraph.vue';
const route = useRoute();
const runs = useRunsStore();
const activeTab = ref('overview');
const artifacts = ref([]);
const artifactsLoading = ref(false);
const tabs = [
    { id: 'overview', label: '概览' },
    { id: 'kg', label: '知识图谱' },
    { id: 'artifacts', label: '产物下载' }
];
const id = computed(() => String(route.params.id || ''));
const status = computed(() => JSON.stringify(runs.status, null, 2));
const logs = computed(() => runs.logs);
const statusText = computed(() => {
    const s = runs.status?.status || 'unknown';
    const statusMap = {
        pending: '等待中',
        running: '运行中',
        succeeded: '已完成',
        failed: '失败'
    };
    return statusMap[s] || s;
});
const statusClass = computed(() => {
    const s = runs.status?.status || 'unknown';
    return `status-${s}`;
});
const sectionId = computed(() => {
    const res = (runs.status && runs.status.result) || null;
    const sid = (res && res.section_id) || null;
    const sids = (res && res.section_ids) || null;
    if (sid)
        return sid;
    if (Array.isArray(sids) && sids.length > 0)
        return sids[0];
    return '';
});
const bookId = computed(() => {
    const res = (runs.status && runs.status.result) || null;
    return (res && res.book_id) || null;
});
async function refresh() {
    if (!id.value)
        return;
    await runs.fetchStatus(id.value);
}
async function copyId() {
    try {
        await navigator.clipboard.writeText(id.value);
        // 可根据需要添加轻提示
    }
    catch { }
}
async function refreshArtifacts() {
    if (!id.value)
        return;
    artifactsLoading.value = true;
    try {
        artifacts.value = await getRunArtifacts(id.value);
    }
    catch (error) {
        console.error('Failed to load artifacts:', error);
        artifacts.value = [];
    }
    finally {
        artifactsLoading.value = false;
    }
}
function downloadFile(fileName) {
    const url = downloadRunFile(id.value, fileName);
    window.open(url, '_blank');
}
function downloadArchive() {
    const url = downloadRunArchive(id.value);
    window.open(url, '_blank');
}
function formatFileSize(bytes) {
    if (bytes === 0)
        return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}
function formatDate(timestamp) {
    return new Date(timestamp * 1000).toLocaleString();
}
function getFileTypeLabel(type) {
    const typeLabels = {
        markdown: 'Markdown',
        json: 'JSON',
        text: '文本',
        logs: '日志'
    };
    return typeLabels[type] || type;
}
onMounted(async () => {
    if (id.value) {
        await runs.fetchStatus(id.value);
        runs.watchStream(id.value);
        // 如果运行已完成，自动加载产物
        if (runs.status?.status === 'succeeded') {
            await refreshArtifacts();
        }
    }
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-outline']} */ ;
/** @type {__VLS_StyleScopedClasses['tab']} */ ;
/** @type {__VLS_StyleScopedClasses['tab']} */ ;
/** @type {__VLS_StyleScopedClasses['status-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['console-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['artifacts-header']} */ ;
/** @type {__VLS_StyleScopedClasses['artifact-item']} */ ;
/** @type {__VLS_StyleScopedClasses['page']} */ ;
/** @type {__VLS_StyleScopedClasses['header']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['artifact-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['tabs']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-info" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "run-id" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
(__VLS_ctx.id);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "status-badge" },
    ...{ class: (__VLS_ctx.statusClass) },
});
(__VLS_ctx.statusText);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "toolbar" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.refresh) },
    ...{ class: "btn btn-primary" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.copyId) },
    ...{ class: "btn btn-secondary" },
});
const __VLS_0 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    to: "/",
    ...{ class: "btn btn-outline" },
}));
const __VLS_2 = __VLS_1({
    to: "/",
    ...{ class: "btn btn-outline" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
var __VLS_3;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tabs-container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tabs" },
});
for (const [tab] of __VLS_getVForSourceType((__VLS_ctx.tabs))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.activeTab = tab.id;
            } },
        key: (tab.id),
        ...{ class: (['tab', { active: __VLS_ctx.activeTab === tab.id }]) },
    });
    (tab.label);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tab-content" },
});
if (__VLS_ctx.activeTab === 'overview') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tab-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "overview-grid" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "status-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
        ...{ class: "status-json" },
    });
    (__VLS_ctx.status);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "console-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    /** @type {[typeof RunConsole, ]} */ ;
    // @ts-ignore
    const __VLS_4 = __VLS_asFunctionalComponent(RunConsole, new RunConsole({
        logs: (__VLS_ctx.logs),
    }));
    const __VLS_5 = __VLS_4({
        logs: (__VLS_ctx.logs),
    }, ...__VLS_functionalComponentArgsRest(__VLS_4));
}
if (__VLS_ctx.activeTab === 'kg') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tab-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "kg-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "kg-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    if (__VLS_ctx.bookId) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "kg-info" },
        });
        (__VLS_ctx.bookId);
    }
    else if (__VLS_ctx.sectionId) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "kg-info" },
        });
        (__VLS_ctx.sectionId);
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "kg-info" },
        });
    }
    if (__VLS_ctx.bookId || __VLS_ctx.sectionId) {
        /** @type {[typeof KgGraph, ]} */ ;
        // @ts-ignore
        const __VLS_7 = __VLS_asFunctionalComponent(KgGraph, new KgGraph({
            bookId: (__VLS_ctx.bookId),
            sectionId: (__VLS_ctx.sectionId),
        }));
        const __VLS_8 = __VLS_7({
            bookId: (__VLS_ctx.bookId),
            sectionId: (__VLS_ctx.sectionId),
        }, ...__VLS_functionalComponentArgsRest(__VLS_7));
    }
}
if (__VLS_ctx.activeTab === 'artifacts') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tab-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "artifacts-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "artifacts-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.refreshArtifacts) },
        ...{ class: "btn btn-secondary" },
    });
    if (__VLS_ctx.artifactsLoading) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "loading" },
        });
    }
    else if (__VLS_ctx.artifacts.length === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "empty" },
        });
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "artifacts-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "download-all" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.downloadArchive) },
            ...{ class: "btn btn-primary" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "artifacts-list" },
        });
        for (const [artifact] of __VLS_getVForSourceType((__VLS_ctx.artifacts))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (artifact.name),
                ...{ class: "artifact-item" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "artifact-info" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "artifact-name" },
            });
            (artifact.name);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "artifact-meta" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "artifact-type" },
            });
            (__VLS_ctx.getFileTypeLabel(artifact.type));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "artifact-size" },
            });
            (__VLS_ctx.formatFileSize(artifact.size));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "artifact-modified" },
            });
            (__VLS_ctx.formatDate(artifact.modified));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!(__VLS_ctx.activeTab === 'artifacts'))
                            return;
                        if (!!(__VLS_ctx.artifactsLoading))
                            return;
                        if (!!(__VLS_ctx.artifacts.length === 0))
                            return;
                        __VLS_ctx.downloadFile(artifact.name);
                    } },
                ...{ class: "btn btn-outline btn-sm" },
            });
        }
    }
}
/** @type {__VLS_StyleScopedClasses['page']} */ ;
/** @type {__VLS_StyleScopedClasses['header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-info']} */ ;
/** @type {__VLS_StyleScopedClasses['run-id']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-outline']} */ ;
/** @type {__VLS_StyleScopedClasses['tabs-container']} */ ;
/** @type {__VLS_StyleScopedClasses['tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-content']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['status-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['status-json']} */ ;
/** @type {__VLS_StyleScopedClasses['console-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['kg-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['kg-header']} */ ;
/** @type {__VLS_StyleScopedClasses['kg-info']} */ ;
/** @type {__VLS_StyleScopedClasses['kg-info']} */ ;
/** @type {__VLS_StyleScopedClasses['kg-info']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['artifacts-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['artifacts-header']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['loading']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['artifacts-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['download-all']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['artifacts-list']} */ ;
/** @type {__VLS_StyleScopedClasses['artifact-item']} */ ;
/** @type {__VLS_StyleScopedClasses['artifact-info']} */ ;
/** @type {__VLS_StyleScopedClasses['artifact-name']} */ ;
/** @type {__VLS_StyleScopedClasses['artifact-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['artifact-type']} */ ;
/** @type {__VLS_StyleScopedClasses['artifact-size']} */ ;
/** @type {__VLS_StyleScopedClasses['artifact-modified']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-outline']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-sm']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            RunConsole: RunConsole,
            KgGraph: KgGraph,
            activeTab: activeTab,
            artifacts: artifacts,
            artifactsLoading: artifactsLoading,
            tabs: tabs,
            id: id,
            status: status,
            logs: logs,
            statusText: statusText,
            statusClass: statusClass,
            sectionId: sectionId,
            bookId: bookId,
            refresh: refresh,
            copyId: copyId,
            refreshArtifacts: refreshArtifacts,
            downloadFile: downloadFile,
            downloadArchive: downloadArchive,
            formatFileSize: formatFileSize,
            formatDate: formatDate,
            getFileTypeLabel: getFileTypeLabel,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
