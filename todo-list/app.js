// ============================================
// TO-DO LIST APP - JAVASCRIPT
// Local Storage & Task Management
// ============================================

class TodoApp {
    constructor() {
        // DOM Elements
        this.taskInput = document.getElementById('taskInput');
        this.prioritySelect = document.getElementById('prioritySelect');
        this.addBtn = document.getElementById('addBtn');
        this.tasksList = document.getElementById('tasksList');
        this.emptyState = document.getElementById('emptyState');
        this.filterBtns = document.querySelectorAll('.filter-btn');
        this.clearCompletedBtn = document.getElementById('clearCompletedBtn');
        this.clearAllBtn = document.getElementById('clearAllBtn');
        this.exportBtn = document.getElementById('exportBtn');
        this.importBtn = document.getElementById('importBtn');
        this.fileInput = document.getElementById('fileInput');
        this.themeToggle = document.getElementById('themeToggle');
        this.taskCountEl = document.getElementById('taskCount');
        this.completedCountEl = document.getElementById('completedCount');
        this.confirmModal = document.getElementById('confirmModal');
        this.confirmYes = document.getElementById('confirmYes');
        this.confirmNo = document.getElementById('confirmNo');
        this.toast = document.getElementById('toast');

        // State
        this.tasks = [];
        this.currentFilter = 'all';
        this.pendingConfirmAction = null;

        // Initialize
        this.init();
    }

    // ============================================
    // INITIALIZATION
    // ============================================

    init() {
        this.loadTasks();
        this.setupEventListeners();
        this.setupTheme();
        this.render();
    }

