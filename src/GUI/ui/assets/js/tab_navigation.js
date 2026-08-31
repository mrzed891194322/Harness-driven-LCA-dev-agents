function rightTabButtons() {
    const tabs = document.querySelector('#right-tabs');
    if (!tabs) return [];
    return Array.from(tabs.querySelectorAll('[role="tab"]'));
}

let activeRightTabMode = 'project';
let rightTabsObserver = null;
let rightTabsUpdateScheduled = false;

function setQuickActionMode(mode) {
    const activeId = mode === 'plan'
        ? 'quick-action-start-lca'
        : mode === 'project'
            ? 'quick-action-project'
            : null;
    [
        'quick-action-project',
        'quick-action-start-lca',
    ].forEach((id) => {
        const element = document.getElementById(id);
        if (!element) return;

        const shouldActivate = id === activeId;
        element.classList.toggle('quick-action-active', shouldActivate);
        const button = element.matches('button') ? element : element.querySelector('button');
        if (button) button.classList.toggle('quick-action-active', shouldActivate);
    });
}

function visibleRightTabLabels(mode) {
    const visibleByMode = {
        project: ['终端显示', '设置&初始化'],
        terminal: ['终端显示'],
        plan: ['终端显示', '计划制定'],
        running: ['终端显示'],
        result: ['终端显示', 'LCA评估结果'],
        lciReport: ['终端显示', 'LCA评估结果', '工作细节'],
        improvement: ['终端显示', 'LCA评估结果', 'LCA评估修改面板(功能开发中)'],
    };
    return visibleByMode[mode] || visibleByMode.project;
}

function applyRightTabMode(mode) {
    const visibleLabels = visibleRightTabLabels(mode);
    const seenTabIds = new Set();

    rightTabButtons().forEach((button) => {
        const label = button.textContent.trim();
        const tabId = button.dataset.tabId || label;
        const matchesMode = visibleLabels.some((visibleLabel) => label.includes(visibleLabel));
        const shouldShow = matchesMode && !seenTabIds.has(tabId);
        seenTabIds.add(tabId);
        button.style.display = shouldShow ? '' : 'none';
    });
}

function setRightTabMode(mode) {
    activeRightTabMode = mode;
    applyRightTabMode(mode);

    setQuickActionMode(mode);
}

function observeRightTabs() {
    const tabs = document.querySelector('#right-tabs');
    if (!tabs || rightTabsObserver) return;

    rightTabsObserver = new MutationObserver(() => {
        if (rightTabsUpdateScheduled) return;
        rightTabsUpdateScheduled = true;
        requestAnimationFrame(() => {
            rightTabsUpdateScheduled = false;
            applyRightTabMode(activeRightTabMode);
        });
    });
    rightTabsObserver.observe(tabs, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['role', 'data-tab-id'],
    });
}

function selectRightTabByText(label, attempt = 0) {
    const button = rightTabButtons().find(el => el.textContent.includes(label));
    if (button) {
        button.style.display = '';
        button.click();
        return;
    }

    if (attempt < 12) {
        setTimeout(() => selectRightTabByText(label, attempt + 1), 100);
    }
}

function initializeRightTabs(attempt = 0) {
    if (rightTabButtons().length > 0) {
        observeRightTabs();
        setRightTabMode('terminal');
        selectRightTabByText('终端显示');
        return;
    }

    if (attempt < 40) {
        setTimeout(() => initializeRightTabs(attempt + 1), 100);
    }
}

window.setRightTabMode = setRightTabMode;
window.setQuickActionMode = setQuickActionMode;
window.selectRightTabByText = selectRightTabByText;
window.selectProjectInitTab = () => selectRightTabByText('设置&初始化');
window.selectPlanEditorTab = () => selectRightTabByText('计划制定');
window.selectImprovementTab = () => selectRightTabByText('LCA评估修改面板(功能开发中)');
window.selectLciMappingTab = () => selectRightTabByText('工作细节');
window.selectTerminalTab = () => selectRightTabByText('终端显示');

window.guiOpenProjectMode = (...args) => {
    setRightTabMode('project');
    selectRightTabByText('设置&初始化');
    return args;
};

window.guiOpenPlanMode = (...args) => {
    setRightTabMode('plan');
    selectRightTabByText('计划制定');
    return args;
};

window.guiStartLca = (...args) => {
    setRightTabMode('running');
    selectRightTabByText('终端显示');
    return args;
};

window.guiOpenResultMode = (...args) => {
    setRightTabMode('result');
    selectRightTabByText('LCA评估结果');
    return args;
};

window.guiOpenLciReportMode = (...args) => {
    setRightTabMode('lciReport');
    selectRightTabByText('工作细节');
    return args;
};

window.guiOpenImprovementMode = (...args) => {
    setRightTabMode('improvement');
    selectRightTabByText('LCA评估修改面板(功能开发中)');
    return args;
};

window.guiCloseImprovementPanel = (...args) => {
    setRightTabMode('result');
    selectRightTabByText('LCA评估结果');
    return args;
};

window.guiCloseLciReportPanel = (...args) => {
    setRightTabMode('result');
    selectRightTabByText('LCA评估结果');
    return args;
};

window.guiClosePanel = (...args) => {
    setRightTabMode('terminal');
    selectRightTabByText('终端显示');
    return args;
};

window.guiSelectTerminal = (...args) => {
    setRightTabMode('terminal');
    selectRightTabByText('终端显示');
    return args;
};

initializeRightTabs();
