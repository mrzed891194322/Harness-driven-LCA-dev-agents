function rightTabButtons() {
    const tabs = document.querySelector('#right-tabs');
    if (!tabs) return [];
    return Array.from(tabs.querySelectorAll('[role="tab"]'));
}

let activeRightTabMode = 'project';
let rightTabsObserver = null;
let rightTabsUpdateScheduled = false;

const RIGHT_TAB_IDS = {
    project: ['terminal_tab', 'settings_init_tab'],
    terminal: ['terminal_tab'],
    plan: ['terminal_tab', 'plan_editor_tab'],
    running: ['terminal_tab'],
    result: ['terminal_tab', 'lca_result_tab'],
    lciReport: ['terminal_tab', 'lca_result_tab', 'lci_mapping_tab'],
    improvement: ['terminal_tab', 'lca_result_tab', 'lca_improvement_tab'],
};

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

function visibleRightTabIds(mode) {
    return RIGHT_TAB_IDS[mode] || RIGHT_TAB_IDS.project;
}

function tabButtonId(button) {
    return button.dataset.tabId || button.getAttribute('data-tab-id') || '';
}

function applyRightTabMode(mode) {
    const visibleIds = visibleRightTabIds(mode);
    const seenTabIds = new Set();

    rightTabButtons().forEach((button) => {
        const tabId = tabButtonId(button);
        const shouldShow = visibleIds.includes(tabId) && !seenTabIds.has(tabId);
        if (visibleIds.includes(tabId)) {
            seenTabIds.add(tabId);
        }
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

function selectRightTabById(tabId, attempt = 0) {
    const button = rightTabButtons().find((el) => tabButtonId(el) === tabId);
    if (button) {
        button.style.display = '';
        button.click();
        return;
    }

    if (attempt < 12) {
        setTimeout(() => selectRightTabById(tabId, attempt + 1), 100);
    }
}

function initializeRightTabs(attempt = 0) {
    if (rightTabButtons().length > 0) {
        observeRightTabs();
        setRightTabMode('terminal');
        selectRightTabById('terminal_tab');
        return;
    }

    if (attempt < 40) {
        setTimeout(() => initializeRightTabs(attempt + 1), 100);
    }
}

window.setRightTabMode = setRightTabMode;
window.setQuickActionMode = setQuickActionMode;
window.selectRightTabById = selectRightTabById;
window.selectProjectInitTab = () => selectRightTabById('settings_init_tab');
window.selectPlanEditorTab = () => selectRightTabById('plan_editor_tab');
window.selectImprovementTab = () => selectRightTabById('lca_improvement_tab');
window.selectLciMappingTab = () => selectRightTabById('lci_mapping_tab');
window.selectTerminalTab = () => selectRightTabById('terminal_tab');

const SETTINGS_SECTION_IDS = {
    init_check: 'settings-section-init-check',
    agent: 'settings-section-agent',
};

const AGENT_FORM_IDS = {
    codex: 'settings-agent-form-codex',
    claude: 'settings-agent-form-claude',
    opencode: 'settings-agent-form-opencode',
    pi: 'settings-agent-form-pi',
};

function applySettingsSection(key) {
    Object.entries(SETTINGS_SECTION_IDS).forEach(([itemKey, id]) => {
        const element = document.getElementById(id);
        if (!element) return;
        const shouldShow = itemKey === key;
        const hosts = [element];
        const classified = element.closest('.settings-section');
        if (classified && classified !== element) hosts.push(classified);
        hosts.forEach((host) => {
            host.classList.toggle('settings-section-hidden', !shouldShow);
            host.classList.remove('hide', 'hidden');
            host.style.removeProperty('display');
            host.removeAttribute('hidden');
        });
    });
    const scroll = document.getElementById('project-init-detail-scroll');
    if (scroll) scroll.scrollTop = 0;
}

function applyAgentForm(worker) {
    const selected = Object.prototype.hasOwnProperty.call(AGENT_FORM_IDS, worker)
        ? worker
        : 'codex';
    Object.entries(AGENT_FORM_IDS).forEach(([itemKey, id]) => {
        const element = document.getElementById(id);
        if (!element) return;
        const shouldShow = itemKey === selected;
        const hosts = [element];
        const classified = element.closest('.settings-agent-form');
        if (classified && classified !== element) hosts.push(classified);
        hosts.forEach((host) => {
            host.classList.toggle('settings-section-hidden', !shouldShow);
            host.classList.remove('hide', 'hidden');
            host.style.removeProperty('display');
            host.removeAttribute('hidden');
        });
    });
    Object.keys(AGENT_FORM_IDS).forEach((itemKey) => {
        const card = document.getElementById(`settings-agent-card-${itemKey}`);
        if (!card) return;
        const shouldActivate = itemKey === selected;
        card.classList.toggle('settings-agent-card-active', shouldActivate);
        const button = card.matches('button') ? card : card.querySelector('button');
        if (button) button.classList.toggle('settings-agent-card-active', shouldActivate);
    });
}

function currentAgentFromDropdown() {
    const root = document.getElementById('settings-agent-dropdown');
    if (!root) return 'codex';
    const input = root.querySelector('input');
    const raw = ((input && input.value) || root.textContent || '').trim().toLowerCase();
    if (Object.prototype.hasOwnProperty.call(AGENT_FORM_IDS, raw)) return raw;
    return 'codex';
}

function bindSettingsSectionHandler(key) {
    return (...args) => {
        applySettingsSection(key);
        return args;
    };
}

function bindAgentFormHandler(worker) {
    return (...args) => {
        applyAgentForm(worker);
        return args;
    };
}

window.guiSelectSettings_init_check = bindSettingsSectionHandler('init_check');
window.guiSelectSettings_agent = bindSettingsSectionHandler('agent');
window.guiOpenAgentSettings = (...args) => {
    applySettingsSection('agent');
    applyAgentForm(currentAgentFromDropdown());
    return args;
};
window.guiSelectAgentForm_codex = bindAgentFormHandler('codex');
window.guiSelectAgentForm_claude = bindAgentFormHandler('claude');
window.guiSelectAgentForm_opencode = bindAgentFormHandler('opencode');
window.guiSelectAgentForm_pi = bindAgentFormHandler('pi');

window.guiOpenProjectMode = (...args) => {
    setRightTabMode('project');
    selectRightTabById('settings_init_tab');
    applySettingsSection('init_check');
    return args;
};

window.guiOpenPlanMode = (...args) => {
    setRightTabMode('plan');
    selectRightTabById('plan_editor_tab');
    return args;
};

window.guiStartLca = (...args) => {
    setRightTabMode('running');
    selectRightTabById('terminal_tab');
    return args;
};

window.guiOpenResultMode = (...args) => {
    setRightTabMode('result');
    selectRightTabById('lca_result_tab');
    return args;
};

window.guiOpenLciReportMode = (...args) => {
    setRightTabMode('lciReport');
    selectRightTabById('lci_mapping_tab');
    return args;
};

window.guiOpenImprovementMode = (...args) => {
    setRightTabMode('improvement');
    selectRightTabById('lca_improvement_tab');
    return args;
};

window.guiCloseImprovementPanel = (...args) => {
    setRightTabMode('result');
    selectRightTabById('lca_result_tab');
    return args;
};

window.guiCloseLciReportPanel = (...args) => {
    setRightTabMode('result');
    selectRightTabById('lca_result_tab');
    return args;
};

window.guiClosePanel = (...args) => {
    setRightTabMode('terminal');
    selectRightTabById('terminal_tab');
    return args;
};

window.guiSelectTerminal = (...args) => {
    setRightTabMode('terminal');
    selectRightTabById('terminal_tab');
    return args;
};

initializeRightTabs();
