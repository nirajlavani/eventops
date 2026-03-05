// EventOps AI - GenZ Warm Theme

// Global error handler to catch any JS errors
window.onerror = function(message, source, lineno, colno, error) {
  console.error('Global JS Error:', message, 'at', source, lineno, colno, error);
  return false;
};

const API_BASE = '';
let currentEventId = null;
let currentEventType = null;
let currentView = 'dashboard';
let pendingExtraction = null;
let allEvents = [];
let placeholderInterval = null;
let currentPlaceholderIndex = 0;
let chatCollapseTimer = null;
let isChatExpanded = false; // Start collapsed
let conversationHistory = []; // Track conversation for context
const MAX_CONVERSATION_HISTORY = 10; // Keep last 10 messages
let isChatHovered = false;
let isAITyping = false; // Prevent collapse while AI is responding
let isChatFullscreen = false; // Fullscreen mode
const CHAT_COLLAPSE_DELAY = 5000; // 5 seconds
let collapsedPromptIndex = 0;

const COLLAPSED_PROMPTS = [
  "Any progress on your wedding planning?",
  "Share an update below",
  "Any updates on your wedding planning?",
  "What did you knock off today?",
  "Hi! How can I help you?",
  "What's on your mind today?"
];

// Rotating placeholder suggestions
const PLACEHOLDER_SUGGESTIONS = [
  'Just bought my reception suit for $800 paid with my Venture X',
  'Zoom call with venue director this Friday at 4pm',
  'Cancel the reception and add a sangeet instead',
  'Paid the photographer $2000 deposit, rest due in April',
  'Move mehndi to 6pm Saturday',
  'Booked the DJ for $1500, paid half upfront',
  'Change the haldi ceremony to 4pm',
  'Add task: finalize guest list by next week'
];

// Color assignments for items
const COLORS = ['purple', 'orange', 'green', 'yellow', 'pink'];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  loadEvents();
  setupNavigation();
  startPlaceholderRotation();
  setupCreateEventForm();
  setupChatAutoCollapse();
});

// Chat Auto-Collapse Functions
function setupChatAutoCollapse() {
  const chatInput = document.getElementById('captureInput');
  const aiAssistant = document.querySelector('.ai-assistant');
  
  if (!chatInput || !aiAssistant) return;
  
  // Create the collapsed prompt element
  createCollapsedPrompt(aiAssistant);
  
  // Start collapsed
  aiAssistant.classList.add('collapsed');
  isChatExpanded = false;
  showCollapsedPrompt();
  
  // Start the collapse timer
  startChatCollapseTimer();
  
  // Expand on focus
  chatInput.addEventListener('focus', () => {
    expandChat();
    resetChatCollapseTimer();
  });
  
  // Reset timer on any input
  chatInput.addEventListener('input', () => {
    resetChatCollapseTimer();
  });
  
  // Reset timer on click anywhere in the chat
  aiAssistant.addEventListener('click', () => {
    expandChat();
    resetChatCollapseTimer();
  });
  
  // Prevent collapse while hovering
  aiAssistant.addEventListener('mouseenter', () => {
    isChatHovered = true;
    clearChatCollapseTimer();
  });
  
  aiAssistant.addEventListener('mouseleave', () => {
    isChatHovered = false;
    resetChatCollapseTimer();
  });
  
  // Start collapse timer when focus is lost (with delay)
  chatInput.addEventListener('blur', () => {
    resetChatCollapseTimer();
  });
  
  // Toggle fullscreen when clicking on chat header
  const chatHeader = aiAssistant.querySelector('.chat-header');
  if (chatHeader) {
    chatHeader.addEventListener('click', (e) => {
      // Don't toggle if clicking on buttons inside header
      if (e.target.tagName === 'BUTTON' || e.target.closest('button')) {
        return;
      }
      toggleFullscreen();
    });
  }
}

function createCollapsedPrompt(aiAssistant) {
  const promptEl = document.createElement('div');
  promptEl.className = 'collapsed-chat-prompt';
  promptEl.id = 'collapsedChatPrompt';
  promptEl.textContent = COLLAPSED_PROMPTS[0];
  aiAssistant.parentNode.insertBefore(promptEl, aiAssistant);
}

function showCollapsedPrompt() {
  const promptEl = document.getElementById('collapsedChatPrompt');
  if (promptEl) {
    promptEl.style.display = 'block';
    promptEl.style.opacity = '1';
  }
}

function hideCollapsedPrompt() {
  const promptEl = document.getElementById('collapsedChatPrompt');
  if (promptEl) {
    promptEl.style.opacity = '0';
    setTimeout(() => {
      promptEl.style.display = 'none';
    }, 200);
  }
}

function rotateCollapsedPrompt() {
  collapsedPromptIndex = (collapsedPromptIndex + 1) % COLLAPSED_PROMPTS.length;
  const promptEl = document.getElementById('collapsedChatPrompt');
  if (promptEl) {
    promptEl.textContent = COLLAPSED_PROMPTS[collapsedPromptIndex];
  }
}

function startChatCollapseTimer() {
  clearChatCollapseTimer();
  chatCollapseTimer = setTimeout(() => {
    collapseChat();
  }, CHAT_COLLAPSE_DELAY);
}

function clearChatCollapseTimer() {
  if (chatCollapseTimer) {
    clearTimeout(chatCollapseTimer);
    chatCollapseTimer = null;
  }
}

function resetChatCollapseTimer() {
  startChatCollapseTimer();
}

function collapseChat() {
  // Don't collapse if mouse is hovering, AI is typing, or fullscreen
  if (isChatHovered || isAITyping || isChatFullscreen) {
    return;
  }
  
  const aiAssistant = document.querySelector('.ai-assistant');
  if (aiAssistant && isChatExpanded) {
    aiAssistant.classList.add('collapsed');
    isChatExpanded = false;
    rotateCollapsedPrompt();
    showCollapsedPrompt();
  }
}

function expandChat() {
  const aiAssistant = document.querySelector('.ai-assistant');
  if (aiAssistant && !isChatExpanded) {
    aiAssistant.classList.remove('collapsed');
    isChatExpanded = true;
    hideCollapsedPrompt();
  }
}

