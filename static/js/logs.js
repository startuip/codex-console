const elements = {
    logViewer: document.getElementById('system-log-viewer'),
    logLevel: document.getElementById('log-level'),
    logKeyword: document.getElementById('log-keyword'),
    logLines: document.getElementById('log-lines'),
    applyFilterBtn: document.getElementById('apply-filter-btn'),
    refreshLogBtn: document.getElementById('refresh-log-btn'),
    cpaFilterBtn: document.getElementById('cpa-filter-btn'),
    pauseLogBtn: document.getElementById('pause-log-btn'),
    clearLogViewBtn: document.getElementById('clear-log-view-btn'),
    autoScrollToggle: document.getElementById('auto-scroll-toggle'),
    logStreamStatus: document.getElementById('log-stream-status'),
    logFilePath: document.getElementById('log-file-path'),
    logTotalLines: document.getElementById('log-total-lines'),
    logLastUpdated: document.getElementById('log-last-updated'),
};

const state = {
    nextOffset: null,
    paused: false,
    pollTimer: null,
    pollIntervalMs: 2000,
    loading: false,
    lastKeywordBeforeCpa: '',
};

document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    loadLogs({ reset: true, showToast: false });
    startPolling();
});

function initEventListeners() {
    elements.applyFilterBtn.addEventListener('click', () => {
        loadLogs({ reset: true, showToast: false });
    });

    elements.refreshLogBtn.addEventListener('click', () => {
        loadLogs({ reset: true, showToast: true });
    });

    elements.cpaFilterBtn.addEventListener('click', () => {
        const isCpaMode = elements.logKeyword.value.trim() === 'CPA Auto Refill';

        if (isCpaMode) {
            elements.logKeyword.value = state.lastKeywordBeforeCpa;
            elements.cpaFilterBtn.textContent = '只看 CPA 自动补号';
        } else {
            state.lastKeywordBeforeCpa = elements.logKeyword.value.trim();
            elements.logKeyword.value = 'CPA Auto Refill';
            elements.cpaFilterBtn.textContent = '返回全部日志';
        }

        loadLogs({ reset: true, showToast: false });
    });

    elements.pauseLogBtn.addEventListener('click', () => {
        state.paused = !state.paused;
        elements.pauseLogBtn.textContent = state.paused ? '继续滚动' : '暂停滚动';
        setStreamStatus(state.paused ? 'warning' : 'active', state.paused ? '已暂停' : '实时中');

        if (!state.paused) {
            loadLogs({ reset: false, showToast: false });
        }
    });

    elements.clearLogViewBtn.addEventListener('click', () => {
        renderLogs([]);
    });

    elements.autoScrollToggle.addEventListener('change', () => {
        if (elements.autoScrollToggle.checked) {
            scrollLogsToBottom();
        }
    });

    elements.logKeyword.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            loadLogs({ reset: true, showToast: false });
        }
    });
}

function startPolling() {
    stopPolling();
    state.pollTimer = setInterval(() => {
        if (!state.paused) {
            loadLogs({ reset: false, showToast: false });
        }
    }, state.pollIntervalMs);
}

function stopPolling() {
    if (state.pollTimer) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
    }
}

async function loadLogs({ reset = false, showToast = false } = {}) {
    if (state.loading) {
        return;
    }

    state.loading = true;

    try {
        const query = new URLSearchParams({
            lines: elements.logLines.value || '200',
            level: elements.logLevel.value || 'ALL',
        });

        const keyword = elements.logKeyword.value.trim();
        if (keyword) {
            query.set('keyword', keyword);
        }

        if (!reset && state.nextOffset !== null) {
            query.set('offset', String(state.nextOffset));
        }

        const data = await api.get(`/settings/logs?${query.toString()}`);

        if (data.error) {
            throw new Error(data.error);
        }

        const logs = Array.isArray(data.logs) ? data.logs : [];

        if (reset || state.nextOffset === null || data.reset) {
            renderLogs(logs);
        } else if (logs.length > 0) {
            appendLogs(logs);
        }

        state.nextOffset = typeof data.next_offset === 'number' ? data.next_offset : state.nextOffset;

        elements.logFilePath.textContent = data.file_path || '未配置';
        elements.logTotalLines.textContent = String(data.total_lines || 0);
        elements.logLastUpdated.textContent = formatDateTime(new Date());

        if (!state.paused) {
            setStreamStatus('active', '实时中');
        }

        if (showToast) {
            toast.success(`日志已刷新，当前匹配 ${data.total_lines || 0} 行`);
        }
    } catch (error) {
        setStreamStatus('failed', '读取失败');
        if (showToast) {
            toast.error(error.message || '读取日志失败');
        }
        console.error('读取系统日志失败:', error);
    } finally {
        state.loading = false;
    }
}

function renderLogs(logs) {
    elements.logViewer.innerHTML = '';

    if (!logs.length) {
        const line = document.createElement('div');
        line.className = 'log-line info log-empty-state';
        line.textContent = '[系统] 当前没有匹配条件的日志';
        elements.logViewer.appendChild(line);
        return;
    }

    appendLogs(logs);
}

function appendLogs(logs) {
    const emptyState = elements.logViewer.querySelector('.log-empty-state');
    if (emptyState) {
        emptyState.remove();
    }

    logs.forEach((entry) => {
        elements.logViewer.appendChild(createLogLine(entry));
    });

    if (elements.autoScrollToggle.checked) {
        scrollLogsToBottom();
    }
}

function createLogLine(entry) {
    const line = document.createElement('div');
    line.className = `log-line ${detectLogType(entry)}`;

    const match = entry.match(/^(\d{4}-\d{2}-\d{2} [\d:,]+)\s+(.*)$/);
    if (match) {
        const timestamp = document.createElement('span');
        timestamp.className = 'timestamp';
        timestamp.textContent = match[1];
        line.appendChild(timestamp);
        line.append(document.createTextNode(match[2]));
    } else {
        line.textContent = entry;
    }

    return line;
}

function detectLogType(entry) {
    const upper = String(entry || '').toUpperCase();

    if (upper.includes('[ERROR]') || upper.includes('失败') || upper.includes('异常')) {
        return 'error';
    }
    if (upper.includes('[WARNING]') || upper.includes('警告')) {
        return 'warning';
    }
    if (upper.includes('[DEBUG]')) {
        return 'debug';
    }
    if (upper.includes('成功') || upper.includes('已安排补号')) {
        return 'success';
    }
    return 'info';
}

function setStreamStatus(type, text) {
    elements.logStreamStatus.className = `status-badge ${type}`;
    elements.logStreamStatus.textContent = text;
}

function scrollLogsToBottom() {
    elements.logViewer.scrollTop = elements.logViewer.scrollHeight;
}

function formatDateTime(date) {
    return date.toLocaleString('zh-CN', {
        hour12: false,
    });
}
