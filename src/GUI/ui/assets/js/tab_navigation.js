function rightTabButtons() {
    const tabs = document.querySelector('#right-tabs');
    if (!tabs) return [];
    return Array.from(tabs.querySelectorAll('[role="tab"]'));
}

function setQuickActionMode(mode) {
    const idsByMode = {
        project: 'quick-action-project',
        plan: 'quick-action-plan',
        lci: 'quick-action-lci',
    };
    const activeId = idsByMode[mode];

    ['quick-action-project', 'quick-action-plan', 'quick-action-lci'].forEach((id) => {
        const element = document.getElementById(id);
        if (!element) return;

        const shouldActivate = id === activeId;
        element.classList.toggle('quick-action-active', shouldActivate);
        const button = element.matches('button') ? element : element.querySelector('button');
        if (button) button.classList.toggle('quick-action-active', shouldActivate);
    });
}

function setRightTabMode(mode) {
    const visibleByMode = {
        terminal: ['终端显示'],
        project: ['终端显示', '项目初始化'],
        plan: ['终端显示', '计划输入', '计划输出', '计划修改'],
        lci: ['终端显示', 'LCI制定', 'LCI映射'],
    };
    const visibleLabels = visibleByMode[mode] || visibleByMode.terminal;

    rightTabButtons().forEach((button) => {
        const label = button.textContent.trim();
        const shouldShow = visibleLabels.some((visibleLabel) => label.includes(visibleLabel));
        button.style.display = shouldShow ? '' : 'none';
    });

    setQuickActionMode(mode);
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
        setRightTabMode('terminal');
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
window.selectPlanInputTab = () => selectRightTabByText('计划输入');
window.selectLciDesignTab = () => selectRightTabByText('LCI制定');
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

window.guiOpenLciMode = (...args) => {
    setRightTabMode('lci');
    return args;
};

window.guiClosePanel = (...args) => {
    setRightTabMode('terminal');
    selectRightTabByText('终端显示');
    return args;
};

window.guiSelectTerminal = (...args) => {
    selectRightTabByText('终端显示');
    return args;
};

initializeRightTabs();