function toggleFullscreen() {
  const aiAssistant = document.querySelector('.ai-assistant');
  if (!aiAssistant) return;
  
  // First make sure chat is expanded
  if (!isChatExpanded) {
    expandChat();
  }
  
  isChatFullscreen = !isChatFullscreen;
  
  if (isChatFullscreen) {
    aiAssistant.classList.add('fullscreen');
    clearChatCollapseTimer(); // Don't collapse when fullscreen
  } else {
    aiAssistant.classList.remove('fullscreen');
    resetChatCollapseTimer();
  }
}

function setupCreateEventForm() {
  const form = document.getElementById('createEventForm');
  if (form) {
    form.addEventListener('submit', function(e) {
      console.log('Form submit event triggered');
      createEvent(e);
    });
  }
}

// Placeholder rotation
function startPlaceholderRotation() {
  const input = document.getElementById('captureInput');
  if (!input) return;
  
  input.placeholder = PLACEHOLDER_SUGGESTIONS[0];
  
  placeholderInterval = setInterval(() => {
    currentPlaceholderIndex = (currentPlaceholderIndex + 1) % PLACEHOLDER_SUGGESTIONS.length;
    input.placeholder = PLACEHOLDER_SUGGESTIONS[currentPlaceholderIndex];
  }, 4000);
}

function clearPlaceholder() {
  if (placeholderInterval) {
    clearInterval(placeholderInterval);
    placeholderInterval = null;
  }
}

function restorePlaceholder() {
  const input = document.getElementById('captureInput');
  if (input && input.value === '') {
    startPlaceholderRotation();
  }
}

// Navigation
function setupNavigation() {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      switchView(item.dataset.view);
    });
  });
}

function switchView(view) {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.view === view);
  });
  
  document.querySelectorAll('.view-content').forEach(content => {
    content.classList.add('hidden');
  });
  
  const viewEl = document.getElementById(`view-${view}`);
  if (viewEl) viewEl.classList.remove('hidden');
  currentView = view;
  
  refreshCurrentView();
}

function refreshCurrentView() {
  switch (currentView) {
    case 'dashboard': 
      if (currentEventId) loadDashboard(); 
      break;
    case 'events': loadEventsList(); break;
    case 'vendors': loadVendors(); break;
    case 'payments': loadPayments(); break;
    case 'tasks': loadTasks(); break;
    case 'calendar': loadCalendar(); break;
  }
}

// Events
let eventSelectorInitialized = false;

async function loadEvents() {
  const welcomeState = document.getElementById('welcomeState');
  const dashboardContent = document.getElementById('dashboardContent');
  const selector = document.getElementById('eventSelector');
  const sidebarSelector = document.getElementById('sidebarEventSelector');
  
  try {
    const response = await fetch(`${API_BASE}/api/events`);
    allEvents = await response.json();
    
    selector.innerHTML = '';
    
    if (allEvents.length === 0) {
      // Show welcome state, hide dashboard content
      if (welcomeState) welcomeState.style.display = 'flex';
      if (dashboardContent) dashboardContent.style.display = 'none';
      if (sidebarSelector) sidebarSelector.style.display = 'none';
      selector.innerHTML = '<option value="">No events yet</option>';
      currentEventId = null;
      currentEventType = null;
    } else {
      // Hide welcome state, show dashboard content
      if (welcomeState) welcomeState.style.display = 'none';
      if (dashboardContent) dashboardContent.style.display = 'block';
      if (sidebarSelector) sidebarSelector.style.display = 'flex';
      
      allEvents.forEach(event => {
        const option = document.createElement('option');
        option.value = event.id;
        option.dataset.type = event.event_type;
        option.textContent = event.name;
        selector.appendChild(option);
      });
      
      // Keep current selection if still valid, otherwise select first
      const stillValid = currentEventId && allEvents.find(e => e.id === currentEventId);
      if (!stillValid) {
        currentEventId = allEvents[0].id;
        currentEventType = allEvents[0].event_type;
      }
      selector.value = currentEventId;
      loadDashboard();
    }
    
    // Only add event listener once
    if (!eventSelectorInitialized) {
      selector.addEventListener('change', (e) => {
        const selected = allEvents.find(ev => ev.id === e.target.value);
        if (selected) {
          currentEventId = selected.id;
          currentEventType = selected.event_type;
          refreshCurrentView();
        }
      });
      eventSelectorInitialized = true;
    }
  } catch (error) {
    console.error('Failed to load events:', error);
    // Show welcome state on error as fallback
    if (welcomeState) welcomeState.style.display = 'flex';
    if (dashboardContent) dashboardContent.style.display = 'none';
    if (sidebarSelector) sidebarSelector.style.display = 'none';
    showToast('Failed to load events', 'error');
  }
}

// Dashboard
async function loadDashboard() {
  if (!currentEventId) return;
  
  try {
    const [dashResponse, tasksResponse, calendarResponse, paymentsResponse] = await Promise.all([
      fetch(`${API_BASE}/api/events/${currentEventId}/dashboard`),
      fetch(`${API_BASE}/api/events/${currentEventId}/tasks`),
      fetch(`${API_BASE}/api/events/${currentEventId}/calendar`),
      fetch(`${API_BASE}/api/events/${currentEventId}/payments`)
    ]);
    
    const dashboard = await dashResponse.json();
    const tasks = await tasksResponse.json();
    const calendar = await calendarResponse.json();
    const payments = await paymentsResponse.json();
    
    // Total Paid
    const totalPaid = parseFloat(dashboard.financial_summary?.total_paid || 0);
    document.getElementById('stat-paid').textContent = `$${formatNumber(totalPaid)}`;
    
    // Total Pending
    const totalPending = parseFloat(dashboard.financial_summary?.total_upcoming || 0);
    document.getElementById('stat-pending').textContent = `$${formatNumber(totalPending)}`;
    
    // Pending Tasks
    const pendingTasks = tasks.filter(t => t.status !== 'completed').length;
    document.getElementById('stat-tasks').textContent = pendingTasks;
    
    // Upcoming
    renderUpcomingItems(payments, calendar);
    
    // Recent Payments
    renderRecentPayments(payments.slice(0, 4));
    
    // Open Tasks
    renderOpenTasks(tasks.filter(t => t.status !== 'completed').slice(0, 4));
    
  } catch (error) {
    console.error('Failed to load dashboard:', error);
  }
}

