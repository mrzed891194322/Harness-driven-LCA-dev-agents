function rightTabButtons() {
    const tabs = document.querySelector('#right-tabs');
    if (!tabs) return [];
    return Array.from(tabs.querySelectorAll('[role="tab"]'));
}

let activeRightTabMode = 'project';
let rightTabsObserver = null;
let rightTabsUpdateScheduled = false;

function setQuickActionMode(mode) {
    const activeId = mode === 'plan' ? 'quick-action-start-lca' : null;
    ['quick-action-project', 'quick-action-start-lca'].forEach((id) => {
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
        project: ['项目初始化', '终端显示'],
        terminal: ['项目初始化', '终端显示'],
        plan: ['项目初始化', '终端显示', '计划制定'],
        running: ['项目初始化', '终端显示'],
        result: ['项目初始化', '终端显示', 'LCA执行结果'],
        lciReport: ['项目初始化', '终端显示', 'LCA执行结果', 'LCI映射'],
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
        setRightTabMode('project');
        selectRightTabByText('项目初始化');
        return;
    }

    if (attempt < 40) {
        setTimeout(() => initializeRightTabs(attempt + 1), 100);
    }
}

window.setRightTabMode = setRightTabMode;
window.setQuickActionMode = setQuickActionMode;
window.selectRightTabByText = selectRightTabByText;
window.selectProjectInitTab = () => selectRightTabByText('项目初始化');
window.selectPlanEditorTab = () => selectRightTabByText('计划制定');
window.selectLciMappingTab = () => selectRightTabByText('LCI映射');
window.selectTerminalTab = () => selectRightTabByText('终端显示');

window.guiOpenProjectMode = (...args) => {
    setRightTabMode('project');
    return args;
};

window.guiOpenPlanMode = (...args) => {
    setRightTabMode('plan');
    return args;
};

window.guiStartLca = (...args) => {
    setRightTabMode('running');
    selectRightTabByText('终端显示');
    return args;
};

window.guiOpenResultMode = (...args) => {
    setRightTabMode('result');
    return args;
};

window.guiOpenLciReportMode = (...args) => {
    setRightTabMode('lciReport');
    return args;
};

window.guiClosePanel = (...args) => {
    setRightTabMode('project');
    selectRightTabByText('项目初始化');
    return args;
};

window.guiSelectTerminal = (...args) => {
    setRightTabMode('terminal');
    selectRightTabByText('终端显示');
    return args;
};

initializeRightTabs();
