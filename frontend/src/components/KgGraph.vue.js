import { ref, onMounted, onUnmounted, watch } from 'vue';
import cytoscape from 'cytoscape';
import { getKgSection } from '../services/api';
const props = defineProps();
const graphContainer = ref();
const loading = ref(false);
const error = ref('');
const graphStats = ref(null);
let cy = null;
const initCytoscape = () => {
    if (!graphContainer.value)
        return;
    cy = cytoscape({
        container: graphContainer.value,
        style: [
            {
                selector: 'node',
                style: {
                    'background-color': '#0074D9',
                    'label': 'data(label)',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'color': '#fff',
                    'font-size': '12px',
                    'width': 40,
                    'height': 40,
                    'overlay-padding': '6px',
                    'z-index': 10
                }
            },
            {
                selector: 'node[type="concept"]',
                style: {
                    'background-color': '#FF851B'
                }
            },
            {
                selector: 'node[type="entity"]',
                style: {
                    'background-color': '#2ECC40'
                }
            },
            {
                selector: 'node[type="relationship"]',
                style: {
                    'background-color': '#B10DC9',
                    'shape': 'diamond'
                }
            },
            {
                selector: 'edge',
                style: {
                    'width': 2,
                    'line-color': '#ccc',
                    'target-arrow-color': '#ccc',
                    'target-arrow-shape': 'triangle',
                    'arrow-scale': 1.2,
                    'curve-style': 'bezier',
                    'label': 'data(label)',
                    'font-size': '10px',
                    'text-background-color': '#fff',
                    'text-background-opacity': 0.8,
                    'text-background-padding': '2px'
                }
            },
            {
                selector: 'node:selected',
                style: {
                    'border-width': 3,
                    'border-color': '#FF4136'
                }
            },
            {
                selector: 'edge:selected',
                style: {
                    'line-color': '#FF4136',
                    'target-arrow-color': '#FF4136',
                    'width': 3
                }
            }
        ],
        layout: {
            name: 'cose',
            idealEdgeLength: 100,
            nodeOverlap: 20,
            refresh: 20,
            fit: true,
            padding: 30,
            randomize: false,
            componentSpacing: 100,
            nodeRepulsion: 400000,
            edgeElasticity: 100,
            nestingFactor: 5,
            gravity: 80,
            numIter: 1000,
            initialTemp: 200,
            coolingFactor: 0.95,
            minTemp: 1.0
        }
    });
    // 添加交互事件
    cy.on('tap', 'node', (evt) => {
        const node = evt.target;
        console.log('节点详情:', node.data());
    });
    cy.on('tap', 'edge', (evt) => {
        const edge = evt.target;
        console.log('边详情:', edge.data());
    });
};
const loadGraphData = async (sectionId) => {
    if (!cy)
        return;
    loading.value = true;
    error.value = '';
    try {
        const data = await getKgSection(sectionId);
        if (!data.nodes || !data.edges) {
            throw new Error('图谱数据格式错误');
        }
        // 转换数据格式为 Cytoscape 所需
        const cytoscapeData = [
            ...data.nodes.map((node) => ({
                data: {
                    id: node.id,
                    label: node.label || node.name || node.id,
                    type: node.type || 'concept',
                    ...node.properties
                }
            })),
            ...data.edges.map((edge) => ({
                data: {
                    id: edge.id || `${edge.source}-${edge.target}`,
                    source: edge.source,
                    target: edge.target,
                    label: edge.label || edge.type || '',
                    type: edge.type || 'relation',
                    ...edge.properties
                }
            }))
        ];
        cy.elements().remove();
        cy.add(cytoscapeData);
        cy.layout({ name: 'cose' }).run();
        graphStats.value = {
            nodes: data.nodes.length,
            edges: data.edges.length
        };
    }
    catch (err) {
        error.value = err.message || '加载图谱数据失败';
        console.error('KG Graph loading error:', err);
    }
    finally {
        loading.value = false;
    }
};
const refreshGraph = () => {
    if (props.sectionId) {
        loadGraphData(props.sectionId);
    }
};
const resetLayout = () => {
    if (cy) {
        cy.layout({ name: 'cose' }).run();
    }
};
// 监听 sectionId 变化
watch(() => props.sectionId, (newSectionId) => {
    if (newSectionId) {
        loadGraphData(newSectionId);
    }
}, { immediate: true });
onMounted(() => {
    initCytoscape();
});
onUnmounted(() => {
    if (cy) {
        cy.destroy();
    }
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['kg-graph-header']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-canvas']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-canvas']} */ ;
/** @type {__VLS_StyleScopedClasses['loading']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "kg-graph-container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "kg-graph-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "graph-controls" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.refreshGraph) },
    disabled: (__VLS_ctx.loading),
    ...{ class: "btn btn-secondary" },
});
(__VLS_ctx.loading ? '加载中...' : '刷新图谱');
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.resetLayout) },
    ...{ class: "btn btn-secondary" },
});
if (__VLS_ctx.error) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-message" },
    });
    (__VLS_ctx.error);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ref: "graphContainer",
    ...{ class: "graph-canvas" },
    ...{ class: ({ loading: __VLS_ctx.loading }) },
});
/** @type {typeof __VLS_ctx.graphContainer} */ ;
if (__VLS_ctx.graphStats) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "graph-stats" },
    });
    (__VLS_ctx.graphStats.nodes);
    (__VLS_ctx.graphStats.edges);
}
/** @type {__VLS_StyleScopedClasses['kg-graph-container']} */ ;
/** @type {__VLS_StyleScopedClasses['kg-graph-header']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['error-message']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-canvas']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-stats']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            graphContainer: graphContainer,
            loading: loading,
            error: error,
            graphStats: graphStats,
            refreshGraph: refreshGraph,
            resetLayout: resetLayout,
        };
    },
    __typeProps: {},
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    __typeProps: {},
});
; /* PartiallyEnd: #4569/main.vue */