    setupEventListeners() {
        // Add task
        this.addBtn.addEventListener('click', () => this.handleAddTask());
        this.taskInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.handleAddTask();
        });

        // Filters
        this.filterBtns.forEach((btn) => {
            btn.addEventListener('click', (e) => this.handleFilter(e.target.dataset.filter));
        });

        // Actions
        this.clearCompletedBtn.addEventListener('click', () => this.handleClearCompleted());
        this.clearAllBtn.addEventListener('click', () => this.handleClearAll());
        this.exportBtn.addEventListener('click', () => this.handleExport());
        this.importBtn.addEventListener('click', () => this.fileInput.click());
        this.fileInput.addEventListener('change', (e) => this.handleImport(e));

        // Theme
        this.themeToggle.addEventListener('click', () => this.toggleTheme());

        // Modal
        this.confirmYes.addEventListener('click', () => this.confirmAction());
        this.confirmNo.addEventListener('click', () => this.closeModal());
        this.confirmModal.addEventListener('click', (e) => {
            if (e.target === this.confirmModal) this.closeModal();
        });
    }

    // ============================================
    // TASK MANAGEMENT
    // ============================================

    handleAddTask() {
        const text = this.taskInput.value.trim();
        const priority = this.prioritySelect.value;

        if (!text) {
            this.showToast('Please enter a task', 'error');
            return;
        }

        if (text.length > 200) {
            this.showToast('Task is too long (max 200 characters)', 'error');
            return;
        }

        const task = {
            id: Date.now(),
            text,
            priority,
            completed: false,
            createdAt: new Date().toISOString(),
        };

        this.tasks.unshift(task);
        this.saveTasks();
        this.render();
        this.taskInput.value = '';
        this.prioritySelect.value = 'medium';
        this.taskInput.focus();
        this.showToast('Task added successfully', 'success');
    }

    handleToggleTask(id) {
        const task = this.tasks.find((t) => t.id === id);
        if (task) {
            task.completed = !task.completed;
            this.saveTasks();
            this.render();
            this.showToast(
                task.completed ? 'Task completed!' : 'Task marked as incomplete',
                'success'
            );
        }
    }

    handleDeleteTask(id) {
        this.pendingConfirmAction = () => {
            this.tasks = this.tasks.filter((t) => t.id !== id);
            this.saveTasks();
            this.render();
            this.showToast('Task deleted', 'success');
        };
        this.openModal('Delete Task', 'Are you sure you want to delete this task?');
    }

    handleEditTask(id) {
        const task = this.tasks.find((t) => t.id === id);
        if (task) {
            const newText = prompt('Edit task:', task.text);
            if (newText !== null) {
                const trimmedText = newText.trim();
                if (trimmedText) {
                    if (trimmedText.length > 200) {
                        this.showToast('Task is too long (max 200 characters)', 'error');
                        return;
                    }
                    task.text = trimmedText;
                    this.saveTasks();
                    this.render();
                    this.showToast('Task updated', 'success');
                } else {
                    this.showToast('Task cannot be empty', 'error');
                }
            }
        }
    }

    // ============================================
    // FILTER & DISPLAY
    // ============================================

    handleFilter(filter) {
        this.currentFilter = filter;
        this.filterBtns.forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.filter === filter);
        });
        this.render();
    }

    getFilteredTasks() {
        switch (this.currentFilter) {
            case 'active':
                return this.tasks.filter((t) => !t.completed);
            case 'completed':
                return this.tasks.filter((t) => t.completed);
            case 'high':
                return this.tasks.filter((t) => t.priority === 'high');
            default:
                return this.tasks;
        }
    }

    render() {
        this.renderTasks();
        this.updateStats();
    }

    renderTasks() {
        const filtered = this.getFilteredTasks();
        this.tasksList.innerHTML = '';

        if (filtered.length === 0) {
            this.emptyState.classList.remove('hidden');
            return;
        }

        this.emptyState.classList.add('hidden');
        filtered.forEach((task) => {
            const li = this.createTaskElement(task);
            this.tasksList.appendChild(li);
        });
    }

    createTaskElement(task) {
        const li = document.createElement('li');
        li.className = `task-item ${task.completed ? 'completed' : ''}`;
        li.dataset.id = task.id;

        const date = new Date(task.createdAt);
        const dateStr = date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
        });
        const timeStr = date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
        });

        li.innerHTML = `
            <input
                type="checkbox"
                class="task-checkbox"
                ${task.completed ? 'checked' : ''}
                data-id="${task.id}"
            >
            <div class="task-content">
                <span class="task-text">${this.escapeHtml(task.text)}</span>
                <div class="task-meta">
                    <span class="priority-badge ${task.priority}">${task.priority}</span>
                    <span class="task-date">📅 ${dateStr} ${timeStr}</span>
                </div>
            </div>
            <div class="task-actions">
                <button class="task-btn edit" data-id="${task.id}" title="Edit task">✏️</button>
                <button class="task-btn delete" data-id="${task.id}" title="Delete task">🗑️</button>
            </div>
        `;

        // Event listeners
        const checkbox = li.querySelector('.task-checkbox');
        checkbox.addEventListener('change', () => this.handleToggleTask(task.id));

        const editBtn = li.querySelector('.task-btn.edit');
        editBtn.addEventListener('click', () => this.handleEditTask(task.id));

        const deleteBtn = li.querySelector('.task-btn.delete');
        deleteBtn.addEventListener('click', () => this.handleDeleteTask(task.id));

        return li;
    }

    updateStats() {
        const total = this.tasks.length;
        const completed = this.tasks.filter((t) => t.completed).length;
        this.taskCountEl.textContent = `${total} task${total !== 1 ? 's' : ''}`;
        this.completedCountEl.textContent = `${completed} completed`;
    }

    // ============================================
    // ACTIONS
    // ============================================

    handleClearCompleted() {
        const completed = this.tasks.filter((t) => t.completed).length;
        if (completed === 0) {
            this.showToast('No completed tasks to clear', 'info');
            return;
        }
        this.pendingConfirmAction = () => {
            this.tasks = this.tasks.filter((t) => !t.completed);
            this.saveTasks();
            this.render();
            this.showToast(`${completed} completed task(s) cleared`, 'success');
        };
        this.openModal(
            'Clear Completed',
            `Are you sure you want to delete ${completed} completed task(s)?`
        );
    }

    handleClearAll() {
        if (this.tasks.length === 0) {
            this.showToast('No tasks to clear', 'info');
            return;
        }
        this.pendingConfirmAction = () => {
            this.tasks = [];
            this.saveTasks();
            this.render();
            this.showToast('All tasks cleared', 'success');
        };
        this.openModal('Clear All Tasks', 'Are you sure you want to delete ALL tasks? This cannot be undone.');
    }

    handleExport() {
        if (this.tasks.length === 0) {
            this.showToast('No tasks to export', 'info');
            return;
        }

        const dataStr = JSON.stringify(this.tasks, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `tasks-${new Date().toISOString().split('T')[0]}.json`;
        link.click();
        URL.revokeObjectURL(url);
        this.showToast('Tasks exported successfully', 'success');
    }

    handleImport(event) {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const imported = JSON.parse(e.target.result);
                if (!Array.isArray(imported)) {
                    throw new Error('Invalid format');
                }

                // Validate tasks
                const isValid = imported.every(
                    (task) =>
                        typeof task.id === 'number' &&
                        typeof task.text === 'string' &&
                        typeof task.completed === 'boolean' &&
                        ['low', 'medium', 'high'].includes(task.priority)
                );

                if (!isValid) {
                    throw new Error('Invalid task format');
                }

                this.tasks = imported;
                this.saveTasks();
                this.render();
                this.showToast(`${imported.length} task(s) imported successfully`, 'success');
            } catch (error) {
                this.showToast('Invalid file format', 'error');
                console.error(error);
            }
        };
        reader.readAsText(file);
        event.target.value = '';
    }

    // ============================================
    // LOCAL STORAGE
    // ============================================

    saveTasks() {
        localStorage.setItem('tasks', JSON.stringify(this.tasks));
    }

    loadTasks() {
        const stored = localStorage.getItem('tasks');
        this.tasks = stored ? JSON.parse(stored) : [];
    }

    // ============================================
    // THEME
    // ============================================

    setupTheme() {
        const isDark = localStorage.getItem('darkMode') === 'true';
        if (isDark) {
            document.body.classList.add('dark-mode');
            this.themeToggle.textContent = '☀️';
        }
    }

    toggleTheme() {
        const isDark = document.body.classList.toggle('dark-mode');
        localStorage.setItem('darkMode', isDark);
        this.themeToggle.textContent = isDark ? '☀️' : '🌙';
        this.showToast(`Dark mode ${isDark ? 'enabled' : 'disabled'}`, 'info');
    }

    // ============================================
    // UI HELPERS
    // ============================================

    showToast(message, type = 'info') {
        this.toast.textContent = message;
        this.toast.className = `toast ${type} show`;
        setTimeout(() => {
            this.toast.classList.remove('show');
        }, 3000);
    }

    openModal(title, message) {
        document.getElementById('confirmTitle').textContent = title;
        document.getElementById('confirmMessage').textContent = message;
        this.confirmModal.classList.add('show');
    }

    closeModal() {
        this.confirmModal.classList.remove('show');
        this.pendingConfirmAction = null;
    }

    confirmAction() {
        if (this.pendingConfirmAction) {
            this.pendingConfirmAction();
        }
        this.closeModal();
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    new TodoApp();
});

console.log('✓ To-Do List App Loaded Successfully');
console.log('Features: Local Storage, Dark Mode, Import/Export, Priorities, Filters');