function renderUpcomingItems(payments, calendar) {
  const container = document.getElementById('stat-upcoming');
  const items = [];
  
  payments.forEach(p => {
    if (p.due_date && !p.paid_date) {
      items.push({
        title: p.notes?.split(';')[0] || 'Payment due',
        type: 'payment',
        date: new Date(p.due_date)
      });
    }
  });
  
  calendar.forEach(c => {
    if (c.event_date) {
      items.push({
        title: c.title,
        type: 'event',
        date: new Date(c.event_date)
      });
    }
  });
  
  items.sort((a, b) => a.date - b.date);
  const upcoming = items.filter(i => i.date >= new Date()).slice(0, 2);
  
  if (upcoming.length === 0) {
    container.innerHTML = '<div class="upcoming-empty">No upcoming items</div>';
    return;
  }
  
  container.innerHTML = upcoming.map(item => `
    <div class="upcoming-item">
      <span class="upcoming-title">${escapeHtml(item.title)}</span>
      <span class="upcoming-badge">${item.type}</span>
      <span class="upcoming-date">${formatShortDate(item.date)}</span>
    </div>
  `).join('');
}

function renderRecentPayments(payments) {
  const container = document.getElementById('recentPayments');
  
  if (payments.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon"><i class="fas fa-credit-card"></i></div>
        <p>No payments yet</p>
      </div>
    `;
    return;
  }
  
  container.innerHTML = payments.map((p, i) => `
    <div class="item-row">
      <div class="item-icon ${COLORS[i % COLORS.length]}">
        <i class="fas fa-dollar-sign"></i>
      </div>
      <div class="item-content">
        <div class="item-title">$${formatNumber(parseFloat(p.amount))}</div>
        <div class="item-subtitle">${p.paid_date ? formatShortDate(new Date(p.paid_date)) : 'Pending'}</div>
      </div>
      ${p.paid_date ? '<span class="tag tag-success">Paid</span>' : '<span class="tag tag-warning">Due</span>'}
    </div>
  `).join('');
}

function renderOpenTasks(tasks) {
  const container = document.getElementById('openTasks');
  
  if (tasks.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon"><i class="fas fa-check-circle"></i></div>
        <p>All caught up!</p>
      </div>
    `;
    return;
  }
  
  container.innerHTML = tasks.map((t, i) => `
    <div class="item-row">
      <div class="item-icon ${COLORS[(i + 2) % COLORS.length]}">
        <i class="fas fa-circle" style="font-size: 0.5rem;"></i>
      </div>
      <div class="item-content">
        <div class="item-title">${escapeHtml(t.title)}</div>
        ${t.due_date ? `<div class="item-subtitle">Due: ${formatShortDate(new Date(t.due_date))}</div>` : ''}
      </div>
      <span class="tag ${getPriorityTagClass(t.priority)}">${t.priority}</span>
    </div>
  `).join('');
}

// Events List
async function loadEventsList() {
  try {
    const response = await fetch(`${API_BASE}/api/events`);
    const events = await response.json();
    const container = document.getElementById('eventsList');
    
    if (events.length === 0) {
      container.innerHTML = `
        <div class="section-card">
          <div class="empty-state">
            <div class="empty-state-icon"><i class="fas fa-calendar-plus"></i></div>
            <p>Create your first event to get started!</p>
            <button class="btn btn-primary mt-4" onclick="showCreateEventModal()">
              <i class="fas fa-plus"></i> Create Event
            </button>
          </div>
        </div>
      `;
      return;
    }
    
    container.innerHTML = events.map((event, i) => renderEventCard(event, i)).join('');
  } catch (error) {
    console.error('Failed to load events:', error);
  }
}

function renderEventCard(event, index) {
  const dateDisplay = event.start_date && event.end_date 
    ? formatDateRange(event.start_date, event.end_date)
    : event.event_date 
      ? formatShortDate(new Date(event.event_date))
      : 'No date';
  
  const locationDisplay = event.location_city || event.location || 'No location';
  const hasSubEvents = event.sub_events && event.sub_events.length > 0;
  
  let subEventsHtml = '';
  if (hasSubEvents) {
    subEventsHtml = `
      <div class="event-card-details" id="event-details-${event.id}">
        <div class="sub-events-header">
          <i class="fas fa-list"></i> Sub-Events Schedule
        </div>
        <div class="sub-events-table">
          ${event.sub_events.map(se => `
            <div class="sub-event-item">
              <div class="sub-event-info">
                <span class="sub-event-name">${escapeHtml(se.name)}</span>
                <span class="sub-event-datetime">
                  ${formatShortDate(new Date(se.date))}${se.start_time ? ` at ${formatTime(se.start_time)}` : ''}
                </span>
              </div>
              ${se.location ? `<span class="sub-event-location"><i class="fas fa-map-marker-alt"></i> ${escapeHtml(se.location)}</span>` : ''}
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }
  
  return `
    <div class="event-card ${hasSubEvents ? 'expandable' : ''}" id="event-card-${event.id}">
      <div class="event-card-clickable" onclick="handleEventCardClick(event, '${event.id}', '${event.event_type}')">
        <div class="event-card-header">
          <div class="event-card-icon ${COLORS[index % COLORS.length]}">
            <i class="fas fa-calendar-alt"></i>
          </div>
          <div class="event-card-header-right">
            <span class="tag tag-default">${formatEventType(event.event_type)}</span>
            ${hasSubEvents ? `<i class="fas fa-chevron-down expand-icon" id="expand-icon-${event.id}"></i>` : ''}
          </div>
        </div>
        <div class="event-card-title">${escapeHtml(event.name)}</div>
        <div class="event-card-summary">
          <div class="event-card-meta">
            <i class="fas fa-calendar"></i> ${dateDisplay}
          </div>
          <div class="event-card-meta">
            <i class="fas fa-map-marker-alt"></i> ${escapeHtml(locationDisplay)}
          </div>
        </div>
        ${hasSubEvents ? `<div class="event-card-badge">${event.sub_events.length} sub-event${event.sub_events.length > 1 ? 's' : ''}</div>` : ''}
      </div>
      ${subEventsHtml}
    </div>
  `;
}

