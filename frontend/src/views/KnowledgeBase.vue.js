import { ref, onMounted } from 'vue';
// 状态管理
const documents = ref([]);
const loading = ref(false);
const debugQuery = ref('');
const debugResults = ref(null);
const testing = ref(null);
// 上传进度
const uploadProgress = ref({
    show: false,
    uploading: false,
    files: []
});
// API基础URL - 使用相对路径，由Vite代理转发
// 页面加载时获取文档列表
onMounted(() => {
    loadDocuments();
});
// 加载文档列表
async function loadDocuments() {
    try {
        const response = await fetch('/api/v1/rag/docs');
        if (response.ok) {
            documents.value = await response.json();
        }
    }
    catch (error) {
        console.error('加载文档列表失败:', error);
    }
}
// 上传文件
async function uploadFiles(event) {
    const files = event.target.files;
    if (!files || files.length === 0)
        return;
    // 显示进度模态框
    uploadProgress.value = {
        show: true,
        uploading: true,
        files: Array.from(files).map(f => ({ name: f.name, status: 'pending' }))
    };
    // 逐个上传文件
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const progressFile = uploadProgress.value.files[i];
        try {
            progressFile.status = 'uploading';
            const formData = new FormData();
            formData.append('files', file);
            const response = await fetch('/api/v1/rag/docs', {
                method: 'POST',
                body: formData
            });
            if (response.ok) {
                progressFile.status = 'success';
            }
            else {
                progressFile.status = 'error';
            }
        }
        catch (error) {
            console.error(`上传文件 ${file.name} 失败:`, error);
            progressFile.status = 'error';
        }
    }
    uploadProgress.value.uploading = false;
    // 刷新文档列表
    await loadDocuments();
    event.target.value = '';
}
// 删除文档
async function deleteDocument(name) {
    if (!confirm(`确定要删除文档 "${name}" 吗？`))
        return;
    try {
        const response = await fetch(`/api/v1/rag/docs/${encodeURIComponent(name)}`, {
            method: 'DELETE'
        });
        if (response.ok) {
            await loadDocuments();
        }
        else {
            alert('删除失败');
        }
    }
    catch (error) {
        console.error('删除文档失败:', error);
        alert('删除失败');
    }
}
// 重建索引
async function reindexAll() {
    if (!confirm('确定要重建全部索引吗？这可能需要一些时间。'))
        return;
    loading.value = true;
    try {
        const response = await fetch('/api/v1/rag/reindex', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ clean: true })
        });
        if (response.ok) {
            alert('重建索引任务已启动');
            await loadDocuments();
        }
        else {
            alert('重建索引失败');
        }
    }
    catch (error) {
        console.error('重建索引失败:', error);
        alert('重建索引失败');
    }
    finally {
        loading.value = false;
    }
}
// 测试向量检索
async function testVector() {
    await runTest('vector', '/api/v1/rag/test_vector', {
        query: debugQuery.value,
        top_k: 5
    });
}
// 测试KG检索
async function testKG() {
    await runTest('kg', '/api/v1/rag/test_kg', {
        query: debugQuery.value,
        hop: 2,
        rel_types: ['DEFINES', 'MENTIONS', 'HAS_CHUNK']
    });
}
// 测试混合检索
async function testDual() {
    await runTest('dual', '/api/v1/rag/test_dual', {
        query: debugQuery.value
    });
}
// 运行测试
async function runTest(type, url, payload) {
    testing.value = type;
    debugResults.value = null;
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (response.ok) {
            debugResults.value = await response.json();
        }
        else {
            const error = await response.text();
            alert(`测试失败: ${error}`);
        }
    }
    catch (error) {
        console.error(`测试${type}失败:`, error);
        alert(`测试失败: ${error}`);
    }
    finally {
        testing.value = null;
    }
}
// 关闭上传模态框
function closeUploadModal() {
    if (!uploadProgress.value.uploading) {
        uploadProgress.value.show = false;
    }
}
// 工具函数
function formatFileSize(bytes) {
    if (bytes === 0)
        return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}
