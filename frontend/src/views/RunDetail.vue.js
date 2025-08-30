import { onMounted, computed } from 'vue';
import { useRoute } from 'vue-router';
import { useRunsStore } from '../store/runs';
import RunConsole from '../components/RunConsole.vue';
import KgGraph from '../components/KgGraph.vue';
const route = useRoute();
const runs = useRunsStore();
const id = computed(() => String(route.params.id || ''));
const status = computed(() => JSON.stringify(runs.status, null, 2));
const logs = computed(() => runs.logs);
const sectionId = computed(() => {
    const res = (runs.status && runs.status.result) || null;
    return (res && res.section_id) || id.value;
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
onMounted(async () => {
    if (id.value) {
        await runs.fetchStatus(id.value);
        runs.watchStream(id.value);
    }
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['kg-panel']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
(__VLS_ctx.id);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "toolbar" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.refresh) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.copyId) },
});
const __VLS_0 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    to: "/",
}));
const __VLS_2 = __VLS_1({
    to: "/",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
var __VLS_3;
__VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
    ...{ class: "status" },
});
(__VLS_ctx.status);
/** @type {[typeof RunConsole, ]} */ ;
// @ts-ignore
const __VLS_4 = __VLS_asFunctionalComponent(RunConsole, new RunConsole({
    logs: (__VLS_ctx.logs),
}));
const __VLS_5 = __VLS_4({
    logs: (__VLS_ctx.logs),
}, ...__VLS_functionalComponentArgsRest(__VLS_4));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "kg-panel" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
(__VLS_ctx.sectionId);
/** @type {[typeof KgGraph, ]} */ ;
// @ts-ignore
const __VLS_7 = __VLS_asFunctionalComponent(KgGraph, new KgGraph({
    sectionId: (__VLS_ctx.sectionId),
}));
const __VLS_8 = __VLS_7({
    sectionId: (__VLS_ctx.sectionId),
}, ...__VLS_functionalComponentArgsRest(__VLS_7));
/** @type {__VLS_StyleScopedClasses['page']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['status']} */ ;
/** @type {__VLS_StyleScopedClasses['kg-panel']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            RunConsole: RunConsole,
            KgGraph: KgGraph,
            id: id,
            status: status,
            logs: logs,
            sectionId: sectionId,
            refresh: refresh,
            copyId: copyId,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