function handleEventCardClick(e, eventId, eventType) {
  const card = document.getElementById(`event-card-${eventId}`);
  const details = document.getElementById(`event-details-${eventId}`);
  const expandIcon = document.getElementById(`expand-icon-${eventId}`);
  
  if (e.target.closest('.expand-icon') || (details && !card.classList.contains('expanded'))) {
    e.stopPropagation();
    toggleEventCard(eventId);
  } else if (!details || card.classList.contains('expanded')) {
    selectEvent(eventId, eventType);
  }
}

function toggleEventCard(eventId) {
  const card = document.getElementById(`event-card-${eventId}`);
  const details = document.getElementById(`event-details-${eventId}`);
  const expandIcon = document.getElementById(`expand-icon-${eventId}`);
  
  if (!details) return;
  
  card.classList.toggle('expanded');
  
  if (card.classList.contains('expanded')) {
    details.style.maxHeight = details.scrollHeight + 'px';
    if (expandIcon) expandIcon.style.transform = 'rotate(180deg)';
  } else {
    details.style.maxHeight = '0';
    if (expandIcon) expandIcon.style.transform = 'rotate(0)';
  }
}

function formatTime(timeStr) {
  if (!timeStr) return '';
  const parts = timeStr.split(':');
  const hours = parseInt(parts[0]);
  const minutes = parts[1];
  const ampm = hours >= 12 ? 'PM' : 'AM';
  const hour12 = hours % 12 || 12;
  return `${hour12}:${minutes} ${ampm}`;
}

function selectEvent(eventId, eventType) {
  currentEventId = eventId;
  currentEventType = eventType;
  document.getElementById('eventSelector').value = eventId;
  switchView('dashboard');
}

// Vendors
async function loadVendors() {
  const container = document.getElementById('vendorsList');
  
  if (!currentEventId) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon"><i class="fas fa-store"></i></div>
        <p>Create an event first to add vendors</p>
        <button class="btn btn-primary mt-4" onclick="showCreateEventModal()">
          <i class="fas fa-plus"></i> Create Event
        </button>
      </div>
    `;
    return;
  }
  
  try {
    const response = await fetch(`${API_BASE}/api/events/${currentEventId}/vendors`);
    const vendors = await response.json();
    
    if (vendors.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon"><i class="fas fa-store"></i></div>
          <p>No vendors yet. Tell me about your vendors!</p>
        </div>
      `;
      return;
    }
    
    container.innerHTML = vendors.map((v, i) => `
      <div class="item-row">
        <div class="avatar avatar-${COLORS[i % COLORS.length]}">
          <i class="${getVendorIcon(v.category)}"></i>
        </div>
        <div class="item-content">
          <div class="item-title">${escapeHtml(v.name)}</div>
          <div class="item-subtitle">${escapeHtml(v.category || 'Other')}</div>
        </div>
        ${v.contact_info ? `<span class="item-subtitle">${escapeHtml(v.contact_info)}</span>` : ''}
      </div>
    `).join('');
  } catch (error) {
    console.error('Failed to load vendors:', error);
  }
}

// Payments
async function loadPayments() {
  const container = document.getElementById('paymentsList');
  
  if (!currentEventId) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon"><i class="fas fa-credit-card"></i></div>
        <p>Create an event first to track payments</p>
        <button class="btn btn-primary mt-4" onclick="showCreateEventModal()">
          <i class="fas fa-plus"></i> Create Event
        </button>
      </div>
    `;
    return;
  }
  
  try {
    const response = await fetch(`${API_BASE}/api/events/${currentEventId}/payments`);
    const payments = await response.json();
    
    if (payments.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon"><i class="fas fa-credit-card"></i></div>
          <p>No payments recorded yet</p>
        </div>
      `;
      return;
    }
    
    container.innerHTML = payments.map((p, i) => `
      <div class="item-row">
        <div class="item-icon ${COLORS[i % COLORS.length]}">
          <i class="fas fa-dollar-sign"></i>
        </div>
        <div class="item-content">
          <div class="item-title">$${formatNumber(parseFloat(p.amount))}</div>
          <div class="item-subtitle">
            ${p.paid_date ? `Paid: ${formatShortDate(new Date(p.paid_date))}` : ''}
            ${p.due_date ? ` · Due: ${formatShortDate(new Date(p.due_date))}` : ''}
          </div>
        </div>
        ${p.paid_date ? '<span class="tag tag-success">Paid</span>' : '<span class="tag tag-warning">Pending</span>'}
      </div>
    `).join('');
  } catch (error) {
    console.error('Failed to load payments:', error);
  }
}

// Tasks
async function loadTasks() {
  const container = document.getElementById('allTasksList');
  
  if (!currentEventId) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon"><i class="fas fa-tasks"></i></div>
        <p>Create an event first to manage tasks</p>
        <button class="btn btn-primary mt-4" onclick="showCreateEventModal()">
          <i class="fas fa-plus"></i> Create Event
        </button>
      </div>
    `;
    return;
  }
  
  try {
    const response = await fetch(`${API_BASE}/api/events/${currentEventId}/tasks`);
    const tasks = await response.json();
    
    if (tasks.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon"><i class="fas fa-tasks"></i></div>
          <p>No tasks yet</p>
        </div>
      `;
      return;
    }
    
    container.innerHTML = tasks.map((t, i) => `
      <div class="item-row">
        <div class="item-icon ${t.status === 'completed' ? 'green' : COLORS[(i + 1) % COLORS.length]}">
          <i class="fas ${t.status === 'completed' ? 'fa-check' : 'fa-circle'}" style="font-size: ${t.status === 'completed' ? '1rem' : '0.5rem'};"></i>
        </div>
        <div class="item-content">
          <div class="item-title" style="${t.status === 'completed' ? 'text-decoration: line-through; opacity: 0.5;' : ''}">${escapeHtml(t.title)}</div>
          ${t.due_date ? `<div class="item-subtitle">Due: ${formatShortDate(new Date(t.due_date))}</div>` : ''}
        </div>
        <span class="tag ${getPriorityTagClass(t.priority)}">${t.priority}</span>
      </div>
    `).join('');
  } catch (error) {
    console.error('Failed to load tasks:', error);
  }
}

