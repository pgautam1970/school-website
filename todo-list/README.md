# To-Do List Application

## 📋 Overview

A modern, feature-rich To-Do List application built with vanilla HTML, CSS, and JavaScript. All data is stored locally in your browser using Local Storage, so your tasks persist even after closing the browser.

## ✨ Features

### 📝 Core Features
- **Add Tasks** - Create new tasks with priority levels (Low, Medium, High)
- **Edit Tasks** - Modify task text after creation
- **Delete Tasks** - Remove individual tasks with confirmation
- **Mark Complete** - Check off completed tasks
- **Local Storage** - Tasks automatically saved to browser storage
- **Persistent Data** - Tasks survive browser refresh/restart

### 🎯 Advanced Features
- **Priority System** - Assign low, medium, or high priority to tasks
- **Task Filtering** - Filter by: All, Active, Completed, High Priority
- **Live Statistics** - See total tasks and completed count
- **Dark Mode** - Toggle between light and dark themes
- **Import/Export** - Backup and restore tasks as JSON
- **Timestamps** - Auto-add creation date/time to each task
- **Task Validation** - Prevent empty or overly long tasks
- **Responsive Design** - Works perfectly on mobile, tablet, desktop

### 🎨 UI/UX
- **Smooth Animations** - Slide-in effects for new tasks
- **Visual Feedback** - Toast notifications for all actions
- **Confirmation Modals** - Prevent accidental deletions
- **Priority Badges** - Color-coded priority indicators
- **Empty State** - Helpful message when no tasks exist
- **Accessibility** - Keyboard navigation, focus styles

## 🚀 Getting Started

### Installation

1. **Clone/Download**
   ```bash
   git clone https://github.com/pgautam1970/school-website.git
   cd school-website/todo-list
   ```

2. **Open in Browser**
   - Simply open `index.html` in your web browser
   - No build process or server needed!

### Basic Usage

1. **Add a Task**
   - Type task in input field
   - Choose priority (optional)
   - Click "+ Add Task" or press Enter

2. **Manage Tasks**
   - ✓ Check box to mark complete
   - ✏️ Click edit button to modify
   - 🗑️ Click delete button to remove

3. **Filter Tasks**
   - Click filter buttons to view specific tasks
   - See live statistics

4. **Dark Mode**
   - Click moon/sun icon in header
   - Theme preference is saved

5. **Backup Data**
   - Click "📥 Export" to download JSON file
   - Click "📤 Import" to restore from file

## 💾 Local Storage Details

Your tasks are stored in browser's Local Storage:
- **Storage Key:** `tasks`
- **Format:** JSON array
- **Backup:** Stored indefinitely until cleared
- **Privacy:** Data stays on your device

### Storage Structure
```json
[
  {
    "id": 1625097600000,
    "text": "Buy groceries",
    "priority": "high",
    "completed": false,
    "createdAt": "2026-07-07T10:30:00.000Z"
  }
]
```

## 🎨 Customization

### Colors
Edit CSS variables in `styles.css`:
```css
:root {
    --primary-color: #6366f1;
    --secondary-color: #8b5cf6;
    --success-color: #10b981;
    --danger-color: #ef4444;
    /* ... more colors ... */
}
```

### Task Limit
Modify max task text length in `app.js`:
```javascript
if (text.length > 200) {  // Change 200 to your desired limit
    this.showToast('Task is too long', 'error');
    return;
}
```

## 📱 Responsive Breakpoints

- **Desktop:** Full layout with all features
- **Tablet (640px):** Optimized grid and spacing
- **Mobile (480px):** Single column, touch-friendly

## 🔧 Technical Details

### Architecture
- **Class-based:** TodoApp class manages all functionality
- **Event-driven:** Listeners for all user interactions
- **Local-first:** All data stored locally
- **No dependencies:** Pure vanilla JavaScript

### Methods
- `handleAddTask()` - Create new task
- `handleToggleTask()` - Mark complete/incomplete
- `handleDeleteTask()` - Remove task
- `handleEditTask()` - Modify task text
- `handleFilter()` - Filter tasks
- `handleClearCompleted()` - Delete completed tasks
- `handleClearAll()` - Delete all tasks
- `handleExport()` - Export as JSON
- `handleImport()` - Import from JSON
- `saveTasks()` - Save to Local Storage
- `loadTasks()` - Load from Local Storage
- `toggleTheme()` - Switch dark/light mode

## 🎯 Features Roadmap

- [ ] Task categories/tags
- [ ] Due dates
- [ ] Recurring tasks
- [ ] Cloud sync
- [ ] Collaborative lists
- [ ] Voice input
- [ ] Push notifications

## 🐛 Browser Support

- ✅ Chrome (latest)
- ✅ Firefox (latest)
- ✅ Safari (latest)
- ✅ Edge (latest)
- ✅ Mobile browsers

## ⚙️ Performance

- **Load Time:** < 100ms
- **Memory:** < 1MB
- **Storage:** ~1KB per 10 tasks
- **Animations:** Smooth 60fps

## 🔒 Privacy & Security

- ✅ No external API calls
- ✅ No user tracking
- ✅ No ads
- ✅ All data local
- ✅ No authentication needed

## 📝 Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Enter | Add new task |
| Tab | Navigate buttons |
| Space | Toggle checkbox |

## 🆘 Troubleshooting

### Tasks not saving?
- Check if Local Storage is enabled
- Try clearing browser cache
- Use incognito/private mode to test

### Import fails?
- Ensure JSON file is valid
- Use exported file format
- Check console for errors

### Dark mode not working?
- Clear Local Storage: `localStorage.clear()`
- Refresh page

## 📄 License

Free to use and modify.

---

**Built with ❤️ for productivity**

*Last Updated: 2026-07-07*