function formatTime(timestamp) {
    return new Date(timestamp).toLocaleString('zh-CN');
}
function getUploadStatusText(status) {
    const statusMap = {
        pending: '等待中',
        uploading: '上传中',
        success: '成功',
        error: '失败'
    };
    return statusMap[status] || status;
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-header']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-reindex']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-upload']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-upload']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-upload']} */ ;
/** @type {__VLS_StyleScopedClasses['table-header']} */ ;
/** @type {__VLS_StyleScopedClasses['table-row']} */ ;
/** @type {__VLS_StyleScopedClasses['table-row']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-delete']} */ ;
/** @type {__VLS_StyleScopedClasses['query-section']} */ ;
/** @type {__VLS_StyleScopedClasses['query-section']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-test']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-test']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-test']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-test']} */ ;
/** @type {__VLS_StyleScopedClasses['results-section']} */ ;
/** @type {__VLS_StyleScopedClasses['result-group']} */ ;
/** @type {__VLS_StyleScopedClasses['modal']} */ ;
/** @type {__VLS_StyleScopedClasses['status']} */ ;
/** @type {__VLS_StyleScopedClasses['pending']} */ ;
/** @type {__VLS_StyleScopedClasses['status']} */ ;
/** @type {__VLS_StyleScopedClasses['status']} */ ;
/** @type {__VLS_StyleScopedClasses['status']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-refresh']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-upload']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-delete']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "knowledge-base" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "subtitle" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "main-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "left-panel" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "panel-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "actions" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.reindexAll) },
    disabled: (__VLS_ctx.loading),
    ...{ class: "btn-reindex" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
    ...{ class: "icon-refresh" },
});
(__VLS_ctx.loading ? '重建中...' : '重建索引');
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "btn-upload" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
    ...{ class: "icon-upload" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
    ...{ onChange: (__VLS_ctx.uploadFiles) },
    type: "file",
    multiple: true,
    accept: ".pdf,.txt,.md,.docx",
    ...{ style: {} },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "documents-list" },
});
if (__VLS_ctx.documents.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty-state" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "document-table" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "table-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "col-name" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "col-size" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "col-time" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "col-status" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "col-actions" },
    });
    for (const [doc] of __VLS_getVForSourceType((__VLS_ctx.documents))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (doc.name),
            ...{ class: "table-row" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "col-name" },
            title: (doc.name),
        });
        (doc.name);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "col-size" },
        });
        (__VLS_ctx.formatFileSize(doc.size));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "col-time" },
        });
        (__VLS_ctx.formatTime(doc.updated_at));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "col-status" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: (['status-badge', doc.indexed ? 'indexed' : 'pending']) },
        });
        (doc.indexed ? '已索引' : '待索引');
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "col-actions" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.documents.length === 0))
                        return;
                    __VLS_ctx.deleteDocument(doc.name);
                } },
            ...{ class: "btn-delete" },
            title: "删除",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: "icon-delete" },
        });
    }
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "right-panel" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "panel-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "debug-panel" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "query-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.textarea, __VLS_intrinsicElements.textarea)({
    value: (__VLS_ctx.debugQuery),
    placeholder: "输入要测试的查询内容...",
    rows: "3",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "debug-actions" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.testVector) },
    disabled: (!__VLS_ctx.debugQuery.trim() || !!__VLS_ctx.testing),
    ...{ class: "btn-test" },
});
(__VLS_ctx.testing === 'vector' ? '测试中...' : '向量检索');
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.testKG) },
    disabled: (!__VLS_ctx.debugQuery.trim() || !!__VLS_ctx.testing),
    ...{ class: "btn-test" },
});
(__VLS_ctx.testing === 'kg' ? '测试中...' : 'KG检索');
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.testDual) },
    disabled: (!__VLS_ctx.debugQuery.trim() || !!__VLS_ctx.testing),
    ...{ class: "btn-test primary" },
});
(__VLS_ctx.testing === 'dual' ? '测试中...' : '混合检索');
if (__VLS_ctx.debugResults) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "results-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    if (__VLS_ctx.debugResults.vector_hits) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "result-group" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        (__VLS_ctx.debugResults.vector_hits.length);
        for (const [hit, idx] of __VLS_getVForSourceType((__VLS_ctx.debugResults.vector_hits))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (idx),
                ...{ class: "result-item" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "result-header" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "score" },
            });
            (hit.score?.toFixed(3));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "source" },
            });
            (hit.doc);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "result-content" },
            });
            (hit.chunk);
        }
    }
    if (__VLS_ctx.debugResults.kg_hits) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "result-group" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        (__VLS_ctx.debugResults.kg_hits.length);
        for (const [hit, idx] of __VLS_getVForSourceType((__VLS_ctx.debugResults.kg_hits))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (idx),
                ...{ class: "result-item" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "result-header" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "score" },
            });
            (hit.score?.toFixed(3));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "result-content" },
            });
            (hit.path);
        }
    }
    if (__VLS_ctx.debugResults.merged) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "result-group" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        (__VLS_ctx.debugResults.merged.length);
        for (const [item, idx] of __VLS_getVForSourceType((__VLS_ctx.debugResults.merged))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (idx),
                ...{ class: "result-item" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "result-header" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "score" },
            });
            (item.score?.toFixed(3));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "type" },
            });
            (item.type === 'chunk' ? '文档片段' : 'KG路径');
        }
    }
    if (__VLS_ctx.debugResults.prompt_preview) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "result-group" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
            ...{ class: "prompt-preview" },
        });
        (__VLS_ctx.debugResults.prompt_preview);
    }
}
if (__VLS_ctx.uploadProgress.show) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "modal-overlay" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "modal" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "upload-list" },
    });
    for (const [file] of __VLS_getVForSourceType((__VLS_ctx.uploadProgress.files))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (file.name),
            ...{ class: "upload-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "filename" },
        });
        (file.name);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: (['status', file.status]) },
        });
        (__VLS_ctx.getUploadStatusText(file.status));
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "modal-actions" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.closeUploadModal) },
        disabled: (__VLS_ctx.uploadProgress.uploading),
    });
}
/** @type {__VLS_StyleScopedClasses['knowledge-base']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['main-content']} */ ;
/** @type {__VLS_StyleScopedClasses['left-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-header']} */ ;
/** @type {__VLS_StyleScopedClasses['actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-reindex']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-refresh']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-upload']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-upload']} */ ;
/** @type {__VLS_StyleScopedClasses['documents-list']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['document-table']} */ ;
/** @type {__VLS_StyleScopedClasses['table-header']} */ ;
/** @type {__VLS_StyleScopedClasses['col-name']} */ ;
/** @type {__VLS_StyleScopedClasses['col-size']} */ ;
/** @type {__VLS_StyleScopedClasses['col-time']} */ ;
/** @type {__VLS_StyleScopedClasses['col-status']} */ ;
/** @type {__VLS_StyleScopedClasses['col-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['table-row']} */ ;
/** @type {__VLS_StyleScopedClasses['col-name']} */ ;
/** @type {__VLS_StyleScopedClasses['col-size']} */ ;
/** @type {__VLS_StyleScopedClasses['col-time']} */ ;
/** @type {__VLS_StyleScopedClasses['col-status']} */ ;
/** @type {__VLS_StyleScopedClasses['col-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-delete']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-delete']} */ ;
/** @type {__VLS_StyleScopedClasses['right-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-header']} */ ;
/** @type {__VLS_StyleScopedClasses['debug-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['query-section']} */ ;
/** @type {__VLS_StyleScopedClasses['debug-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-test']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-test']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-test']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['results-section']} */ ;
/** @type {__VLS_StyleScopedClasses['result-group']} */ ;
/** @type {__VLS_StyleScopedClasses['result-item']} */ ;
/** @type {__VLS_StyleScopedClasses['result-header']} */ ;
/** @type {__VLS_StyleScopedClasses['score']} */ ;
/** @type {__VLS_StyleScopedClasses['source']} */ ;
/** @type {__VLS_StyleScopedClasses['result-content']} */ ;
/** @type {__VLS_StyleScopedClasses['result-group']} */ ;
/** @type {__VLS_StyleScopedClasses['result-item']} */ ;
/** @type {__VLS_StyleScopedClasses['result-header']} */ ;
/** @type {__VLS_StyleScopedClasses['score']} */ ;
/** @type {__VLS_StyleScopedClasses['result-content']} */ ;
/** @type {__VLS_StyleScopedClasses['result-group']} */ ;
/** @type {__VLS_StyleScopedClasses['result-item']} */ ;
/** @type {__VLS_StyleScopedClasses['result-header']} */ ;
/** @type {__VLS_StyleScopedClasses['score']} */ ;
/** @type {__VLS_StyleScopedClasses['type']} */ ;
/** @type {__VLS_StyleScopedClasses['result-group']} */ ;
/** @type {__VLS_StyleScopedClasses['prompt-preview']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['modal']} */ ;
/** @type {__VLS_StyleScopedClasses['upload-list']} */ ;
/** @type {__VLS_StyleScopedClasses['upload-item']} */ ;
/** @type {__VLS_StyleScopedClasses['filename']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-actions']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            documents: documents,
            loading: loading,
            debugQuery: debugQuery,
            debugResults: debugResults,
            testing: testing,
            uploadProgress: uploadProgress,
            uploadFiles: uploadFiles,
            deleteDocument: deleteDocument,
            reindexAll: reindexAll,
            testVector: testVector,
            testKG: testKG,
            testDual: testDual,
            closeUploadModal: closeUploadModal,
            formatFileSize: formatFileSize,
            formatTime: formatTime,
            getUploadStatusText: getUploadStatusText,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