// Calendar
async function loadCalendar() {
  const container = document.getElementById('calendarList');
  
  if (!currentEventId) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon"><i class="fas fa-calendar-day"></i></div>
        <p>Create an event first to add calendar items</p>
        <button class="btn btn-primary mt-4" onclick="showCreateEventModal()">
          <i class="fas fa-plus"></i> Create Event
        </button>
      </div>
    `;
    return;
  }
  
  try {
    const response = await fetch(`${API_BASE}/api/events/${currentEventId}/calendar`);
    const events = await response.json();
    
    if (events.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon"><i class="fas fa-calendar-day"></i></div>
          <p>No calendar events yet</p>
        </div>
      `;
      return;
    }
    
    container.innerHTML = events.map((e, i) => `
      <div class="item-row">
        <div class="item-icon ${COLORS[i % COLORS.length]}">
          <i class="fas fa-calendar-day"></i>
        </div>
        <div class="item-content">
          <div class="item-title">${escapeHtml(e.title)}</div>
          <div class="item-subtitle">${formatShortDate(new Date(e.event_date))}${e.event_time ? ` at ${e.event_time}` : ''}</div>
        </div>
        ${e.location ? `<span class="item-subtitle"><i class="fas fa-map-marker-alt"></i> ${escapeHtml(e.location)}</span>` : ''}
      </div>
    `).join('');
  } catch (error) {
    console.error('Failed to load calendar:', error);
  }
}

// Chat / Capture (Persistent)
function handleCaptureKeypress(event) {
  if (event.key === 'Enter') submitCapture();
}

async function submitCapture() {
  const input = document.getElementById('captureInput');
  const text = input.value.trim();
  
  if (!text) return;
  if (!currentEventId) {
    showToast('Please create an event first', 'error');
    return;
  }
  
  // Keep chat expanded during conversation
  expandChat();
  resetChatCollapseTimer();
  
  addMessage(text, 'user');
  input.value = '';
  clearPlaceholder();
  
  // Track user message in conversation history
  addToConversationHistory('user', text);
  
  showTypingIndicator();
  
  try {
    const response = await fetch(`${API_BASE}/api/events/${currentEventId}/capture/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        text,
        conversation_history: conversationHistory
      })
    });
    
    const result = await response.json();
    hideTypingIndicator();
    
    // Log referenced records for debugging (if available)
    if (result.referenced_records && result.referenced_records.length > 0) {
      console.log('Referenced records:', result.referenced_records);
    }
    
    // Use response_mode if available for cleaner routing
    const responseMode = result.response_mode || 'confirm';
    
    // Handle error response mode
    if (responseMode === 'error' || result.intent === 'unknown') {
      const msg = result.assistant_message || "I couldn't understand that. Try something like 'Paid decorator $500' or 'Add task to book DJ'.";
      addMessage(msg, 'ai');
      addToConversationHistory('assistant', msg);
      return;
    }
    
    // Handle answer response mode (queries)
    if (responseMode === 'answer' || result.intent === 'query') {
      const msg = result.assistant_message || result.query_results?.natural_response || "Here's what I found.";
      addMessage(msg, 'ai');
      addToConversationHistory('assistant', msg);
      return;
    }
    
    // Handle clarify response mode or conversation intent
    if (responseMode === 'clarify' || result.intent === 'conversation') {
      const msg = result.assistant_message || "I understand. Let me know if you need anything else!";
      addMessage(msg, 'ai');
      addToConversationHistory('assistant', msg);
      return;
    }
    
    // Handle follow-up question - show extraction with question
    if (result.follow_up_question) {
      pendingExtraction = result;
      if (result.assistant_message) {
        showExtractionWithMessage(result);
      } else {
        showExtractionResultWithFollowUp(result);
      }
      return;
    }
    
    // Handle execute response mode - auto-confirm
    if (responseMode === 'execute' || (result.assistant_message && !result.needs_confirmation)) {
      addMessage(result.assistant_message || 'Done!', 'ai');
      addToConversationHistory('assistant', result.assistant_message || 'Done!');
      pendingExtraction = result;
      await autoConfirmExtraction();
      return;
    }
    
    // Show standard extraction preview with optional assistant message (confirm mode)
    pendingExtraction = result;
    if (result.assistant_message) {
      showExtractionWithMessage(result);
    } else {
      showExtractionResult(result);
    }
  } catch (error) {
    hideTypingIndicator();
    addMessage('Something went wrong. Please try again.', 'ai');
    console.error('Capture error:', error);
  }
}

function addToConversationHistory(role, content) {
  conversationHistory.push({ role, content });
  // Keep only the last N messages
  if (conversationHistory.length > MAX_CONVERSATION_HISTORY) {
    conversationHistory = conversationHistory.slice(-MAX_CONVERSATION_HISTORY);
  }
}

function showExtractionWithMessage(result) {
  let html = `<div class="extraction-with-message">`;
  html += `<div class="assistant-message">${result.assistant_message}</div>`;
  
  if (result.needs_confirmation) {
    html += '<div class="extraction-preview" style="margin-top: 12px;">';
    for (const [key, value] of Object.entries(result.data)) {
      if (value !== null && value !== undefined && value !== '') {
        const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        html += `<div class="extraction-field">
          <span class="extraction-label">${label}</span>
          <span class="extraction-value">${value}</span>
        </div>`;
      }
    }
    html += '</div>';
    
    if (result.follow_up_question) {
      html += `<div class="follow-up-question">
        <i class="fas fa-question-circle"></i>
        <span>${result.follow_up_question}</span>
      </div>`;
    }
    
    html += `<div class="confirm-actions">
      <button class="btn btn-secondary btn-sm" onclick="cancelExtraction()">Cancel</button>
      <button class="btn btn-primary btn-sm" onclick="confirmExtraction()">Save</button>
    </div>`;
  }
  
  html += `</div>`;
  addMessage(html, 'ai', true);
  addToConversationHistory('assistant', result.assistant_message);
}

async function autoConfirmExtraction() {
  if (!pendingExtraction) return;
  
  try {
    const response = await fetch(`${API_BASE}/api/events/${currentEventId}/capture/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        log_id: pendingExtraction.log_id,
        intent: pendingExtraction.intent,
        action: pendingExtraction.action || 'create',
        reference_id: pendingExtraction.reference_id,
        data: pendingExtraction.data
      })
    });
    
    const confirmResult = await response.json();
    
    if (confirmResult.success) {
      refreshCurrentView();
    }
    
    pendingExtraction = null;
  } catch (error) {
    console.error('Auto-confirm error:', error);
  }
}

function showExtractionResult(result) {
  let html = '';
  
  if (result.intent === 'sub_event_update') {
    html = renderSubEventUpdatePreview(result);
  } else if (result.intent === 'event_update') {
    html = renderEventUpdatePreview(result);
  } else {
    html = renderStandardExtractionPreview(result);
  }
  
  addMessage(html, 'ai', true);
}

function showQueryResults(queryResults) {
  let html = `<div class="query-response">`;
  html += `<div class="query-summary">${queryResults.natural_response}</div>`;
  
  const results = queryResults.results;
  
  // Payments
  if (results.payments && results.payments.length > 0) {
    html += `<div class="query-section">
      <div class="query-section-title"><i class="fas fa-credit-card"></i> Payments</div>
      <div class="query-items">`;
    for (const p of results.payments) {
      const vendor = p.vendor_name || 'Unknown vendor';
      const amount = p.amount ? `$${p.amount.toLocaleString()}` : '';
      const date = p.paid_date ? new Date(p.paid_date).toLocaleDateString() : '';
      html += `<div class="query-item">
        <div class="query-item-main">
          <span class="query-item-title">${vendor}</span>
          <span class="query-item-value">${amount}</span>
        </div>
        <div class="query-item-meta">${date}${p.method ? ' • ' + p.method : ''}</div>
      </div>`;
    }
    html += `</div></div>`;
  }
  
  // Tasks
  if (results.tasks && results.tasks.length > 0) {
    html += `<div class="query-section">
      <div class="query-section-title"><i class="fas fa-tasks"></i> Tasks</div>
      <div class="query-items">`;
    for (const t of results.tasks) {
      const status = t.status || 'pending';
      const statusClass = status === 'completed' ? 'status-complete' : 'status-pending';
      const dueDate = t.due_date ? new Date(t.due_date).toLocaleDateString() : '';
      html += `<div class="query-item">
        <div class="query-item-main">
          <span class="query-item-title">${t.title}</span>
          <span class="query-item-badge ${statusClass}">${status}</span>
        </div>
        ${dueDate ? `<div class="query-item-meta">Due: ${dueDate}</div>` : ''}
      </div>`;
    }
    html += `</div></div>`;
  }
  
  // Calendar Events
  if (results.calendar_events && results.calendar_events.length > 0) {
    html += `<div class="query-section">
      <div class="query-section-title"><i class="fas fa-calendar"></i> Upcoming Events</div>
      <div class="query-items">`;
    for (const e of results.calendar_events) {
      const eventDate = e.event_date ? new Date(e.event_date).toLocaleDateString() : '';
      const eventTime = e.event_time || '';
      html += `<div class="query-item">
        <div class="query-item-main">
          <span class="query-item-title">${e.title}</span>
        </div>
        <div class="query-item-meta">${eventDate}${eventTime ? ' at ' + eventTime : ''}${e.location ? ' • ' + e.location : ''}</div>
      </div>`;
    }
    html += `</div></div>`;
  }
  
  // Vendors
  if (results.vendors && results.vendors.length > 0) {
    html += `<div class="query-section">
      <div class="query-section-title"><i class="fas fa-store"></i> Vendors</div>
      <div class="query-items">`;
    for (const v of results.vendors) {
      html += `<div class="query-item">
        <div class="query-item-main">
          <span class="query-item-title">${v.name}</span>
          ${v.category ? `<span class="query-item-badge">${v.category}</span>` : ''}
        </div>
        ${v.contact_info ? `<div class="query-item-meta">${v.contact_info}</div>` : ''}
      </div>`;
    }
    html += `</div></div>`;
  }
  
  html += `</div>`;
  addMessage(html, 'ai', true);
}

function showExtractionResultWithFollowUp(result) {
  let html = `<div class="extraction-with-followup">`;
  html += `<div style="margin-bottom: 12px;">Got it! Here's what I extracted:</div>`;
  html += '<div class="extraction-preview">';
  
  for (const [key, value] of Object.entries(result.data)) {
    if (value !== null && value !== undefined && value !== '') {
      const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
      html += `<div class="extraction-field">
        <span class="extraction-label">${label}</span>
        <span class="extraction-value">${value}</span>
      </div>`;
    }
  }
  
  html += '</div>';
  
  // Show the follow-up question
  html += `<div class="follow-up-question">
    <i class="fas fa-question-circle"></i>
    <span>${result.follow_up_question}</span>
  </div>`;
  
  html += `<div class="confirm-actions">
    <button class="btn btn-secondary btn-sm" onclick="cancelExtraction()">Cancel</button>
    <button class="btn btn-primary btn-sm" onclick="confirmExtraction()">Save Anyway</button>
  </div>`;
  
  html += `</div>`;
  addMessage(html, 'ai', true);
}

function renderSubEventUpdatePreview(result) {
  const data = result.data;
  const action = data.action || 'update';
  
  let actionDescription = '';
  let iconClass = '';
  
  switch (action) {
    case 'add':
      actionDescription = `Add new sub-event "${data.new_name || 'New Sub-Event'}"`;
      iconClass = 'fa-plus-circle';
      break;
    case 'cancel':
      actionDescription = `Cancel sub-event "${data.sub_event_name}"`;
      iconClass = 'fa-times-circle';
      break;
    case 'reschedule':
      actionDescription = `Reschedule "${data.sub_event_name}"`;
      iconClass = 'fa-clock';
      break;
    case 'update':
      if (data.new_name) {
        actionDescription = `Change "${data.sub_event_name}" to "${data.new_name}"`;
      } else {
        actionDescription = `Update "${data.sub_event_name}"`;
      }
      iconClass = 'fa-edit';
      break;
    default:
      actionDescription = `Update sub-event`;
      iconClass = 'fa-edit';
  }
  
  let html = `<div class="extraction-header">
    <i class="fas ${iconClass}" style="color: var(--primary);"></i>
    <span>${actionDescription}</span>
  </div>`;
  
  html += '<div class="extraction-preview">';
  
  if (data.new_date) {
    html += `<div class="extraction-field">
      <span class="extraction-label">New Date</span>
      <span class="extraction-value">${formatShortDate(new Date(data.new_date))}</span>
    </div>`;
  }
  
  if (data.new_start_time) {
    html += `<div class="extraction-field">
      <span class="extraction-label">Start Time</span>
      <span class="extraction-value">${formatTime(data.new_start_time)}</span>
    </div>`;
  }
  
  if (data.new_end_time) {
    html += `<div class="extraction-field">
      <span class="extraction-label">End Time</span>
      <span class="extraction-value">${formatTime(data.new_end_time)}</span>
    </div>`;
  }
  
  if (data.new_location) {
    html += `<div class="extraction-field">
      <span class="extraction-label">Location</span>
      <span class="extraction-value">${escapeHtml(data.new_location)}</span>
    </div>`;
  }
  
  html += '</div>';
  
  const confirmText = action === 'cancel' ? 'Confirm Cancel' : 'Confirm';
  const confirmClass = action === 'cancel' ? 'btn-danger' : 'btn-primary';
  
  html += `<div class="confirm-actions">
    <button class="btn btn-secondary btn-sm" onclick="cancelExtraction()">Cancel</button>
    <button class="btn ${confirmClass} btn-sm" onclick="confirmExtraction()">${confirmText}</button>
  </div>`;
  
  return html;
}

function renderEventUpdatePreview(result) {
  const data = result.data;
  
  let html = `<div class="extraction-header">
    <i class="fas fa-calendar-alt" style="color: var(--primary);"></i>
    <span>Update Event Details</span>
  </div>`;
  
  html += '<div class="extraction-preview">';
  
  for (const [key, value] of Object.entries(data)) {
    if (value != null && value !== '') {
      html += `<div class="extraction-field">
        <span class="extraction-label">${formatLabel(key)}</span>
        <span class="extraction-value">${formatValue(key, value)}</span>
      </div>`;
    }
  }
  
  html += '</div>';
  
  html += `<div class="confirm-actions">
    <button class="btn btn-secondary btn-sm" onclick="cancelExtraction()">Cancel</button>
    <button class="btn btn-primary btn-sm" onclick="confirmExtraction()">Save Changes</button>
  </div>`;
  
  return html;
}

function renderStandardExtractionPreview(result) {
  let html = `<div style="margin-bottom: 8px;">Got it! Here's what I found:</div>`;
  html += '<div class="extraction-preview">';
  
  for (const [key, value] of Object.entries(result.data)) {
    if (value != null && value !== '') {
      html += `<div class="extraction-field">
        <span class="extraction-label">${formatLabel(key)}</span>
        <span class="extraction-value">${formatValue(key, value)}</span>
      </div>`;
    }
  }
  html += '</div>';
  
  if (result.missing_fields?.length > 0) {
    html += `<div style="margin-top: 8px; font-size: 0.8rem; color: var(--warning);">
      Missing: ${result.missing_fields.join(', ')}
    </div>`;
  }
  
  html += `<div class="confirm-actions">
    <button class="btn btn-secondary btn-sm" onclick="cancelExtraction()">Cancel</button>
    <button class="btn btn-primary btn-sm" onclick="confirmExtraction()">Save</button>
  </div>`;
  
  return html;
}

async function confirmExtraction() {
  if (!pendingExtraction) return;
  
  try {
    const response = await fetch(`${API_BASE}/api/events/${currentEventId}/capture/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        log_id: pendingExtraction.log_id,
        intent: pendingExtraction.intent,
        action: pendingExtraction.action || 'create',
        reference_id: pendingExtraction.reference_id,
        data: pendingExtraction.data
      })
    });
    
    const result = await response.json();
    
    if (result.success) {
      addMessage(`<i class="fas fa-check-circle" style="color: var(--success);"></i> ${result.message}`, 'ai', true);
      showToast(result.message, 'success');
      refreshCurrentView();
    } else {
      addMessage(`<i class="fas fa-times-circle" style="color: var(--danger);"></i> ${result.error || 'Failed to save'}`, 'ai', true);
    }
  } catch (error) {
    addMessage('Failed to save. Please try again.', 'ai');
    console.error('Confirm error:', error);
  }
  
  pendingExtraction = null;
}

function cancelExtraction() {
  addMessage('Cancelled. What else can I help with?', 'ai');
  pendingExtraction = null;
}

function addMessage(content, type, isHtml = false) {
  const container = document.getElementById('captureMessages');
  const message = document.createElement('div');
  message.className = `message message-${type}`;
  message.innerHTML = isHtml ? content : escapeHtml(content);
  container.appendChild(message);
  container.scrollTop = container.scrollHeight;
}

function showTypingIndicator() {
  isAITyping = true;
  clearChatCollapseTimer(); // Don't collapse while typing
  
  const container = document.getElementById('captureMessages');
  const indicator = document.createElement('div');
  indicator.className = 'message message-ai';
  indicator.id = 'typingIndicator';
  indicator.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
  container.appendChild(indicator);
  container.scrollTop = container.scrollHeight;
}

function hideTypingIndicator() {
  isAITyping = false;
  document.getElementById('typingIndicator')?.remove();
  resetChatCollapseTimer(); // Restart collapse timer after response
}

// Modal
function showCreateEventModal() {
  document.getElementById('createEventModal').classList.add('show');
  resetSubEventsList();
}

function hideCreateEventModal() {
  document.getElementById('createEventModal').classList.remove('show');
  resetCreateEventForm();
}

function resetCreateEventForm() {
  document.getElementById('eventName').value = '';
  document.getElementById('eventLocation').value = '';
  document.getElementById('eventLocationCity').value = '';
  document.getElementById('eventStartDate').value = '';
  document.getElementById('eventEndDate').value = '';
  resetSubEventsList();
}

function resetSubEventsList() {
  const container = document.getElementById('subEventsList');
  container.innerHTML = createSubEventRowHtml(0);
}

let subEventIndex = 1;

function createSubEventRowHtml(index) {
  return `
    <div class="sub-event-row" data-index="${index}">
      <div class="input-row">
        <div class="input-group flex-1">
          <label>Name</label>
          <input type="text" class="input sub-event-name" placeholder="e.g., Mehndi Night">
        </div>
        <button type="button" class="btn btn-ghost btn-sm sub-event-remove" onclick="removeSubEventRow(this)">
          <i class="fas fa-trash"></i>
        </button>
      </div>
      <div class="input-row">
        <div class="input-group flex-1">
          <label>Date</label>
          <input type="date" class="input sub-event-date">
        </div>
        <div class="input-group flex-1">
          <label>Start Time</label>
          <input type="time" class="input sub-event-start-time">
        </div>
        <div class="input-group flex-1">
          <label>End Time</label>
          <input type="time" class="input sub-event-end-time">
        </div>
      </div>
      <div class="input-row">
        <div class="input-group flex-1">
          <label>Location</label>
          <input type="text" class="input sub-event-location" placeholder="Venue address">
        </div>
      </div>
    </div>
  `;
}

function addSubEventRow() {
  const container = document.getElementById('subEventsList');
  const newRow = document.createElement('div');
  newRow.innerHTML = createSubEventRowHtml(subEventIndex++);
  container.appendChild(newRow.firstElementChild);
}

function removeSubEventRow(button) {
  const row = button.closest('.sub-event-row');
  const container = document.getElementById('subEventsList');
  if (container.children.length > 1) {
    row.remove();
  } else {
    row.querySelector('.sub-event-name').value = '';
    row.querySelector('.sub-event-date').value = '';
    row.querySelector('.sub-event-start-time').value = '';
    row.querySelector('.sub-event-end-time').value = '';
    row.querySelector('.sub-event-location').value = '';
  }
}

function collectSubEventData() {
  const rows = document.querySelectorAll('.sub-event-row');
  const subEvents = [];
  
  rows.forEach((row, index) => {
    const name = row.querySelector('.sub-event-name').value.trim();
    const date = row.querySelector('.sub-event-date').value;
    
    if (name && date) {
      subEvents.push({
        name: name,
        date: date,
        start_time: row.querySelector('.sub-event-start-time').value || null,
        end_time: row.querySelector('.sub-event-end-time').value || null,
        location: row.querySelector('.sub-event-location').value || null,
        order: index
      });
    }
  });
  
  return subEvents;
}

async function createEvent(e) {
  console.log('=== createEvent called ===');
  e.preventDefault();
  
  try {
    const eventNameEl = document.getElementById('eventName');
    const eventTypeEl = document.getElementById('eventType');
    const startDateEl = document.getElementById('eventStartDate');
    const endDateEl = document.getElementById('eventEndDate');
    const locationEl = document.getElementById('eventLocation');
    const locationCityEl = document.getElementById('eventLocationCity');
    
    console.log('Form elements found:', {
      eventName: eventNameEl?.value,
      eventType: eventTypeEl?.value,
      startDate: startDateEl?.value,
      endDate: endDateEl?.value
    });
    
    const eventName = eventNameEl?.value?.trim();
    const eventType = eventTypeEl?.value;
    const startDate = startDateEl?.value;
    const endDate = endDateEl?.value || startDate;
    const subEvents = collectSubEventData();
    
    if (!eventName) {
      console.error('Missing event name');
      showToast('Please enter an event name', 'error');
      return;
    }
    if (!eventType) {
      console.error('Missing event type');
      showToast('Please select an event type', 'error');
      return;
    }
    if (!startDate) {
      console.error('Missing start date');
      showToast('Please select a start date', 'error');
      return;
    }
    
    const data = {
      name: eventName,
      event_type: eventType,
      event_date: startDate,
      start_date: startDate,
      end_date: endDate || startDate,
      location: locationEl?.value?.trim() || null,
      location_city: locationCityEl?.value?.trim() || null,
      sub_events: subEvents.length > 0 ? subEvents : null
    };
    
    console.log('Sending POST to /api/events with data:', JSON.stringify(data, null, 2));
    
    const response = await fetch(`${API_BASE}/api/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    
    console.log('Response status:', response.status);
    const responseText = await response.text();
    console.log('Response body:', responseText);
    
    if (response.ok) {
      const event = JSON.parse(responseText);
      console.log('Event created successfully:', event);
      showToast('Event created!', 'success');
      hideCreateEventModal();
      await loadEvents();
      if (event.id) {
        selectEvent(event.id, event.event_type);
      }
    } else {
      console.error('Create event failed:', response.status, responseText);
      try {
        const error = JSON.parse(responseText);
        showToast(error.detail || 'Failed to create event', 'error');
      } catch {
        showToast('Failed to create event: ' + response.status, 'error');
      }
    }
  } catch (error) {
    console.error('Create event exception:', error);
    showToast('Failed to create event: ' + error.message, 'error');
  }
}

// Toast
function showToast(message, type = 'success') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}"></i> ${escapeHtml(message)}`;
  document.body.appendChild(toast);
  
  setTimeout(() => toast.classList.add('show'), 10);
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 200);
  }, 3000);
}

// Utility Functions
function formatNumber(num) {
  return num.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function formatShortDate(date) {
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatLabel(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function formatValue(key, value) {
  if (key.includes('amount') || key.includes('balance')) {
    const num = parseFloat(value);
    return isNaN(num) ? value : `$${num.toLocaleString()}`;
  }
  if (key.includes('date')) {
    return formatShortDate(new Date(value));
  }
  return escapeHtml(String(value));
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function getPriorityTagClass(priority) {
  return { high: 'tag-danger', medium: 'tag-warning', low: 'tag-success' }[priority] || 'tag-default';
}

function getVendorIcon(category) {
  return { 
    decorator: 'fas fa-palette', 
    photographer: 'fas fa-camera', 
    caterer: 'fas fa-utensils', 
    venue: 'fas fa-building',
    dj: 'fas fa-music',
    florist: 'fas fa-leaf'
  }[category?.toLowerCase()] || 'fas fa-store';
}

function formatEventType(type) {
  return { 
    wedding: 'Wedding',
    indian_wedding: 'Indian Wedding',
    garden: 'Garden', 
    summer: 'Summer', 
    corporate: 'Corporate', 
    birthday: 'Birthday' 
  }[type] || type;
}

function formatDateRange(startDate, endDate) {
  if (!startDate) return '';
  const start = new Date(startDate);
  if (!endDate) return formatShortDate(start);
  const end = new Date(endDate);
  return `${formatShortDate(start)} - ${formatShortDate(end)}`;
}
