// EventOps — Eve, your virtual event planner

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
let fileSortOrder = 'desc'; // For files view
let collapsedPromptIndex = 0;

const COLLAPSED_PROMPTS = [
  "Any progress on your wedding planning?",
  "Share an update below",
  "Any updates on your wedding planning?",
  "What did you knock off today?",
  "Hi, I'm Eve! How can I help?",
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
  setupWelcomeCardHover();
  setupFileDragDrop();
});

function setupWelcomeCardHover() {
  const welcomeBtn = document.querySelector('.btn-welcome');
  const welcomeCard = document.querySelector('.welcome-card');
  
  if (!welcomeBtn || !welcomeCard) return;
  
  welcomeBtn.addEventListener('mouseenter', () => {
    welcomeCard.classList.add('hovered');
  });
  
  welcomeBtn.addEventListener('mouseleave', () => {
    welcomeCard.classList.remove('hovered');
  });
}

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

  // Collapse / exit fullscreen when clicking outside the chat panel
  document.addEventListener('mousedown', (e) => {
    if (!isChatExpanded || isAITyping) return;
    if (!aiAssistant.contains(e.target)) {
      if (isChatFullscreen) {
        toggleFullscreen();
      }
      isChatHovered = false;
      collapseChat();
    }
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

  const fadeEl = document.createElement('div');
  fadeEl.className = 'chat-bottom-fade';
  fadeEl.id = 'chatBottomFade';
  aiAssistant.parentNode.insertBefore(fadeEl, aiAssistant);
}

function showCollapsedPrompt() {
  const promptEl = document.getElementById('collapsedChatPrompt');
  if (promptEl) {
    promptEl.style.display = 'block';
    promptEl.style.opacity = '1';
  }
  const fadeEl = document.getElementById('chatBottomFade');
  if (fadeEl) fadeEl.style.display = 'block';
}

function hideCollapsedPrompt() {
  const promptEl = document.getElementById('collapsedChatPrompt');
  if (promptEl) {
    promptEl.style.opacity = '0';
    setTimeout(() => {
      promptEl.style.display = 'none';
    }, 200);
  }
  const fadeEl = document.getElementById('chatBottomFade');
  if (fadeEl) fadeEl.style.display = 'none';
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
    resetChatCollapseTimer();
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
  // V2 Navigation: .nav-btn buttons in top-nav
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      switchView(btn.dataset.view);
    });
  });
  
  // V1 Fallback: .nav-item links (for backwards compatibility)
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      switchView(item.dataset.view);
    });
  });
}

function switchView(view) {
  const navButtons = document.querySelectorAll('.nav-btn');
  const currentActiveBtn = document.querySelector('.nav-btn.active');
  const newActiveBtn = document.querySelector(`.nav-btn[data-view="${view}"]`);
  
  // If clicking the same view or no buttons found, just update without animation
  if (!currentActiveBtn || !newActiveBtn || currentActiveBtn === newActiveBtn) {
    navButtons.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.view === view);
    });
    updateViewContent(view);
    return;
  }
  
  // Staggered animation: collapse old button first
  currentActiveBtn.classList.remove('active');
  
  // After collapse animation completes (300ms), expand new button
  setTimeout(() => {
    newActiveBtn.classList.add('active');
  }, 300);
  
  // Update V1 nav items (fallback) - immediate
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.view === view);
  });
  
  // Update view content immediately
  updateViewContent(view);
}

function updateViewContent(view) {
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
      if (currentEventId) loadDashboardV2(); 
      break;
    case 'payments': loadPaymentsV2(); break;
    case 'tasks': break;
    case 'calendar': loadCalendarV2(); break;
    case 'notes': loadNotesView(); break;
    case 'files': loadFilesV2(); break;
  }
}

// Events
let eventSelectorInitialized = false;

async function loadEvents() {
  const welcomeState = document.getElementById('welcomeState');
  const dashboardContent = document.getElementById('dashboardContent');
  const selector = document.getElementById('eventSelector');
  const eventTitleEl = document.getElementById('currentEventTitle');
  
  try {
    const response = await fetch(`${API_BASE}/api/events`);
    allEvents = await response.json();
    
    selector.innerHTML = '';
    
    if (allEvents.length === 0) {
      // Show welcome state, hide dashboard content
      if (welcomeState) welcomeState.style.display = 'flex';
      if (dashboardContent) dashboardContent.style.display = 'none';
      selector.innerHTML = '<option value="">No events yet</option>';
      if (eventTitleEl) eventTitleEl.textContent = 'Create Your First Event';
      currentEventId = null;
      currentEventType = null;
    } else {
      // Hide welcome state, show dashboard content
      if (welcomeState) welcomeState.style.display = 'none';
      if (dashboardContent) dashboardContent.style.display = 'block';
      
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
      
      // Update event title
      updateEventTitle();
      
      // Load dashboard with V2 function
      loadDashboardV2();
    }
    
    // Only add event listener once
    if (!eventSelectorInitialized) {
      selector.addEventListener('change', (e) => {
        const selected = allEvents.find(ev => ev.id === e.target.value);
        if (selected) {
          currentEventId = selected.id;
          currentEventType = selected.event_type;
          calViewYear = null;
          calViewMonth = null;
          currentNoteId = null;
          notesList = [];
          updateEventTitle();
          refreshCurrentView();
          updateEditButtonVisibility();
        }
      });
      eventSelectorInitialized = true;
    }
    
    // Update edit button visibility
    updateEditButtonVisibility();
  } catch (error) {
    console.error('Failed to load events:', error);
    // Show welcome state on error as fallback
    if (welcomeState) welcomeState.style.display = 'flex';
    if (dashboardContent) dashboardContent.style.display = 'none';
    showToast('Failed to load events', 'error');
  }
}

function updateEventTitle() {
  const eventTitleEl = document.getElementById('currentEventTitle');
  if (!eventTitleEl || !currentEventId) return;
  
  const currentEvent = allEvents.find(e => e.id === currentEventId);
  if (currentEvent) {
    eventTitleEl.textContent = currentEvent.name;
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
      const displayTitle = p.vendor_name || p.description || 'Payment due';
      items.push({
        title: displayTitle,
        type: 'payment',
        date: parseDateLocal(p.due_date)
      });
    }
  });
  
  calendar.forEach(c => {
    if (c.event_date) {
      items.push({
        title: c.title,
        type: 'event',
        date: parseDateLocal(c.event_date)
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
  
  container.innerHTML = payments.map((p, i) => {
    const displayName = p.vendor_name || p.description || 'Payment';
    const rawPaid = parseFloat(p.amount_paid || 0);
    const amount = rawPaid > 0 ? rawPaid : parseFloat(p.amount || 0);
    return `
    <div class="item-row">
      <div class="item-icon ${COLORS[i % COLORS.length]}">
        <i class="fas fa-dollar-sign"></i>
      </div>
      <div class="item-content">
        <div class="item-title">${escapeHtml(displayName)}</div>
        <div class="item-subtitle">${p.paid_date ? formatShortDate(parseDateLocal(p.paid_date)) : 'Pending'} · $${formatNumber(amount)}</div>
      </div>
      ${p.paid_date ? '<span class="tag tag-success">Paid</span>' : '<span class="tag tag-warning">Due</span>'}
    </div>
  `;}).join('');
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
        ${t.due_date ? `<div class="item-subtitle">Due: ${formatShortDate(parseDateLocal(t.due_date))}</div>` : ''}
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
    
    const taskCounts = await Promise.all(events.map(async (ev) => {
      try {
        const r = await fetch(`${API_BASE}/api/events/${ev.id}/tasks`);
        const tasks = r.ok ? await r.json() : [];
        return tasks.filter(t => t.status === 'pending' || t.status === 'in_progress').length;
      } catch { return 0; }
    }));

    container.innerHTML = events.map((event, i) => renderEventCard(event, i, taskCounts[i])).join('');
  } catch (error) {
    console.error('Failed to load events:', error);
  }
}

function renderEventCard(event, index, tasksRemaining = 0) {
  const dateDisplay = event.start_date && event.end_date 
    ? formatDateRange(event.start_date, event.end_date)
    : event.event_date 
      ? formatShortDate(parseDateLocal(event.event_date))
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
        ${tasksRemaining > 0 ? `<div class="event-card-badge"><i class="fas fa-tasks" style="margin-right:4px"></i>${tasksRemaining} task${tasksRemaining !== 1 ? 's' : ''} remaining</div>` : ''}
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
  calViewYear = null;
  calViewMonth = null;
  currentNoteId = null;
  notesList = [];
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
    
    container.innerHTML = vendors.map((v, i) => {
      const ic = v.icon_class || getVendorIcon(v.category);
      const bg = v.icon_color || getVendorColor(v.category);
      return `
      <div class="item-row">
        <div class="avatar" style="background:${bg}; color:#fff;">
          <i class="${ic}"></i>
        </div>
        <div class="item-content">
          <div class="item-title">${escapeHtml(v.name)}</div>
          <div class="item-subtitle">${escapeHtml(v.category || 'Other')}</div>
        </div>
        ${v.contact_info ? `<span class="item-subtitle">${escapeHtml(v.contact_info)}</span>` : ''}
      </div>`;
    }).join('');
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
            ${p.paid_date ? `Paid: ${formatShortDate(parseDateLocal(p.paid_date))}` : ''}
            ${p.due_date ? ` · Due: ${formatShortDate(parseDateLocal(p.due_date))}` : ''}
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
          ${t.due_date ? `<div class="item-subtitle">Due: ${formatShortDate(parseDateLocal(t.due_date))}</div>` : ''}
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
          <div class="item-subtitle">${formatShortDate(parseDateLocal(e.event_date))}${e.event_time ? ` at ${e.event_time}` : ''}</div>
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

async function _streamExtract(text) {
  const resp = await fetch(`${API_BASE}/api/events/${currentEventId}/capture/extract/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, conversation_history: conversationHistory }),
  });
  if (!resp.ok) throw new Error(`Stream HTTP ${resp.status}`);
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  let result = null;
  let firstDelta = true;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop();
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const payload = line.slice(6).trim();
      if (payload === '[DONE]') continue;
      try {
        const evt = JSON.parse(payload);
        if (evt.type === 'delta') {
          if (firstDelta) { updateTypingStatus('Eve is typing...'); firstDelta = false; }
        } else if (evt.type === 'result') {
          result = evt.data;
        }
      } catch (_) {}
    }
  }
  if (!result) throw new Error('No result from stream');
  return result;
}

async function submitCapture() {
  const input = document.getElementById('captureInput');
  const text = input.value.trim();
  
  if (!text) return;
  if (!currentEventId) {
    showToast('Please create an event first', 'error');
    return;
  }
  
  expandChat();
  resetChatCollapseTimer();
  
  addMessage(text, 'user');
  input.value = '';
  clearPlaceholder();
  
  addToConversationHistory('user', text);
  
  showTypingIndicator('Processing...');

  try {
    let result;
    try {
      result = await _streamExtract(text);
    } catch (streamErr) {
      console.warn('Stream fallback to standard extract:', streamErr);
      const resp = await fetch(`${API_BASE}/api/events/${currentEventId}/capture/extract`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, conversation_history: conversationHistory }),
      });
      result = await resp.json();
    }
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
    
    // Handle document query with structured citations
    if (result.intent === 'document_query') {
      const citations = result.data?.citations || [];
      const html = formatDocumentAnswer(result.assistant_message || '', citations);
      addMessage(html, 'ai', true);
      addToConversationHistory('assistant', result.assistant_message || '');
      return;
    }

    // Handle actionable intents that need persisting (task, calendar_event, etc.)
    const actionableIntents = ['payment', 'task', 'calendar_event', 'vendor', 'sub_event_update', 'event_update'];
    if (actionableIntents.includes(result.intent) && result.action !== 'delete' && responseMode !== 'clarify') {
      const msg = result.assistant_message || 'Done!';
      if (result.follow_up_question) {
        addMessage(msg + ' ' + result.follow_up_question, 'ai');
        addToConversationHistory('assistant', msg + ' ' + result.follow_up_question);
      } else {
        addMessage(msg, 'ai');
        addToConversationHistory('assistant', msg);
      }
      pendingExtraction = result;
      await autoConfirmExtraction();
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
  
  if (result.needs_confirmation && result.data && Object.keys(result.data).length > 0) {
    html += '<ul class="extraction-list">';
    for (const [key, value] of Object.entries(result.data)) {
      if (value !== null && value !== undefined && value !== '') {
        html += formatDataEntry(key, value);
      }
    }
    html += '</ul>';
  }
  
  if (result.follow_up_question) {
    html += `<div class="follow-up-question"><strong>${result.follow_up_question}</strong></div>`;
  }
  
  html += `</div>`;
  addMessage(html, 'ai', true);
  addToConversationHistory('assistant', result.assistant_message + (result.follow_up_question ? ' ' + result.follow_up_question : ''));
  
  // Auto-confirm in background if no follow-up question
  if (result.needs_confirmation && !result.follow_up_question) {
    autoConfirmExtraction();
  }
}

async function autoConfirmExtraction() {
  if (!pendingExtraction) return;
  
  try {
    const confirmPayload = {
      log_id: pendingExtraction.log_id,
      intent: pendingExtraction.intent,
      action: pendingExtraction.action || 'create',
      reference_id: pendingExtraction.reference_id,
      data: pendingExtraction.data
    };
    
    if (pendingExtraction.secondary_actions && pendingExtraction.secondary_actions.length > 0) {
      confirmPayload.secondary_actions = pendingExtraction.secondary_actions;
    }
    
    const response = await fetch(`${API_BASE}/api/events/${currentEventId}/capture/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(confirmPayload)
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
      const date = p.paid_date ? parseDateLocal(p.paid_date).toLocaleDateString() : '';
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
      const dueDate = t.due_date ? parseDateLocal(t.due_date).toLocaleDateString() : '';
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
      const eventDate = e.event_date ? parseDateLocal(e.event_date).toLocaleDateString() : '';
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
  html += `<div style="margin-bottom: 8px;">Got it! Here's what I found:</div>`;
  html += '<ul class="extraction-list">';
  
  for (const [key, value] of Object.entries(result.data)) {
    if (value !== null && value !== undefined && value !== '') {
      html += formatDataEntry(key, value);
    }
  }
  
  html += '</ul>';
  
  html += `<div class="follow-up-question"><strong>${result.follow_up_question}</strong></div>`;
  
  html += `</div>`;
  addMessage(html, 'ai', true);
  addToConversationHistory('assistant', 'Got it! Here\'s what I found. ' + result.follow_up_question);
}

function renderSubEventUpdatePreview(result) {
  const data = result.data;
  const action = data.action || 'update';
  
  let actionDescription = '';
  
  switch (action) {
    case 'add':
      actionDescription = `I'll add a new sub-event "${data.new_name || 'New Sub-Event'}"`;
      break;
    case 'cancel':
      actionDescription = `I'll cancel the "${data.sub_event_name}" sub-event`;
      break;
    case 'reschedule':
      actionDescription = `I'll reschedule "${data.sub_event_name}"`;
      break;
    case 'update':
      if (data.new_name) {
        actionDescription = `I'll change "${data.sub_event_name}" to "${data.new_name}"`;
      } else {
        actionDescription = `I'll update "${data.sub_event_name}"`;
      }
      break;
    default:
      actionDescription = `I'll update the sub-event`;
  }
  
  let html = `<div style="margin-bottom: 8px;">${actionDescription}</div>`;
  
  const hasDetails = data.new_date || data.new_start_time || data.new_end_time || data.new_location;
  if (hasDetails) {
    html += '<ul class="extraction-list">';
    if (data.new_date) {
      html += `<li><strong>Date:</strong> ${formatShortDate(new Date(data.new_date))}</li>`;
    }
    if (data.new_start_time) {
      html += `<li><strong>Time:</strong> ${formatTime(data.new_start_time)}</li>`;
    }
    if (data.new_end_time) {
      html += `<li><strong>End Time:</strong> ${formatTime(data.new_end_time)}</li>`;
    }
    if (data.new_location) {
      html += `<li><strong>Location:</strong> ${escapeHtml(data.new_location)}</li>`;
    }
    html += '</ul>';
  }
  
  // Auto-confirm this action
  setTimeout(() => autoConfirmExtraction(), 100);
  
  return html;
}

function renderEventUpdatePreview(result) {
  const data = result.data;
  
  let html = `<div style="margin-bottom: 8px;">I'll update your event details:</div>`;
  html += '<ul class="extraction-list">';
  
  for (const [key, value] of Object.entries(data)) {
    if (value != null && value !== '') {
      html += formatDataEntry(key, value);
    }
  }
  
  html += '</ul>';
  
  // Auto-confirm this action
  setTimeout(() => autoConfirmExtraction(), 100);
  
  return html;
}

function renderStandardExtractionPreview(result) {
  let html = `<div style="margin-bottom: 8px;">Got it! I'll save this for you:</div>`;
  html += '<ul class="extraction-list">';
  
  for (const [key, value] of Object.entries(result.data)) {
    if (value != null && value !== '') {
      html += formatDataEntry(key, value);
    }
  }
  html += '</ul>';
  
  if (result.missing_fields?.length > 0) {
    html += `<div class="follow-up-question"><strong>I'm missing some info: ${result.missing_fields.join(', ')}. Can you provide those details?</strong></div>`;
  } else {
    // Auto-confirm if no missing fields
    setTimeout(() => autoConfirmExtraction(), 100);
  }
  
  return html;
}

async function confirmExtraction() {
  if (!pendingExtraction) return;
  
  showTypingIndicator('Saving...');
  
  try {
    const confirmPayload = {
      log_id: pendingExtraction.log_id,
      intent: pendingExtraction.intent,
      action: pendingExtraction.action || 'create',
      reference_id: pendingExtraction.reference_id,
      data: pendingExtraction.data
    };
    
    if (pendingExtraction.secondary_actions && pendingExtraction.secondary_actions.length > 0) {
      confirmPayload.secondary_actions = pendingExtraction.secondary_actions;
    }
    
    const response = await fetch(`${API_BASE}/api/events/${currentEventId}/capture/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(confirmPayload)
    });
    
    hideTypingIndicator();
    const result = await response.json();
    
    if (result.success) {
      addMessage(`Done! ${result.message}`, 'ai');
      showToast(result.message, 'success');
      refreshCurrentView();
    } else {
      addMessage(`Oops! ${result.error || 'Failed to save'}`, 'ai');
    }
  } catch (error) {
    hideTypingIndicator();
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

function showTypingIndicator(message = null) {
  isAITyping = true;
  clearChatCollapseTimer();
  
  const container = document.getElementById('captureMessages');
  let indicator = document.getElementById('typingIndicator');
  
  if (!indicator) {
    indicator = document.createElement('div');
    indicator.className = 'message message-ai typing-message';
    indicator.id = 'typingIndicator';
    container.appendChild(indicator);
  }
  
  if (message) {
    indicator.innerHTML = `<span class="typing-status">${message}</span>`;
  } else {
    indicator.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
  }
  
  container.scrollTop = container.scrollHeight;
}

function updateTypingStatus(message) {
  const indicator = document.getElementById('typingIndicator');
  if (indicator) {
    indicator.innerHTML = `<span class="typing-status">${message}</span>`;
  }
}

function hideTypingIndicator() {
  isAITyping = false;
  document.getElementById('typingIndicator')?.remove();
  resetChatCollapseTimer();
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

// Edit Event Modal Functions
function updateEditButtonVisibility() {
  const editBtn = document.getElementById('editEventBtn');
  if (editBtn) {
    editBtn.style.display = currentEventId ? 'flex' : 'none';
  }
}

let editSubEventIndex = 0;
let originalSubEvents = [];
let subEventsToDelete = [];

async function showEditEventModal() {
  if (!currentEventId) {
    showToast('Please select an event first', 'error');
    return;
  }
  
  try {
    const eventResponse = await fetch(`${API_BASE}/api/events/${currentEventId}`);
    if (!eventResponse.ok) throw new Error('Failed to fetch event');
    const event = await eventResponse.json();
    
    document.getElementById('editEventName').value = event.name || '';
    document.getElementById('editEventType').value = event.event_type || 'wedding';
    document.getElementById('editEventStartDate').value = event.start_date || '';
    document.getElementById('editEventEndDate').value = event.end_date || '';
    document.getElementById('editEventLocation').value = event.location || '';
    document.getElementById('editEventLocationCity').value = event.location_city || '';
    
    const subEventsResponse = await fetch(`${API_BASE}/api/events/${currentEventId}/sub-events`);
    const subEvents = subEventsResponse.ok ? await subEventsResponse.json() : [];
    originalSubEvents = subEvents;
    subEventsToDelete = [];
    
    const container = document.getElementById('editSubEventsList');
    container.innerHTML = '';
    editSubEventIndex = 0;
    
    if (subEvents.length === 0) {
      container.innerHTML = '<p class="text-muted" style="text-align: center; padding: var(--space-4);">No sub-events yet. Click "Add New" to create one.</p>';
    } else {
      subEvents.forEach((subEvent, idx) => {
        container.innerHTML += createEditSubEventRowHtml(idx, subEvent);
        editSubEventIndex = idx + 1;
      });
    }
    
    document.getElementById('editEventModal').classList.add('show');
  } catch (error) {
    console.error('Failed to load event for editing:', error);
    showToast('Failed to load event details', 'error');
  }
}

function hideEditEventModal() {
  document.getElementById('editEventModal').classList.remove('show');
  subEventsToDelete = [];
}

function createEditSubEventRowHtml(index, subEvent = null) {
  const id = subEvent ? subEvent.id : '';
  const name = subEvent ? (subEvent.name || '') : '';
  const date = subEvent ? (subEvent.date || '') : '';
  const startTime = subEvent ? (subEvent.start_time || '') : '';
  const endTime = subEvent ? (subEvent.end_time || '') : '';
  const isExisting = !!subEvent?.id;
  
  return `
    <div class="sub-event-row" data-index="${index}" data-id="${id}" data-is-new="${!isExisting}">
      <div class="input-row">
        <div class="input-group flex-1">
          <label>Name</label>
          <input type="text" class="input edit-sub-event-name" value="${escapeHtml(name)}" placeholder="e.g., Mehndi Night">
        </div>
        <button type="button" class="btn btn-ghost btn-sm sub-event-remove" onclick="removeEditSubEventRow(this)" title="Remove sub-event">
          <i class="fas fa-trash"></i>
        </button>
      </div>
      <div class="input-row">
        <div class="input-group flex-1">
          <label>Date</label>
          <input type="date" class="input edit-sub-event-date" value="${date}">
        </div>
        <div class="input-group flex-1">
          <label>Start Time</label>
          <input type="time" class="input edit-sub-event-start-time" value="${startTime}">
        </div>
        <div class="input-group flex-1">
          <label>End Time</label>
          <input type="time" class="input edit-sub-event-end-time" value="${endTime}">
        </div>
      </div>
    </div>
  `;
}

function addEditSubEventRow() {
  const container = document.getElementById('editSubEventsList');
  const emptyMsg = container.querySelector('.text-muted');
  if (emptyMsg) emptyMsg.remove();
  
  container.innerHTML += createEditSubEventRowHtml(editSubEventIndex);
  editSubEventIndex++;
}

function removeEditSubEventRow(button) {
  const row = button.closest('.sub-event-row');
  const subEventId = row.dataset.id;
  const isNew = row.dataset.isNew === 'true';
  
  if (subEventId && !isNew) {
    subEventsToDelete.push(subEventId);
  }
  
  row.remove();
  
  const container = document.getElementById('editSubEventsList');
  if (container.children.length === 0) {
    container.innerHTML = '<p class="text-muted" style="text-align: center; padding: var(--space-4);">No sub-events. Click "Add New" to create one.</p>';
  }
}

async function saveEventChanges(e) {
  e.preventDefault();
  
  try {
    const eventData = {
      name: document.getElementById('editEventName').value.trim(),
      event_type: document.getElementById('editEventType').value,
      start_date: document.getElementById('editEventStartDate').value || null,
      end_date: document.getElementById('editEventEndDate').value || null,
      location: document.getElementById('editEventLocation').value.trim() || null,
      location_city: document.getElementById('editEventLocationCity').value.trim() || null,
    };
    
    if (!eventData.name) {
      showToast('Event name is required', 'error');
      return;
    }
    
    const eventResponse = await fetch(`${API_BASE}/api/events/${currentEventId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(eventData),
    });
    
    if (!eventResponse.ok) {
      throw new Error('Failed to update event');
    }
    
    for (const subEventId of subEventsToDelete) {
      const deleteResponse = await fetch(`${API_BASE}/api/events/${currentEventId}/sub-events/${subEventId}`, {
        method: 'DELETE',
      });
      if (!deleteResponse.ok) {
        console.warn(`Failed to delete sub-event ${subEventId}`);
      }
    }
    
    const subEventRows = document.querySelectorAll('#editSubEventsList .sub-event-row');
    for (const row of subEventRows) {
      const name = row.querySelector('.edit-sub-event-name').value.trim();
      const date = row.querySelector('.edit-sub-event-date').value || null;
      const startTime = row.querySelector('.edit-sub-event-start-time').value || null;
      const endTime = row.querySelector('.edit-sub-event-end-time').value || null;
      const subEventId = row.dataset.id;
      const isNew = row.dataset.isNew === 'true';
      
      if (!name) continue;
      
      if (isNew) {
        if (!date) {
          showToast(`Sub-event "${name}" requires a date`, 'error');
          return;
        }
        const subEventData = { name, date, start_time: startTime, end_time: endTime };
        await fetch(`${API_BASE}/api/events/${currentEventId}/sub-events`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(subEventData),
        });
      } else if (subEventId) {
        const subEventData = { name };
        if (date) subEventData.date = date;
        if (startTime) subEventData.start_time = startTime;
        if (endTime) subEventData.end_time = endTime;
        
        await fetch(`${API_BASE}/api/events/${currentEventId}/sub-events/${subEventId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(subEventData),
        });
      }
    }
    
    showToast('Event updated successfully!', 'success');
    hideEditEventModal();
    await loadEvents();
    refreshCurrentView();
  } catch (error) {
    console.error('Failed to save event changes:', error);
    showToast('Failed to save changes: ' + error.message, 'error');
  }
}

// Feedback System
function showFeedbackPopup() {
  document.getElementById('feedbackPopup').classList.add('show');
  document.getElementById('feedbackText').focus();
}

function hideFeedbackPopup() {
  document.getElementById('feedbackPopup').classList.remove('show');
  document.getElementById('feedbackText').value = '';
}

async function submitFeedback() {
  const feedbackText = document.getElementById('feedbackText').value.trim();
  
  if (!feedbackText) {
    showToast('Please describe the issue', 'error');
    return;
  }
  
  const lastUserMsg = conversationHistory.filter(c => c.role === 'user').slice(-1)[0];
  const lastAiMsg = conversationHistory.filter(c => c.role === 'assistant').slice(-1)[0];
  
  const feedbackData = {
    event_id: currentEventId,
    user_feedback: feedbackText,
    conversation_history: JSON.stringify(conversationHistory),
    last_user_message: lastUserMsg?.content || null,
    last_llm_response: lastAiMsg?.content || null,
  };
  
  try {
    const response = await fetch(`${API_BASE}/api/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(feedbackData),
    });
    
    if (response.ok) {
      showToast('Feedback submitted. Thank you!', 'success');
      hideFeedbackPopup();
    } else {
      showToast('Failed to submit feedback', 'error');
    }
  } catch (error) {
    console.error('Feedback submission error:', error);
    showToast('Failed to submit feedback', 'error');
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

function parseDateLocal(dateStr) {
  if (!dateStr) return new Date();
  const parts = dateStr.split('T')[0].split('-');
  return new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
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

function formatDataEntry(key, value) {
  const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  if (Array.isArray(value)) {
    let html = `<li><strong>${label}:</strong><ul>`;
    value.forEach((item, i) => {
      if (typeof item === 'object' && item !== null) {
        const parts = Object.entries(item)
          .filter(([, v]) => v != null && v !== '')
          .map(([k, v]) => `${formatLabel(k)}: ${formatValue(k, v)}`)
          .join(', ');
        html += `<li>${parts}</li>`;
      } else {
        html += `<li>${escapeHtml(String(item))}</li>`;
      }
    });
    html += '</ul></li>';
    return html;
  }
  if (typeof value === 'object' && value !== null) {
    const parts = Object.entries(value)
      .filter(([, v]) => v != null && v !== '')
      .map(([k, v]) => `${formatLabel(k)}: ${formatValue(k, v)}`)
      .join(', ');
    return `<li><strong>${label}:</strong> ${parts}</li>`;
  }
  return `<li><strong>${label}:</strong> ${formatValue(key, value)}</li>`;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatDocumentAnswer(rawAnswer, citations) {
  const uniqueCitations = [];
  const seen = new Set();
  for (const c of citations) {
    const key = `${c.section_title}|${c.page_number}`;
    if (!seen.has(key)) {
      seen.add(key);
      uniqueCitations.push(c);
    }
  }

  let html = escapeHtml(rawAnswer);

  html = html.replace(/\[(\d+)\]/g, (_, num) => {
    const idx = parseInt(num, 10);
    if (idx >= 1 && idx <= uniqueCitations.length) {
      const c = uniqueCitations[idx - 1];
      const tip = escapeHtml(`${c.section_title}, p.${c.page_number}`);
      return `<span class="cite-pill" title="${tip}">${idx}</span>`;
    }
    return `[${num}]`;
  });

  html = html.replace(/^&gt;\s?(.+)$/gm, '<blockquote class="doc-quote">$1</blockquote>');
  html = html.replace(/<\/blockquote>\n<blockquote class="doc-quote">/g, '\n');

  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  html = html.replace(/^[-•]\s+(.+)$/gm, '<li>$1</li>');
  html = html.replace(/((?:<li>.*<\/li>\s*)+)/g, '<ul class="doc-answer-list">$1</ul>');

  html = html.replace(/\n{2,}/g, '</p><p>');
  html = html.replace(/\n/g, '<br>');
  html = `<p>${html}</p>`;

  let sourcesHtml = '';
  if (uniqueCitations.length > 0) {
    const items = uniqueCitations.map((c, i) => {
      const label = escapeHtml(c.section_title || 'Document');
      const page = c.page_number || '?';
      return `<span class="source-ref"><span class="cite-pill cite-pill-sm">${i + 1}</span> ${label}, p.${page}</span>`;
    }).join('');
    sourcesHtml = `<div class="doc-sources"><span class="doc-sources-label">Sources</span><div class="doc-sources-list">${items}</div></div>`;
  }

  return `<div class="doc-answer">${html}${sourcesHtml}</div>`;
}

function getPriorityTagClass(priority) {
  return { high: 'tag-danger', medium: 'tag-warning', low: 'tag-success' }[priority] || 'tag-default';
}

const VENDOR_ICON_MAP = {
  photography:    'fas fa-camera',
  videography:    'fas fa-video',
  music_dj:       'fas fa-compact-disc',
  catering:       'fas fa-utensils',
  mehndi:         'fas fa-hand-sparkles',
  officiant:      'fas fa-book-open',
  decor:          'fas fa-wreath',
  makeup_hair:    'fas fa-paint-brush',
  attire:         'fas fa-shirt',
  jewelry:        'fas fa-gem',
  bakery:         'fas fa-cake-candles',
  transportation: 'fas fa-car-side',
  rentals:        'fas fa-tent',
  planner:        'fas fa-clipboard-list',
  choreographer:  'fas fa-person-walking',
  invitations:    'fas fa-envelope-open-text',
  favors:         'fas fa-gift',
  travel:         'fas fa-plane-departure',
  venue:          'fas fa-building-columns',
  florist:        'fas fa-seedling',
  photographer:   'fas fa-camera',
  caterer:        'fas fa-utensils',
  decorator:      'fas fa-palette',
  dj:             'fas fa-compact-disc',
};

const VENDOR_COLOR_MAP = {
  photography:    '#A0C9CB',
  videography:    '#A0C9CB',
  music_dj:       '#FF6037',
  catering:       '#CB997E',
  mehndi:         '#D4A373',
  officiant:      '#87A878',
  decor:          '#FFBF69',
  makeup_hair:    '#E8A0BF',
  attire:         '#B4A7D6',
  jewelry:        '#F0C27F',
  bakery:         '#F4845F',
  transportation: '#7FCDCD',
  rentals:        '#C4A35A',
  planner:        '#A0C9CB',
  choreographer:  '#FF9F1C',
  invitations:    '#D4A5A5',
  favors:         '#87A878',
  travel:         '#7EB0D5',
  venue:          '#733635',
  florist:        '#87A878',
  photographer:   '#A0C9CB',
  caterer:        '#CB997E',
  decorator:      '#FFBF69',
  dj:             '#FF6037',
};

const VENDOR_ICON_INVENTORY = [
  { icon: 'fas fa-camera',             label: 'Camera' },
  { icon: 'fas fa-video',              label: 'Video' },
  { icon: 'fas fa-compact-disc',       label: 'Disc' },
  { icon: 'fas fa-music',              label: 'Music' },
  { icon: 'fas fa-utensils',           label: 'Utensils' },
  { icon: 'fas fa-hand-sparkles',      label: 'Mehndi' },
  { icon: 'fas fa-book-open',          label: 'Book' },
  { icon: 'fas fa-wreath',             label: 'Wreath' },
  { icon: 'fas fa-palette',            label: 'Palette' },
  { icon: 'fas fa-paint-brush',        label: 'Brush' },
  { icon: 'fas fa-shirt',              label: 'Attire' },
  { icon: 'fas fa-gem',                label: 'Gem' },
  { icon: 'fas fa-cake-candles',       label: 'Cake' },
  { icon: 'fas fa-car-side',           label: 'Car' },
  { icon: 'fas fa-tent',               label: 'Tent' },
  { icon: 'fas fa-clipboard-list',     label: 'Planner' },
  { icon: 'fas fa-person-walking',     label: 'Dance' },
  { icon: 'fas fa-envelope-open-text', label: 'Invite' },
  { icon: 'fas fa-gift',               label: 'Gift' },
  { icon: 'fas fa-plane-departure',    label: 'Travel' },
  { icon: 'fas fa-building-columns',   label: 'Venue' },
  { icon: 'fas fa-seedling',           label: 'Floral' },
  { icon: 'fas fa-heart',              label: 'Heart' },
  { icon: 'fas fa-star',               label: 'Star' },
  { icon: 'fas fa-champagne-glasses',  label: 'Cheers' },
  { icon: 'fas fa-ring',               label: 'Ring' },
  { icon: 'fas fa-store',              label: 'Store' },
  { icon: 'fas fa-leaf',               label: 'Leaf' },
  { icon: 'fas fa-dollar-sign',        label: 'Dollar' },
  { icon: 'fas fa-microphone',         label: 'Mic' },
];

const VENDOR_COLOR_PALETTE = [
  '#A0C9CB', '#FF6037', '#733635', '#FFBF69',
  '#CB997E', '#87A878', '#D4A373', '#E8A0BF',
  '#B4A7D6', '#F0C27F', '#F4845F', '#7FCDCD',
  '#C4A35A', '#D4A5A5', '#7EB0D5', '#FF9F1C',
  '#6B8E5D', '#F5F4ED', '#1F1F1F', '#4A4A4A',
];

function getVendorIcon(category) {
  const key = category?.toLowerCase().replace(/\s+/g, '_');
  return VENDOR_ICON_MAP[key] || 'fas fa-store';
}

function getVendorColor(category) {
  const key = category?.toLowerCase().replace(/\s+/g, '_');
  return VENDOR_COLOR_MAP[key] || '#A0C9CB';
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

// ============================================
// UI V2 FUNCTIONS
// ============================================

async function loadDashboardV2() {
  if (!currentEventId) return;
  
  try {
    const [dashResponse, vendorsResponse, eventResponse, tasksResponse] = await Promise.all([
      fetch(`${API_BASE}/api/events/${currentEventId}/dashboard`),
      fetch(`${API_BASE}/api/events/${currentEventId}/vendors`),
      fetch(`${API_BASE}/api/events/${currentEventId}`),
      fetch(`${API_BASE}/api/events/${currentEventId}/tasks`)
    ]);
    
    const dashboard = await dashResponse.json();
    const vendors = await vendorsResponse.json();
    const event = await eventResponse.json();
    const allTasks = tasksResponse.ok ? await tasksResponse.json() : [];
    
    const tasksRemainingCount = allTasks.filter(t => t.status === 'pending' || t.status === 'in_progress').length;
    const vendorsCount = vendors.length;
    const totalPaid = parseFloat(dashboard.financial_summary?.total_paid || 0);
    const totalPending = parseFloat(dashboard.financial_summary?.total_upcoming || 0);
    
    const statTasksRemaining = document.getElementById('stat-tasks-remaining');
    const statVendors = document.getElementById('stat-vendors');
    const statPaid = document.getElementById('stat-paid');
    const statPending = document.getElementById('stat-pending');
    
    if (statTasksRemaining) statTasksRemaining.textContent = tasksRemainingCount;
    if (statVendors) statVendors.textContent = vendorsCount;
    if (statPaid) statPaid.textContent = `$${formatNumber(totalPaid)}`;
    if (statPending) statPending.textContent = `$${formatNumber(totalPending)}`;

    renderBudgetTracker(dashboard.budget_breakdown);

    await loadTasksKanban();
    
  } catch (error) {
    console.error('Failed to load dashboard V2:', error);
  }
}

function renderBudgetTracker(breakdown) {
  const container = document.getElementById('budgetTracker');
  if (!container || !breakdown) { if (container) container.style.display = 'none'; return; }

  const spent = parseFloat(breakdown.total_spent || 0);
  const pending = parseFloat(breakdown.total_pending || 0);
  const committed = spent + pending;

  if (committed === 0) { container.style.display = 'none'; return; }
  container.style.display = '';

  const paidPct = committed > 0 ? (spent / committed) * 100 : 0;
  const pendingPct = committed > 0 ? (pending / committed) * 100 : 0;

  const paidEl = document.getElementById('budgetFillPaid');
  const pendingEl = document.getElementById('budgetFillPending');

  paidEl.style.transition = 'none';
  pendingEl.style.transition = 'none';
  paidEl.style.width = '0%';
  pendingEl.style.width = '0%';

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      paidEl.style.transition = 'width 0.8s cubic-bezier(0.4, 0, 0.2, 1)';
      pendingEl.style.transition = 'width 0.8s cubic-bezier(0.4, 0, 0.2, 1) 0.15s';
      paidEl.style.width = `${paidPct}%`;
      pendingEl.style.width = `${pendingPct}%`;
    });
  });

  document.getElementById('budgetLabelSpent').textContent = `$${formatNumber(spent)} PAID`;
  document.getElementById('budgetLabelRemaining').textContent = `$${formatNumber(pending)} PENDING  ·  $${formatNumber(committed)} TOTAL`;
}

let _donutAnimatedOnce = false;

function renderSpendDonut(payments, vendors) {
  const section = document.getElementById('spendDonutSection');
  if (!section) return;

  const vendorMap = {};
  vendors.forEach(v => { vendorMap[v.id] = v; });

  const vendorTotals = {};
  payments.forEach(p => {
    const amount = parseFloat(p.amount || 0);
    if (amount <= 0) return;
    const vid = p.vendor_id;
    if (!vid) return;
    vendorTotals[vid] = (vendorTotals[vid] || 0) + amount;
  });

  const sorted = Object.entries(vendorTotals)
    .map(([vid, amount]) => {
      const v = vendorMap[vid];
      const name = v ? v.name : 'Unknown';
      const color = v ? (v.icon_color || getVendorColor(v.category)) : '#A0C9CB';
      return { vid, name, amount, color };
    })
    .sort((a, b) => b.amount - a.amount);

  const totalSpend = sorted.reduce((s, e) => s + e.amount, 0);

  if (totalSpend === 0 || sorted.length === 0) { section.style.display = 'none'; return; }
  section.style.display = '';

  const amountEl = document.getElementById('spendDonutAmount');
  if (!_donutAnimatedOnce) {
    let startTime = null;
    const duration = 900;
    function countUp(ts) {
      if (!startTime) startTime = ts;
      const progress = Math.min((ts - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      amountEl.textContent = `$${formatNumber(Math.round(totalSpend * eased))}`;
      if (progress < 1) requestAnimationFrame(countUp);
    }
    requestAnimationFrame(countUp);
  } else {
    amountEl.textContent = `$${formatNumber(totalSpend)}`;
  }

  const sw = 12;
  const r = 72;
  const straight = 234;
  const halfArc = Math.PI * r;
  const circumference = 2 * straight + 2 * halfArc;
  const gapLen = 6;
  const gapCount = sorted.length > 1 ? sorted.length : 0;
  const totalGap = gapLen * gapCount;
  const usable = circumference - totalGap;

  const svgW = straight + 2 * r + sw + 4;
  const svgH = 2 * r + sw + 4;
  const svg = document.getElementById('spendDonutSvg');
  svg.setAttribute('viewBox', `0 0 ${svgW} ${svgH}`);

  const midX = svgW / 2;
  const midY = svgH / 2;
  const left = midX - straight / 2;
  const right = midX + straight / 2;
  const top_ = midY - r;
  const bot = midY + r;

  const pillPath = `M ${left} ${top_} L ${right} ${top_} A ${r} ${r} 0 1 1 ${right} ${bot} L ${left} ${bot} A ${r} ${r} 0 1 1 ${left} ${top_}`;

  const slicesEl = document.getElementById('spendDonutSlices');
  slicesEl.innerHTML = '';
  let offset = 0;

  const shouldAnimate = !_donutAnimatedOnce;

  sorted.forEach((entry, i) => {
    const frac = entry.amount / totalSpend;
    const arcLen = frac * usable;
    const pct = Math.round(frac * 100);
    const el = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    el.setAttribute('d', pillPath);
    el.setAttribute('fill', 'none');
    el.setAttribute('stroke', entry.color);
    el.setAttribute('stroke-width', `${sw}`);
    el.setAttribute('stroke-linecap', 'butt');
    el.setAttribute('stroke-dasharray', `${arcLen} ${circumference - arcLen}`);
    el.setAttribute('stroke-dashoffset', `${-offset}`);
    el.setAttribute('data-vendor-id', entry.vid);
    el.style.cursor = 'pointer';
    el.style.transition = 'stroke-width 0.15s ease';

    el.addEventListener('mouseenter', (e) => {
      el.setAttribute('stroke-width', `${sw + 4}`);
      let tip = document.getElementById('donutTooltip');
      if (!tip) {
        tip = document.createElement('div');
        tip.id = 'donutTooltip';
        tip.className = 'donut-tooltip';
        document.body.appendChild(tip);
      }
      tip.innerHTML = `<strong>${escapeHtml(entry.name)}</strong> — $${formatNumber(entry.amount)} (${pct}%)`;
      tip.style.display = 'block';
      tip.style.left = `${e.clientX}px`;
      tip.style.top = `${e.clientY - 40}px`;
    });
    el.addEventListener('mousemove', (e) => {
      const tip = document.getElementById('donutTooltip');
      if (tip) {
        tip.style.left = `${e.clientX}px`;
        tip.style.top = `${e.clientY - 40}px`;
      }
    });
    el.addEventListener('mouseleave', () => {
      el.setAttribute('stroke-width', `${sw}`);
      const tip = document.getElementById('donutTooltip');
      if (tip) tip.style.display = 'none';
    });

    if (shouldAnimate) {
      el.setAttribute('stroke-dasharray', `0 ${circumference}`);
      el.setAttribute('stroke-dashoffset', '0');

      const targetArc = arcLen;
      const targetOffset = -offset;
      const delay = i * 120;

      setTimeout(() => {
        el.style.transition = 'stroke-dasharray 0.8s cubic-bezier(0.4, 0, 0.2, 1), stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1)';
        el.setAttribute('stroke-dasharray', `${targetArc} ${circumference - targetArc}`);
        el.setAttribute('stroke-dashoffset', `${targetOffset}`);
      }, 50 + delay);
    }

    slicesEl.appendChild(el);
    offset += arcLen + (i < sorted.length - 1 ? gapLen : 0);
  });

  _donutAnimatedOnce = true;

  const legendEl = document.getElementById('spendDonutLegend');
  const half = Math.ceil(sorted.length / 2);
  const col1 = sorted.slice(0, half);
  const col2 = sorted.slice(half);
  const renderCol = (items) => items.map(entry => {
    const pct = Math.round((entry.amount / totalSpend) * 100);
    return `<div class="spend-legend-item"><span class="spend-legend-dot" style="background:${entry.color}"></span><span class="spend-legend-name">${escapeHtml(entry.name)}</span><span class="spend-legend-values">$${formatNumber(entry.amount)} <span class="spend-legend-pct">${pct}%</span></span></div>`;
  }).join('');
  legendEl.innerHTML = `<div class="spend-legend-column">${renderCol(col1)}</div><div class="spend-legend-column">${renderCol(col2)}</div>`;
}

function renderDashboardSchedule(calendar, subEvents) {
  const container = document.getElementById('dashboardSchedule');
  if (!container) return;
  
  const items = [];
  
  subEvents.forEach(se => {
    if (se.date) {
      items.push({
        name: se.name,
        date: new Date(se.date),
        type: 'subevent'
      });
    }
  });
  
  calendar.forEach(c => {
    if (c.event_date) {
      items.push({
        name: c.title,
        date: parseDateLocal(c.event_date),
        type: 'calendar',
        raw: c
      });
    }
  });
  
  items.sort((a, b) => a.date - b.date);
  const upcoming = items.filter(i => i.date >= new Date()).slice(0, 6);
  
  if (upcoming.length === 0) {
    container.innerHTML = '<div class="schedule-item-simple"><span class="schedule-name">No upcoming events</span></div>';
    return;
  }
  
  container.innerHTML = upcoming.map(item => {
    if (item.type === 'calendar' && item.raw) {
      const calJson = escapeHtml(JSON.stringify(item.raw));
      return `<div class="schedule-item-simple clickable" onclick="showCalendarEventDetail(this)" data-cal='${calJson}'>
        <span class="schedule-name">${escapeHtml(item.name)}</span>
        <span class="schedule-date">${formatShortDate(item.date)}</span>
      </div>`;
    }
    return `<div class="schedule-item-simple">
      <span class="schedule-name">${escapeHtml(item.name)}</span>
      <span class="schedule-date">${formatShortDate(item.date)}</span>
    </div>`;
  }).join('');
}

async function loadPaymentsV2() {
  if (!currentEventId) return;

  try {
    const [paymentsResponse, vendorsResponse, attachmentsResponse] = await Promise.all([
      fetch(`${API_BASE}/api/events/${currentEventId}/payments`),
      fetch(`${API_BASE}/api/events/${currentEventId}/vendors`),
      fetch(`${API_BASE}/api/events/${currentEventId}/attachments`),
    ]);

    const payments = await paymentsResponse.json();
    const vendors = await vendorsResponse.json();
    const attachments = await attachmentsResponse.json();

    renderSpendDonut(payments, vendors);

    const vendorFiles = {};
    const vendorPayments = {};
    attachments.forEach(a => {
      if (a.vendor_id) {
        if (!vendorFiles[a.vendor_id]) vendorFiles[a.vendor_id] = [];
        vendorFiles[a.vendor_id].push(a);
      }
    });
    payments.forEach(p => {
      if (p.vendor_id) {
        if (!vendorPayments[p.vendor_id]) vendorPayments[p.vendor_id] = [];
        vendorPayments[p.vendor_id].push(p);
      }
    });

    const vendorsContainer = document.getElementById('vendorsList');
    if (vendorsContainer) {
      if (vendors.length === 0) {
        vendorsContainer.innerHTML = '<div class="empty-state-v2"><p>No vendors yet</p></div>';
      } else {
        vendorsContainer.innerHTML = vendors.map((v, i) => {
          const files = vendorFiles[v.id] || [];
          const vPayments = vendorPayments[v.id] || [];
          return renderExpandableVendorCard(v, i, files, vPayments);
        }).join('');
      }
    }

    const completedPayments = payments.filter(p => p.paid_date);
    const pendingPayments = payments.filter(p => !p.paid_date);

    const paymentsContainer = document.getElementById('paymentsList');
    if (paymentsContainer) {
      if (completedPayments.length === 0) {
        paymentsContainer.innerHTML = '<div class="empty-state-v2"><p>No payments recorded</p></div>';
      } else {
        paymentsContainer.innerHTML = completedPayments.map(p => {
          const displayName = p.vendor_name || p.description || 'Payment';
          const rawPaid2 = parseFloat(p.amount_paid || 0);
          const amount = rawPaid2 > 0 ? rawPaid2 : parseFloat(p.amount || 0);
          return `
          <div class="payment-item-v2">
            <div class="payment-details">
              <div class="payment-vendor-name">${escapeHtml(displayName)}</div>
              <div class="payment-date">${p.paid_date ? formatShortDate(parseDateLocal(p.paid_date)) : ''}</div>
            </div>
            <div class="payment-amount-v2">$${formatNumber(amount)}</div>
          </div>
        `;}).join('');
      }
    }

    const pendingContainer = document.getElementById('pendingPaymentsList');
    if (pendingContainer) {
      if (pendingPayments.length === 0) {
        pendingContainer.innerHTML = '<div class="empty-state-v2"><p>No pending payments</p></div>';
      } else {
        pendingContainer.innerHTML = pendingPayments.map(p => {
          const displayName = p.vendor_name || p.description || 'Payment due';
          const amount = parseFloat(p.amount || 0);
          const dueText = p.due_date ? `Due ${formatShortDate(parseDateLocal(p.due_date))}` : 'Due date TBD';
          return `
          <div class="payment-item-v2">
            <div class="payment-details">
              <div class="payment-vendor-name">${escapeHtml(displayName)}</div>
              <div class="payment-date">${dueText}</div>
            </div>
            <div class="payment-amount-v2">$${formatNumber(amount)}</div>
          </div>
        `;}).join('');
      }
    }

  } catch (error) {
    console.error('Failed to load payments V2:', error);
  }
}

function renderExpandableVendorCard(vendor, index, files, payments) {
  const fileCount = files.length;
  const iconClass = vendor.icon_class || getVendorIcon(vendor.category);
  const iconColor = vendor.icon_color || getVendorColor(vendor.category);

  const filesHtml = files.length > 0
    ? files.map(f => renderVendorFileCard(f)).join('')
    : '<div class="vendor-empty-hint">No files attached yet</div>';

  const paymentsHtml = payments.length > 0
    ? payments.map(p => renderVendorPaymentRow(p)).join('')
    : '<div class="vendor-empty-hint">No payments recorded</div>';

  const totalPaid = payments
    .filter(p => !!p.paid_date)
    .reduce((sum, p) => {
      const paid = parseFloat(p.amount_paid || 0);
      return sum + (paid > 0 ? paid : parseFloat(p.amount || 0));
    }, 0);
  const totalDue = payments
    .filter(p => !p.paid_date)
    .reduce((sum, p) => sum + parseFloat(p.amount || 0), 0);

  const paymentSummaryHtml = payments.length > 0
    ? `<div class="vendor-payment-summary-stats">
        <span class="vp-stat vp-stat-paid"><i class="fas fa-check-circle"></i> Paid: $${formatNumber(totalPaid)}</span>
        <span class="vp-stat vp-stat-due"><i class="fas fa-exclamation-circle"></i> Due: $${formatNumber(totalDue)}</span>
      </div>`
    : '';

  return `
    <div class="vendor-item-v2 expandable" id="vendor-card-${vendor.id}">
      <div class="vendor-card-header" onclick="toggleVendorCard('${vendor.id}')">
        <div class="vendor-avatar" style="background: ${iconColor}" onclick="event.stopPropagation(); openVendorIconPicker('${vendor.id}', '${escapeHtml(vendor.name)}', '${iconClass}', '${iconColor}', '${escapeHtml(vendor.category || '')}')">
          <i class="${iconClass}"></i>
        </div>
        <div class="vendor-info">
          <div class="vendor-name">${escapeHtml(vendor.name)}</div>
          <div class="vendor-category">${escapeHtml(vendor.category || 'Vendor')}</div>
        </div>
        <div class="vendor-header-right">
          ${fileCount > 0 ? `<span class="vendor-file-count"><i class="fas fa-paperclip"></i> ${fileCount}</span>` : ''}
          <i class="fas fa-chevron-down vendor-expand-icon" id="vendor-expand-icon-${vendor.id}"></i>
        </div>
      </div>

      <div class="vendor-detail-panel" id="vendor-detail-${vendor.id}">
        <div class="vendor-files-section">
          <div class="vendor-section-header">
            <span class="vendor-section-title"><i class="fas fa-folder-open"></i> Files</span>
            <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation(); uploadFileForVendor('${vendor.id}')" title="Upload file">
              <i class="fas fa-plus"></i> Upload
            </button>
          </div>
          <div class="vendor-files-grid">${filesHtml}</div>
        </div>

        <div class="vendor-notes-section">
          <div class="vendor-section-header">
            <span class="vendor-section-title"><i class="fas fa-sticky-note"></i> Notes</span>
          </div>
          <textarea class="vendor-notes-input" id="vendor-notes-${vendor.id}"
            placeholder="Add notes about this vendor..."
            onblur="saveVendorNotes('${vendor.id}')">${vendor.notes ? escapeHtml(vendor.notes) : ''}</textarea>
          ${vendor.contact_info ? `<div class="vendor-contact"><i class="fas fa-phone"></i> ${escapeHtml(vendor.contact_info)}</div>` : ''}
        </div>

        <div class="vendor-payments-section">
          <div class="vendor-section-header">
            <span class="vendor-section-title"><i class="fas fa-dollar-sign"></i> Payments</span>
          </div>
          ${paymentSummaryHtml}
          <div class="vendor-payments-scroll">${paymentsHtml}</div>
        </div>
      </div>
    </div>
  `;
}

function renderVendorFileCard(file) {
  const ext = file.original_filename?.split('.').pop()?.toLowerCase() || '';
  const isImage = ['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext);
  const icon = getFileIcon(file.content_type, file.original_filename);
  const iconClass = getFileIconClass(file.content_type, file.original_filename);
  const truncatedName = file.original_filename.length > 18
    ? file.original_filename.substring(0, 15) + '...'
    : file.original_filename;

  return `
    <div class="vendor-file-card">
      <div class="vendor-file-icon ${iconClass}">
        <i class="${icon}"></i>
      </div>
      <div class="vendor-file-name" title="${escapeHtml(file.original_filename)}">${escapeHtml(truncatedName)}</div>
      <div class="vendor-file-btns">
        <button class="btn-icon-sm" onclick="event.stopPropagation(); previewFile('${file.id}', '${ext}', '${escapeHtml(file.original_filename)}')" title="Preview">
          <i class="fas fa-eye"></i>
        </button>
        <button class="btn-icon-sm" onclick="event.stopPropagation(); downloadFile('${file.id}')" title="Download">
          <i class="fas fa-download"></i>
        </button>
      </div>
    </div>
  `;
}

function renderVendorPaymentRow(payment) {
  const rawPaid = parseFloat(payment.amount_paid || 0);
  const rawAmt = parseFloat(payment.amount || 0);
  const amount = rawPaid > 0 ? rawPaid : rawAmt;
  const isPaid = !!payment.paid_date;
  const dateStr = isPaid
    ? formatShortDate(parseDateLocal(payment.paid_date))
    : payment.due_date ? `Due ${formatShortDate(parseDateLocal(payment.due_date))}` : '';
  const statusClass = isPaid ? 'vp-paid' : 'vp-due';
  const statusLabel = isPaid ? 'Paid' : 'Due';

  return `
    <div class="vendor-payment-row" id="vp-row-${payment.id}">
      <div class="vendor-payment-summary" onclick="event.stopPropagation(); togglePaymentDetail('${payment.id}')">
        <span class="vp-amount">$${formatNumber(amount)}</span>
        <span class="vp-date">${dateStr}</span>
        <span class="vp-status ${statusClass}">${statusLabel}</span>
        <span class="vp-method">${payment.method ? escapeHtml(payment.method) : ''}</span>
        <i class="fas fa-chevron-down vp-expand-icon" id="vp-icon-${payment.id}"></i>
      </div>
      <div class="vendor-payment-detail" id="vp-detail-${payment.id}">
        ${payment.notes ? `<div class="vp-detail-row"><strong>Notes:</strong> ${escapeHtml(payment.notes)}</div>` : ''}
        ${payment.due_date ? `<div class="vp-detail-row"><strong>Due Date:</strong> ${formatShortDate(parseDateLocal(payment.due_date))}</div>` : ''}
        ${payment.method ? `<div class="vp-detail-row"><strong>Method:</strong> ${escapeHtml(payment.method)}</div>` : ''}
        ${!payment.notes && !payment.due_date && !payment.method ? '<div class="vp-detail-row vp-detail-empty">No additional details</div>' : ''}
      </div>
    </div>
  `;
}

function toggleVendorCard(vendorId) {
  const card = document.getElementById(`vendor-card-${vendorId}`);
  const detail = document.getElementById(`vendor-detail-${vendorId}`);
  const icon = document.getElementById(`vendor-expand-icon-${vendorId}`);
  if (!detail) return;

  card.classList.toggle('expanded');

  if (card.classList.contains('expanded')) {
    detail.style.maxHeight = 'none';
    detail.style.overflow = 'auto';
    if (icon) icon.style.transform = 'rotate(180deg)';
  } else {
    detail.style.maxHeight = '0';
    detail.style.overflow = 'hidden';
    if (icon) icon.style.transform = 'rotate(0)';
  }
}

function togglePaymentDetail(paymentId) {
  const row = document.getElementById(`vp-row-${paymentId}`);
  const detail = document.getElementById(`vp-detail-${paymentId}`);
  const icon = document.getElementById(`vp-icon-${paymentId}`);
  if (!detail) return;

  row.classList.toggle('expanded');

  if (row.classList.contains('expanded')) {
    detail.style.maxHeight = detail.scrollHeight + 'px';
    if (icon) icon.style.transform = 'rotate(180deg)';
  } else {
    detail.style.maxHeight = '0';
    if (icon) icon.style.transform = 'rotate(0)';
  }
}

async function saveVendorNotes(vendorId) {
  if (!currentEventId) return;
  const textarea = document.getElementById(`vendor-notes-${vendorId}`);
  if (!textarea) return;

  try {
    await fetch(`${API_BASE}/api/events/${currentEventId}/vendors/${vendorId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes: textarea.value }),
    });
  } catch (error) {
    console.error('Failed to save vendor notes:', error);
  }
}

function openVendorIconPicker(vendorId, vendorName, currentIcon, currentColor, category) {
  let existing = document.getElementById('vendorIconPickerModal');
  if (existing) existing.remove();

  let selectedIcon = currentIcon;
  let selectedColor = currentColor;

  const iconGridHtml = VENDOR_ICON_INVENTORY.map(item => {
    const sel = item.icon === currentIcon ? ' selected' : '';
    return `<button class="vip-icon-btn${sel}" data-icon="${item.icon}" title="${item.label}"><i class="${item.icon}"></i></button>`;
  }).join('');

  const colorGridHtml = VENDOR_COLOR_PALETTE.map(c => {
    const sel = c.toLowerCase() === currentColor.toLowerCase() ? ' selected' : '';
    return `<button class="vip-color-btn${sel}" data-color="${c}" style="background:${c}"></button>`;
  }).join('');

  const modal = document.createElement('div');
  modal.id = 'vendorIconPickerModal';
  modal.className = 'vip-overlay';
  modal.innerHTML = `
    <div class="vip-panel">
      <div class="vip-header">
        <h3 class="vip-title">Customize Icon</h3>
        <button class="vip-close" onclick="closeVendorIconPicker()"><i class="fas fa-times"></i></button>
      </div>

      <div class="vip-preview">
        <div class="vip-preview-avatar" id="vipPreviewAvatar" style="background:${currentColor}">
          <i class="${currentIcon}" id="vipPreviewIcon"></i>
        </div>
        <div class="vip-preview-name">${vendorName}</div>
      </div>

      <div class="vip-section">
        <div class="vip-section-label">Icon</div>
        <div class="vip-icon-grid" id="vipIconGrid">${iconGridHtml}</div>
      </div>

      <div class="vip-section">
        <div class="vip-section-label">Background Color</div>
        <div class="vip-color-grid" id="vipColorGrid">${colorGridHtml}</div>
      </div>

      <div class="vip-actions">
        <button class="btn btn-ghost" onclick="closeVendorIconPicker()">Cancel</button>
        <button class="btn btn-primary" id="vipSaveBtn">Save</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  requestAnimationFrame(() => modal.classList.add('show'));

  modal.querySelector('#vipIconGrid').addEventListener('click', (e) => {
    const btn = e.target.closest('.vip-icon-btn');
    if (!btn) return;
    modal.querySelectorAll('.vip-icon-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    selectedIcon = btn.dataset.icon;
    const preview = document.getElementById('vipPreviewIcon');
    preview.className = selectedIcon;
  });

  modal.querySelector('#vipColorGrid').addEventListener('click', (e) => {
    const btn = e.target.closest('.vip-color-btn');
    if (!btn) return;
    modal.querySelectorAll('.vip-color-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    selectedColor = btn.dataset.color;
    document.getElementById('vipPreviewAvatar').style.background = selectedColor;
  });

  modal.querySelector('#vipSaveBtn').addEventListener('click', async () => {
    if (!currentEventId) return;
    try {
      await fetch(`${API_BASE}/api/events/${currentEventId}/vendors/${vendorId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ icon_class: selectedIcon, icon_color: selectedColor }),
      });
      const avatarEl = document.querySelector(`#vendor-card-${vendorId} .vendor-avatar`);
      if (avatarEl) {
        avatarEl.style.background = selectedColor;
        avatarEl.innerHTML = `<i class="${selectedIcon}"></i>`;
        avatarEl.setAttribute('onclick',
          `event.stopPropagation(); openVendorIconPicker('${vendorId}', '${vendorName.replace(/'/g, "\\'")}', '${selectedIcon}', '${selectedColor}', '${category.replace(/'/g, "\\'")}')`
        );
      }
      const donutSlice = document.querySelector(`#spendDonutSlices path[data-vendor-id="${vendorId}"]`);
      if (donutSlice) {
        donutSlice.setAttribute('stroke', selectedColor);
      }
      const legendDots = document.querySelectorAll('#spendDonutLegend .spend-legend-item');
      legendDots.forEach(item => {
        const nameEl = item.querySelector('.spend-legend-name');
        if (nameEl && nameEl.textContent === vendorName) {
          const dot = item.querySelector('.spend-legend-dot');
          if (dot) dot.style.background = selectedColor;
        }
      });
      closeVendorIconPicker();
    } catch (err) {
      console.error('Failed to save vendor icon:', err);
    }
  });

  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeVendorIconPicker();
  });
}

function closeVendorIconPicker() {
  const modal = document.getElementById('vendorIconPickerModal');
  if (!modal) return;
  modal.classList.remove('show');
  setTimeout(() => modal.remove(), 200);
}

function previewFile(attachmentId, ext, filename) {
  if (!currentEventId) return;
  const baseUrl = `${API_BASE}/api/events/${currentEventId}/attachments/${attachmentId}/download`;
  const inlineUrl = `${baseUrl}?inline=true`;
  const isImage = ['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext);

  if (isImage) {
    const lightbox = document.getElementById('imageLightbox');
    const img = document.getElementById('lightboxImage');
    img.src = inlineUrl;
    lightbox.classList.add('show');
  } else {
    const modal = document.getElementById('filePreviewModal');
    const frame = document.getElementById('filePreviewFrame');
    const title = document.getElementById('filePreviewTitle');
    title.textContent = filename || 'Document Preview';
    frame.src = inlineUrl;
    modal.classList.add('show');
  }
}

function closeLightbox() {
  const lightbox = document.getElementById('imageLightbox');
  lightbox.classList.remove('show');
  document.getElementById('lightboxImage').src = '';
}

function closeFilePreview() {
  const modal = document.getElementById('filePreviewModal');
  modal.classList.remove('show');
  document.getElementById('filePreviewFrame').src = '';
}

async function loadTasksKanban() {
  if (!currentEventId) return;
  
  try {
    const response = await fetch(`${API_BASE}/api/events/${currentEventId}/tasks`);
    const tasks = await response.json();
    
    const columns = {
      pending: tasks.filter(t => t.status === 'pending'),
      in_progress: tasks.filter(t => t.status === 'in_progress'),
      completed: tasks.filter(t => t.status === 'completed'),
    };
    
    const priorityOrder = { high: 0, medium: 1, low: 2 };
    for (const col of Object.values(columns)) {
      col.sort((a, b) => (priorityOrder[a.priority] || 2) - (priorityOrder[b.priority] || 2));
    }
    
    for (const [status, list] of Object.entries(columns)) {
      const container = document.getElementById(`kanban-${status}`);
      const countEl = document.getElementById(`kanban-count-${status}`);
      if (countEl) countEl.textContent = list.length;
      if (!container) continue;
      
      if (list.length === 0) {
        container.innerHTML = '<div class="kanban-empty">No tasks</div>';
      } else {
        container.innerHTML = list.map(task => renderKanbanCard(task)).join('');
      }
    }
    
    setupKanbanDragDrop();
    
  } catch (error) {
    console.error('Failed to load kanban:', error);
  }
}

function renderKanbanCard(task) {
  const categoryLabel = task.vendor_category
    ? `<span class="task-label task-label-category">${escapeHtml(task.vendor_category)}</span>`
    : '';
  const priorityLabel = task.priority
    ? `<span class="task-label task-label-priority-${task.priority}">${task.priority}</span>`
    : '';
  const dueText = task.due_date
    ? `<div class="kanban-card-due"><i class="fas fa-clock"></i> ${formatShortDate(parseDateLocal(task.due_date))}</div>`
    : '';
  const assigneeText = task.assignee
    ? `<div class="kanban-card-assignee"><i class="fas fa-user"></i> ${escapeHtml(task.assignee)}</div>`
    : '';
  
  const taskJson = escapeHtml(JSON.stringify(task));
  
  return `
    <div class="kanban-card" draggable="true" data-task-id="${task.id}" data-vendor-id="${task.vendor_id || ''}" data-task='${taskJson}'>
      <div class="kanban-card-title">${escapeHtml(task.title)}</div>
      <div class="kanban-card-footer">
        <div class="kanban-card-meta">
          ${priorityLabel}${categoryLabel}
        </div>
        ${dueText}
      </div>
      ${assigneeText ? `<div class="kanban-card-bottom">${assigneeText}</div>` : ''}
    </div>`;
}

let activeTaskId = null;
let activeTaskDescOriginal = '';
let activeTaskOriginalDate = '';
let activeTaskOriginalTime = '';
let activeTaskOriginalAllDay = false;
let activeTaskOriginalPriority = '';
let activeTaskOriginalLabel = '';
let activeTaskOriginalAssignee = '';

async function showTaskDetail(cardEl) {
  if (cardEl.classList.contains('dragging')) return;
  
  let task;
  try {
    const raw = cardEl.getAttribute('data-task');
    task = JSON.parse(raw.replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&#39;/g,"'"));
  } catch (e) {
    console.error('Failed to parse task data:', e);
    return;
  }
  
  activeTaskId = task.id;
  
  document.getElementById('taskDetailTitle').textContent = task.title || 'Untitled Task';
  
  const statusMap = { pending: 'To Do', in_progress: 'In Progress', completed: 'Done' };
  const statusClassMap = { pending: 'status-todo', in_progress: 'status-in-progress', completed: 'status-done' };
  document.getElementById('taskDetailStatus').innerHTML =
    `<span class="task-label ${statusClassMap[task.status] || 'status-todo'}">${statusMap[task.status] || task.status}</span>`;
  
  const prioSelect = document.getElementById('taskDetailPriority');
  prioSelect.innerHTML = ['low','medium','high'].map(p =>
    `<option value="${p}" ${p === (task.priority || 'medium') ? 'selected' : ''}>${p.charAt(0).toUpperCase() + p.slice(1)}</option>`
  ).join('');
  activeTaskOriginalPriority = task.priority || 'medium';
  
  const labelSelect = document.getElementById('taskDetailLabelSelect');
  await populateTaskLabelDropdown(labelSelect, task.vendor_category || '');
  activeTaskOriginalLabel = task.vendor_category || '';
  
  const dateInput = document.getElementById('taskDetailDueDate');
  const timeInput = document.getElementById('taskDetailDueTime');
  const allDayCheckbox = document.getElementById('taskDetailAllDay');
  
  dateInput.value = task.due_date || '';
  const hasTime = !!task.due_time;
  timeInput.value = task.due_time ? task.due_time.substring(0, 5) : '';
  allDayCheckbox.checked = !hasTime;
  timeInput.style.display = allDayCheckbox.checked ? 'none' : '';
  
  activeTaskOriginalDate = dateInput.value;
  activeTaskOriginalTime = timeInput.value;
  activeTaskOriginalAllDay = allDayCheckbox.checked;
  
  const vendorSection = document.getElementById('taskDetailVendorSection');
  if (task.vendor_name) {
    vendorSection.style.display = '';
    document.getElementById('taskDetailVendor').textContent = task.vendor_name;
  } else {
    vendorSection.style.display = 'none';
  }
  
  renderAssigneePills(task.assignee || '');
  activeTaskOriginalAssignee = task.assignee || '';
  
  const descEl = document.getElementById('taskDetailDescription');
  const descHtml = task.description || '';
  descEl.innerHTML = descHtml;
  activeTaskDescOriginal = descHtml;
  
  document.getElementById('taskDetailModal').classList.add('show');
}

async function populateTaskLabelDropdown(selectEl, currentCategory) {
  let options = '<option value="">None</option>';
  try {
    const resp = await fetch(`${API_BASE}/api/events/${currentEventId}/vendors`);
    if (resp.ok) {
      const vendors = await resp.json();
      const categories = [...new Set(vendors.map(v => v.category).filter(Boolean))];
      categories.sort();
      categories.forEach(cat => {
        const sel = cat === currentCategory ? ' selected' : '';
        options += `<option value="${escapeHtml(cat)}"${sel}>${escapeHtml(cat)}</option>`;
      });
    }
  } catch (e) {
    console.error('Failed to load vendor categories:', e);
  }
  selectEl.innerHTML = options;
  if (currentCategory && !selectEl.value) {
    selectEl.value = currentCategory;
  }
}

function renderAssigneePills(assigneeStr) {
  const pillsContainer = document.getElementById('assigneePills');
  const textInput = document.getElementById('assigneeTextInput');
  const names = assigneeStr ? assigneeStr.split(',').map(n => n.trim()).filter(Boolean) : [];
  pillsContainer.innerHTML = names.map(name =>
    `<span class="assignee-pill">${escapeHtml(name)}<span class="assignee-pill-remove" onclick="removeAssigneePill(this)">&times;</span></span>`
  ).join('');
  textInput.value = '';
}

function getAssigneeString() {
  const pills = document.querySelectorAll('#assigneePills .assignee-pill');
  return Array.from(pills).map(p => {
    const clone = p.cloneNode(true);
    const rm = clone.querySelector('.assignee-pill-remove');
    if (rm) rm.remove();
    return clone.textContent.trim();
  }).filter(Boolean).join(', ');
}

function removeAssigneePill(removeEl) {
  removeEl.parentElement.remove();
}

(function() {
  document.addEventListener('DOMContentLoaded', () => {
    const cb = document.getElementById('taskDetailAllDay');
    if (cb) {
      cb.addEventListener('change', function() {
        document.getElementById('taskDetailDueTime').style.display = this.checked ? 'none' : '';
      });
    }
    
    const assigneeInput = document.getElementById('assigneeTextInput');
    if (assigneeInput) {
      assigneeInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          const name = this.value.trim();
          if (!name) return;
          const pillsContainer = document.getElementById('assigneePills');
          const pill = document.createElement('span');
          pill.className = 'assignee-pill';
          pill.innerHTML = `${escapeHtml(name)}<span class="assignee-pill-remove" onclick="removeAssigneePill(this)">&times;</span>`;
          pillsContainer.appendChild(pill);
          this.value = '';
        }
        if (e.key === 'Backspace' && this.value === '') {
          const pillsContainer = document.getElementById('assigneePills');
          const lastPill = pillsContainer.lastElementChild;
          if (lastPill) lastPill.remove();
        }
      });
    }
    
    const pillInput = document.getElementById('assigneePillInput');
    if (pillInput) {
      pillInput.addEventListener('click', () => {
        document.getElementById('assigneeTextInput').focus();
      });
    }
  });
})();

function execDescCmd(command) {
  document.execCommand(command, false, null);
  document.getElementById('taskDetailDescription').focus();
}

async function closeTaskDetail() {
  const descEl = document.getElementById('taskDetailDescription');
  const newDesc = descEl.innerHTML.trim();
  
  const dateInput = document.getElementById('taskDetailDueDate');
  const timeInput = document.getElementById('taskDetailDueTime');
  const allDayCheckbox = document.getElementById('taskDetailAllDay');
  
  const newDate = dateInput.value;
  const newTime = allDayCheckbox.checked ? '' : timeInput.value;
  const newPriority = document.getElementById('taskDetailPriority').value;
  const newLabel = document.getElementById('taskDetailLabelSelect').value;
  const newAssignee = getAssigneeString();
  
  const descChanged = newDesc !== activeTaskDescOriginal;
  const dateChanged = newDate !== activeTaskOriginalDate;
  const timeChanged = newTime !== activeTaskOriginalTime;
  const prioChanged = newPriority !== activeTaskOriginalPriority;
  const labelChanged = newLabel !== activeTaskOriginalLabel;
  const assigneeChanged = newAssignee !== activeTaskOriginalAssignee;
  
  const anyChange = descChanged || dateChanged || timeChanged || prioChanged || labelChanged || assigneeChanged;
  
  if (activeTaskId && anyChange) {
    try {
      const payload = {};
      if (descChanged) payload.description = newDesc;
      if (dateChanged) payload.due_date = newDate || null;
      if (timeChanged || dateChanged) payload.due_time = (newTime && newDate) ? newTime + ':00' : null;
      if (prioChanged) payload.priority = newPriority;
      if (labelChanged) payload.vendor_category = newLabel || null;
      if (assigneeChanged) payload.assignee = newAssignee || null;
      
      await fetch(`${API_BASE}/api/events/${currentEventId}/tasks/${activeTaskId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      loadDashboardV2();
    } catch (e) {
      console.error('Failed to save task changes:', e);
    }
  }
  
  activeTaskId = null;
  activeTaskDescOriginal = '';
  activeTaskOriginalDate = '';
  activeTaskOriginalTime = '';
  activeTaskOriginalAllDay = false;
  activeTaskOriginalPriority = '';
  activeTaskOriginalLabel = '';
  activeTaskOriginalAssignee = '';
  document.getElementById('taskDetailModal').classList.remove('show');
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeTaskDetail();
});

document.addEventListener('click', (e) => {
  const modal = document.getElementById('taskDetailModal');
  if (e.target === modal) closeTaskDetail();
});

function setupKanbanDragDrop() {
  const cards = document.querySelectorAll('.kanban-card');
  const dropZones = document.querySelectorAll('.kanban-cards');
  
  cards.forEach(card => {
    let didDrag = false;
    card.addEventListener('mousedown', () => { didDrag = false; });
    card.addEventListener('dragstart', (e) => {
      didDrag = true;
      e.dataTransfer.setData('text/plain', card.dataset.taskId);
      card.classList.add('dragging');
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
      dropZones.forEach(z => z.classList.remove('kanban-drag-over'));
    });
    card.addEventListener('click', () => {
      if (didDrag) return;
      showTaskDetail(card);
    });
  });
  
  dropZones.forEach(zone => {
    zone.addEventListener('dragover', (e) => {
      e.preventDefault();
      zone.classList.add('kanban-drag-over');
    });
    zone.addEventListener('dragleave', () => {
      zone.classList.remove('kanban-drag-over');
    });
    zone.addEventListener('drop', async (e) => {
      e.preventDefault();
      zone.classList.remove('kanban-drag-over');
      const taskId = e.dataTransfer.getData('text/plain');
      const newStatus = zone.closest('.kanban-column').dataset.status;
      await updateTaskStatus(taskId, newStatus);
    });
  });
}

async function updateTaskStatus(taskId, newStatus) {
  if (!currentEventId) return;
  try {
    const response = await fetch(`${API_BASE}/api/events/${currentEventId}/tasks/${taskId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    if (response.ok) {
      loadTasksKanban();
      loadDashboardV2();
    }
  } catch (error) {
    console.error('Failed to update task status:', error);
  }
}

// ============================================
// FULL CALENDAR GRID
// ============================================

let calViewYear = null;
let calViewMonth = null;    // 0-indexed
let calWeddingDate = null;  // Date object of event start_date
let calGridData = { calendar_events: [], tasks: [] };
let editingCalEventId = null;
let _calAnimatedOnce = false;

function initCalendarGrid() {
  const prevBtn = document.getElementById('calPrevMonth');
  const nextBtn = document.getElementById('calNextMonth');
  const todayBtn = document.getElementById('calTodayBtn');
  if (prevBtn) prevBtn.addEventListener('click', () => calNavigate(-1));
  if (nextBtn) nextBtn.addEventListener('click', () => calNavigate(1));
  if (todayBtn) todayBtn.addEventListener('click', calGoToday);
  const weddingBtn = document.getElementById('calWeddingBtn');
  if (weddingBtn) weddingBtn.addEventListener('click', calGoWedding);

  const allDayCheckbox = document.getElementById('calEvtAllDay');
  if (allDayCheckbox) {
    allDayCheckbox.addEventListener('change', () => {
      document.getElementById('calEvtTime').disabled = allDayCheckbox.checked;
      if (allDayCheckbox.checked) document.getElementById('calEvtTime').value = '';
    });
  }
}

initCalendarGrid();

async function loadCalendarV2() {
  if (!currentEventId) return;

  try {
    const eventResponse = await fetch(`${API_BASE}/api/events/${currentEventId}`);
    const event = await eventResponse.json();

    if (event.start_date) {
      calWeddingDate = parseDateLocal(event.start_date);
    } else if (event.event_date) {
      calWeddingDate = parseDateLocal(event.event_date);
    } else {
      calWeddingDate = null;
    }

    const weddingBtn = document.getElementById('calWeddingBtn');
    if (weddingBtn) {
      weddingBtn.style.display = calWeddingDate ? '' : 'none';
    }

    if (calViewYear === null) {
      const now = new Date();
      calViewYear = now.getFullYear();
      calViewMonth = now.getMonth();
    }

    await fetchAndRenderCalGrid();
  } catch (error) {
    console.error('Failed to load calendar V2:', error);
  }
}

function calNavigate(delta) {
  calViewMonth += delta;
  if (calViewMonth > 11) { calViewMonth = 0; calViewYear++; }
  if (calViewMonth < 0) { calViewMonth = 11; calViewYear--; }
  fetchAndRenderCalGrid();
}

function calGoToday() {
  const now = new Date();
  calViewYear = now.getFullYear();
  calViewMonth = now.getMonth();
  fetchAndRenderCalGrid();
}

function calGoWedding() {
  if (!calWeddingDate) return;
  calViewYear = calWeddingDate.getFullYear();
  calViewMonth = calWeddingDate.getMonth();
  fetchAndRenderCalGrid();
}

async function fetchAndRenderCalGrid() {
  const firstDay = new Date(calViewYear, calViewMonth, 1);
  const startDow = firstDay.getDay();
  const gridStart = new Date(calViewYear, calViewMonth, 1 - startDow);
  const lastDay = new Date(calViewYear, calViewMonth + 1, 0);
  const endDow = lastDay.getDay();
  const gridEnd = new Date(calViewYear, calViewMonth + 1, 6 - endDow);

  const fmt = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const titleEl = document.getElementById('calMonthTitle');
  if (titleEl) {
    titleEl.textContent = firstDay.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
  }

  try {
    const resp = await fetch(
      `${API_BASE}/api/events/${currentEventId}/calendar/grid?start=${fmt(gridStart)}&end=${fmt(gridEnd)}`
    );
    calGridData = await resp.json();
  } catch (err) {
    console.error('Failed to fetch calendar grid data:', err);
    calGridData = { calendar_events: [], tasks: [], payments: [] };
  }

  renderCalGrid(gridStart, gridEnd);
}

function renderCalGrid(gridStart, gridEnd) {
  const grid = document.getElementById('calGrid');
  if (!grid) return;

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const weddingKey = calWeddingDate
    ? `${calWeddingDate.getFullYear()}-${calWeddingDate.getMonth()}-${calWeddingDate.getDate()}`
    : null;

  const eventsByDate = {};
  const tasksByDate = {};
  const paymentsByDate = {};

  (calGridData.calendar_events || []).forEach(ce => {
    const start = parseDateLocal(ce.event_date);
    const end = ce.end_date ? parseDateLocal(ce.end_date) : start;
    const d = new Date(start);
    while (d <= end) {
      const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
      if (!eventsByDate[key]) eventsByDate[key] = [];
      const isStart = d.getTime() === start.getTime();
      const isEnd = d.getTime() === end.getTime();
      const isMulti = start.getTime() !== end.getTime();
      eventsByDate[key].push({ ...ce, _isStart: isStart, _isEnd: isEnd, _isMulti: isMulti });
      d.setDate(d.getDate() + 1);
    }
  });

  (calGridData.tasks || []).forEach(t => {
    if (!t.due_date) return;
    const d = parseDateLocal(t.due_date);
    const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
    if (!tasksByDate[key]) tasksByDate[key] = [];
    tasksByDate[key].push(t);
  });

  (calGridData.payments || []).forEach(p => {
    if (!p.paid_date) return;
    const d = parseDateLocal(p.paid_date);
    const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
    if (!paymentsByDate[key]) paymentsByDate[key] = [];
    paymentsByDate[key].push(p);
  });

  const cells = [];
  const cursor = new Date(gridStart);
  const maxItems = 3;

  while (cursor <= gridEnd) {
    const dateKey = `${cursor.getFullYear()}-${cursor.getMonth()}-${cursor.getDate()}`;
    const isOutside = cursor.getMonth() !== calViewMonth;
    const isToday = cursor.getTime() === today.getTime();
    const isWedding = weddingKey && dateKey === weddingKey;
    const dateStr = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, '0')}-${String(cursor.getDate()).padStart(2, '0')}`;

    let classes = 'cal-cell';
    if (isOutside) classes += ' outside-month';
    if (isToday) classes += ' is-today';
    if (isWedding) classes += ' is-wedding-day';

    const evts = eventsByDate[dateKey] || [];
    const tsks = tasksByDate[dateKey] || [];
    const pmts = paymentsByDate[dateKey] || [];
    const allItems = [];

    evts.forEach(ce => {
      let posClass = 'cal-item-event';
      if (ce._isMulti) {
        if (ce._isStart) posClass += ' multi-start';
        else if (ce._isEnd) posClass += ' multi-end';
        else posClass += ' multi-mid';
      }
      const label = ce._isStart ? escapeHtml(ce.title) : (ce._isMulti && !ce._isStart ? '' : escapeHtml(ce.title));
      const ceJson = escapeHtml(JSON.stringify(ce));
      allItems.push(
        `<div class="cal-item ${posClass}" onclick="event.stopPropagation(); openCalEventForEdit('${ce.id}')" title="${escapeHtml(ce.title)}">${label || '&nbsp;'}</div>`
      );
    });

    tsks.forEach(t => {
      let tClass = 'cal-item cal-item-task';
      if (t.status === 'completed') tClass += ' task-completed';
      if (t.priority === 'high') tClass += ' task-high';
      allItems.push(
        `<div class="${tClass}" title="${escapeHtml(t.title)}"><i class="fas fa-check-circle" style="font-size:0.6rem;margin-right:2px;"></i>${escapeHtml(t.title)}</div>`
      );
    });

    pmts.forEach(p => {
      const label = p.vendor_name ? `$${Number(p.amount).toLocaleString()} – ${escapeHtml(p.vendor_name)}` : `$${Number(p.amount).toLocaleString()}`;
      allItems.push(
        `<div class="cal-item cal-item-payment" onclick="event.stopPropagation(); openCalPaymentForEdit('${p.id}')" title="${escapeHtml(label)}"><i class="fas fa-dollar-sign" style="font-size:0.6rem;margin-right:2px;"></i>${label}</div>`
      );
    });

    let itemsHtml = '';
    const visible = allItems.slice(0, maxItems);
    const overflow = allItems.length - maxItems;
    itemsHtml = visible.join('');
    if (overflow > 0) {
      itemsHtml += `<div class="cal-more">+${overflow} more</div>`;
    }

    cells.push(
      `<div class="${classes}" data-date="${dateStr}" onclick="onCalCellClick('${dateStr}')">
        <div class="cal-day-number">${cursor.getDate()}</div>
        <div class="cal-cell-items">${itemsHtml}</div>
      </div>`
    );

    cursor.setDate(cursor.getDate() + 1);
  }

  grid.innerHTML = cells.join('');

  if (!_calAnimatedOnce) {
    const allCells = grid.querySelectorAll('.cal-cell');
    allCells.forEach((cell, i) => {
      cell.style.opacity = '0';
      cell.style.transform = 'translateY(10px)';
      cell.style.transition = 'none';
      setTimeout(() => {
        cell.style.transition = 'opacity 0.35s ease, transform 0.35s ease';
        cell.style.opacity = '1';
        cell.style.transform = 'translateY(0)';
      }, 18 * i);
    });
    _calAnimatedOnce = true;
  }
}

// --- Calendar Event Modal ---

function onCalCellClick(dateStr) {
  editingCalEventId = null;
  const form = document.getElementById('calEventForm');
  if (form) form.reset();

  document.getElementById('calEventModalTitle').textContent = 'New Event';
  document.getElementById('calEvtStartDate').value = dateStr;
  document.getElementById('calEvtEndDate').value = '';
  document.getElementById('calEvtTitle').value = '';
  document.getElementById('calEvtNotes').value = '';
  document.getElementById('calEvtTime').value = '';
  document.getElementById('calEvtTime').disabled = true;
  document.getElementById('calEvtAllDay').checked = true;
  document.getElementById('calEvtDeleteBtn').style.display = 'none';

  document.getElementById('calEventModal').classList.add('show');
  setTimeout(() => document.getElementById('calEvtTitle').focus(), 100);
}

function openCalEventForEdit(calEventId) {
  const ce = (calGridData.calendar_events || []).find(e => e.id === calEventId);
  if (!ce) return;

  editingCalEventId = calEventId;
  document.getElementById('calEventModalTitle').textContent = 'Edit Event';
  document.getElementById('calEvtTitle').value = ce.title || '';
  document.getElementById('calEvtStartDate').value = ce.event_date || '';
  document.getElementById('calEvtEndDate').value = ce.end_date || '';
  document.getElementById('calEvtNotes').value = ce.notes || '';

  const allDay = ce.all_day !== false;
  document.getElementById('calEvtAllDay').checked = allDay;
  document.getElementById('calEvtTime').disabled = allDay;
  document.getElementById('calEvtTime').value = allDay ? '' : (ce.event_time || '');

  document.getElementById('calEvtDeleteBtn').style.display = '';
  document.getElementById('calEventModal').classList.add('show');
  setTimeout(() => document.getElementById('calEvtTitle').focus(), 100);
}

function closeCalEventModal() {
  document.getElementById('calEventModal').classList.remove('show');
  editingCalEventId = null;
}

async function saveCalEvent(e) {
  e.preventDefault();
  if (!currentEventId) return;

  const title = document.getElementById('calEvtTitle').value.trim();
  const startDate = document.getElementById('calEvtStartDate').value;
  const endDate = document.getElementById('calEvtEndDate').value || null;
  const allDay = document.getElementById('calEvtAllDay').checked;
  const timeVal = document.getElementById('calEvtTime').value || null;
  const notes = document.getElementById('calEvtNotes').value.trim() || null;

  if (!title || !startDate) return;

  const payload = {
    title,
    event_date: startDate,
    end_date: endDate,
    all_day: allDay,
    event_time: allDay ? null : timeVal,
    notes,
  };

  try {
    if (editingCalEventId) {
      await fetch(`${API_BASE}/api/events/${currentEventId}/calendar/${editingCalEventId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } else {
      await fetch(`${API_BASE}/api/events/${currentEventId}/calendar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    }

    closeCalEventModal();
    await fetchAndRenderCalGrid();
  } catch (err) {
    console.error('Failed to save calendar event:', err);
  }
}

async function deleteCalEvent() {
  if (!editingCalEventId || !currentEventId) return;

  try {
    await fetch(`${API_BASE}/api/events/${currentEventId}/calendar/${editingCalEventId}`, {
      method: 'DELETE',
    });
    closeCalEventModal();
    await fetchAndRenderCalGrid();
  } catch (err) {
    console.error('Failed to delete calendar event:', err);
  }
}

// --- Calendar Payment Modal ---

let editingCalPaymentId = null;

function openCalPaymentForEdit(paymentId) {
  const p = (calGridData.payments || []).find(pm => pm.id === paymentId);
  if (!p) return;

  editingCalPaymentId = paymentId;
  document.getElementById('calPaymentModalTitle').textContent = 'Payment Details';
  document.getElementById('calPmtVendor').value = p.vendor_name || '';
  document.getElementById('calPmtAmount').value = p.amount || '';
  document.getElementById('calPmtMethod').value = p.method || '';
  document.getElementById('calPmtPaidDate').value = p.paid_date || '';
  document.getElementById('calPmtDueDate').value = p.due_date || '';
  document.getElementById('calPmtNotes').value = p.notes || '';

  document.getElementById('calPaymentModal').classList.add('show');
}

function closeCalPaymentModal() {
  document.getElementById('calPaymentModal').classList.remove('show');
  editingCalPaymentId = null;
}

async function saveCalPayment(e) {
  e.preventDefault();
  if (!editingCalPaymentId || !currentEventId) return;

  const payload = {
    amount: parseFloat(document.getElementById('calPmtAmount').value),
    method: document.getElementById('calPmtMethod').value.trim() || null,
    paid_date: document.getElementById('calPmtPaidDate').value || null,
    due_date: document.getElementById('calPmtDueDate').value || null,
    notes: document.getElementById('calPmtNotes').value.trim() || null,
  };

  try {
    const resp = await fetch(`${API_BASE}/api/events/${currentEventId}/payments/${editingCalPaymentId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (resp.ok) {
      closeCalPaymentModal();
      await fetchAndRenderCalGrid();
    } else {
      console.error('Failed to update payment:', resp.status);
    }
  } catch (err) {
    console.error('Failed to save payment:', err);
  }
}

// ============================================
// NOTES VIEW
// ============================================

let currentNoteId = null;
let notesList = [];
let noteSaveTimer = null;

async function loadNotesView() {
  if (!currentEventId) return;

  const sidebar = document.getElementById('notesSidebar');
  if (sidebar) sidebar.classList.remove('collapsed');
  const expandBtn = document.getElementById('notesSidebarExpandBtn');
  if (expandBtn) expandBtn.style.display = 'none';
  const icon = document.getElementById('notesSidebarToggleIcon');
  if (icon) icon.className = 'fas fa-chevron-left';

  await fetchNotesList();
  renderNotesSidebar();

  if (notesList.length > 0 && !currentNoteId) {
    await selectNote(notesList[0].id);
  } else if (currentNoteId) {
    await selectNote(currentNoteId);
  } else {
    showNotesEmptyState(true);
  }
}

async function fetchNotesList() {
  try {
    const resp = await fetch(`${API_BASE}/api/events/${currentEventId}/notes`);
    if (resp.ok) {
      notesList = await resp.json();
    } else {
      notesList = [];
    }
  } catch (err) {
    console.error('Failed to fetch notes:', err);
    notesList = [];
  }
}

function renderNotesSidebar() {
  const listEl = document.getElementById('notesList');
  if (!listEl) return;

  const query = (document.getElementById('notesSearchInput')?.value || '').toLowerCase().trim();
  const filtered = query
    ? notesList.filter(n => (n.title || '').toLowerCase().includes(query) || (n._preview || '').toLowerCase().includes(query))
    : notesList;

  if (filtered.length === 0) {
    listEl.innerHTML = query
      ? '<div class="notes-list-empty">No matching notes</div>'
      : '<div class="notes-list-empty">No notes yet.<br>Click <b>+ New Note</b> to get started.</div>';
    return;
  }

  listEl.innerHTML = filtered.map(n => {
    const isActive = n.id === currentNoteId;
    const dt = new Date(n.updated_at);
    const dateStr = dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const timeStr = dt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
    const preview = escapeHtml(n._preview || '');
    return `<div class="notes-list-item${isActive ? ' active' : ''}" onclick="selectNote('${n.id}')">
      <span class="notes-list-item-title">${escapeHtml(n.title || 'Untitled')}</span>
      ${preview ? `<span class="notes-list-item-preview">${preview}</span>` : ''}
      <span class="notes-list-item-date">${dateStr}, ${timeStr}</span>
      <button class="notes-list-delete" onclick="event.stopPropagation(); deleteNoteById('${n.id}')" title="Delete"><i class="fas fa-trash-alt"></i></button>
    </div>`;
  }).join('');
}

function filterNotesList() {
  renderNotesSidebar();
}

async function selectNote(noteId) {
  if (noteSaveTimer) {
    clearTimeout(noteSaveTimer);
    noteSaveTimer = null;
    await saveCurrentNote();
  }

  try {
    const resp = await fetch(`${API_BASE}/api/events/${currentEventId}/notes/${noteId}`);
    if (!resp.ok) {
      showToast('Note not found', 'error');
      return;
    }
    const note = await resp.json();
    currentNoteId = note.id;

    document.getElementById('noteTitleInput').value = note.title || '';
    document.getElementById('notesEditor').innerHTML = note.content || '';
    updateNoteTimestamp(note.updated_at);
    updateWordCount();
    showNotesEmptyState(false);

    const idx = notesList.findIndex(n => n.id === note.id);
    if (idx !== -1) {
      notesList[idx]._preview = extractPreview(note.content);
    }
    renderNotesSidebar();
  } catch (err) {
    console.error('Failed to load note:', err);
  }
}

function extractPreview(html) {
  if (!html) return '';
  const tmp = document.createElement('div');
  tmp.innerHTML = html;
  const text = tmp.textContent || '';
  return text.substring(0, 80).trim();
}

function updateWordCount() {
  const el = document.getElementById('notesWordCount');
  if (!el) return;
  const editor = document.getElementById('notesEditor');
  if (!editor) return;
  const text = (editor.textContent || '').trim();
  const words = text ? text.split(/\s+/).length : 0;
  el.textContent = `${words} word${words !== 1 ? 's' : ''}`;
}

function showNotesEmptyState(show) {
  const editorArea = document.getElementById('notesEditorArea');
  if (!editorArea) return;
  if (show) {
    editorArea.classList.add('no-note');
    currentNoteId = null;
  } else {
    editorArea.classList.remove('no-note');
  }
}

function updateNoteTimestamp(isoStr) {
  const el = document.getElementById('noteUpdatedAt');
  if (!el || !isoStr) { if (el) el.textContent = ''; return; }
  const dt = new Date(isoStr);
  const dateStr = dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  const timeStr = dt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  el.textContent = `Last updated ${dateStr} ${timeStr}`;
}

async function createNewNote() {
  if (!currentEventId) return;

  if (noteSaveTimer) {
    clearTimeout(noteSaveTimer);
    noteSaveTimer = null;
    await saveCurrentNote();
  }

  try {
    const resp = await fetch(`${API_BASE}/api/events/${currentEventId}/notes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'Untitled Note', content: '' }),
    });
    if (resp.ok) {
      const note = await resp.json();
      await fetchNotesList();
      currentNoteId = note.id;
      document.getElementById('noteTitleInput').value = note.title || '';
      document.getElementById('notesEditor').innerHTML = note.content || '';
      updateNoteTimestamp(note.updated_at);
      updateWordCount();
      showNotesEmptyState(false);
      renderNotesSidebar();
      setTimeout(() => document.getElementById('noteTitleInput').select(), 100);
    } else {
      const err = await resp.text();
      console.error('Failed to create note:', resp.status, err);
      showToast('Failed to create note', 'error');
    }
  } catch (err) {
    console.error('Failed to create note:', err);
    showToast('Failed to create note', 'error');
  }
}

async function saveCurrentNote() {
  if (!currentNoteId || !currentEventId) return;

  const title = document.getElementById('noteTitleInput').value.trim() || 'Untitled Note';
  const content = document.getElementById('notesEditor').innerHTML;

  try {
    const resp = await fetch(`${API_BASE}/api/events/${currentEventId}/notes/${currentNoteId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, content }),
    });
    if (resp.ok) {
      const note = await resp.json();
      updateNoteTimestamp(note.updated_at);
      updateWordCount();
      const idx = notesList.findIndex(n => n.id === currentNoteId);
      if (idx !== -1) {
        notesList[idx].title = note.title;
        notesList[idx].updated_at = note.updated_at;
        notesList[idx]._preview = extractPreview(note.content);
      }
      renderNotesSidebar();
      flashSaveStatus();
    }
  } catch (err) {
    console.error('Failed to save note:', err);
  }
}

function flashSaveStatus() {
  const el = document.getElementById('notesSaveStatus');
  if (!el) return;
  el.textContent = 'Saved';
  el.classList.add('visible');
  setTimeout(() => el.classList.remove('visible'), 1500);
}

function scheduleNoteSave() {
  if (noteSaveTimer) clearTimeout(noteSaveTimer);
  noteSaveTimer = setTimeout(() => {
    noteSaveTimer = null;
    saveCurrentNote();
  }, 1000);
}

function downloadCurrentNote() {
  if (!currentNoteId) return;
  const title = (document.getElementById('noteTitleInput').value.trim() || 'Untitled Note');
  const editor = document.getElementById('notesEditor');
  if (!editor) return;
  const text = editor.innerText || '';
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = title.replace(/[^a-zA-Z0-9_\- ]/g, '').trim() + '.txt';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function deleteCurrentNote() {
  if (!currentNoteId || !currentEventId) return;
  await deleteNoteById(currentNoteId);
}

async function deleteNoteById(noteId) {
  if (!currentEventId || !noteId) return;
  if (!confirm('Delete this note?')) return;

  try {
    await fetch(`${API_BASE}/api/events/${currentEventId}/notes/${noteId}`, {
      method: 'DELETE',
    });

    const wasCurrent = noteId === currentNoteId;
    if (wasCurrent) currentNoteId = null;

    await fetchNotesList();
    renderNotesSidebar();

    if (wasCurrent) {
      if (notesList.length > 0) {
        await selectNote(notesList[0].id);
      } else {
        document.getElementById('noteTitleInput').value = '';
        document.getElementById('notesEditor').innerHTML = '';
        document.getElementById('noteUpdatedAt').textContent = '';
        const wc = document.getElementById('notesWordCount');
        if (wc) wc.textContent = '';
        showNotesEmptyState(true);
      }
    }
  } catch (err) {
    console.error('Failed to delete note:', err);
  }
}

function toggleNotesSidebar() {
  const sidebar = document.getElementById('notesSidebar');
  const expandBtn = document.getElementById('notesSidebarExpandBtn');
  const icon = document.getElementById('notesSidebarToggleIcon');

  if (!sidebar) return;

  const isCollapsed = sidebar.classList.toggle('collapsed');
  if (expandBtn) expandBtn.style.display = isCollapsed ? '' : 'none';
  if (icon) icon.className = isCollapsed ? 'fas fa-chevron-right' : 'fas fa-chevron-left';
}

function execFmt(command) {
  document.execCommand(command, false, null);
  document.getElementById('notesEditor').focus();
  updateToolbarState();
}

function applyBlockFormat(tag) {
  const editor = document.getElementById('notesEditor');
  if (!editor) return;
  editor.focus();

  const sel = window.getSelection();
  if (!sel.rangeCount) return;

  const range = sel.getRangeAt(0);
  let node = range.startContainer;
  if (node.nodeType === Node.TEXT_NODE) node = node.parentNode;

  const block = node.closest('h1, h2, h3, p, div');
  if (block && editor.contains(block) && block !== editor) {
    const newEl = document.createElement(tag);
    newEl.innerHTML = block.innerHTML;
    block.replaceWith(newEl);
    const r = document.createRange();
    r.selectNodeContents(newEl);
    r.collapse(false);
    sel.removeAllRanges();
    sel.addRange(r);
  } else {
    document.execCommand('formatBlock', false, `<${tag}>`);
  }

  updateToolbarState();
  scheduleNoteSave();
}

function updateToolbarState() {
  const commands = ['bold', 'italic', 'underline', 'strikethrough', 'insertUnorderedList', 'insertOrderedList'];
  document.querySelectorAll('.notes-fmt-btn').forEach(btn => {
    const onclick = btn.getAttribute('onclick') || '';
    const match = onclick.match(/execFmt\('(\w+)'\)/);
    if (match) {
      const cmd = match[1];
      btn.classList.toggle('active', document.queryCommandState(cmd));
    }
  });

  const block = document.queryCommandValue('formatBlock');
  const sel = document.getElementById('notesBlockFormat');
  if (sel) {
    if (block === 'h1') sel.value = 'h1';
    else if (block === 'h2') sel.value = 'h2';
    else if (block === 'h3') sel.value = 'h3';
    else sel.value = 'p';
  }
}

(function initNotesEditorListeners() {
  document.addEventListener('DOMContentLoaded', () => {
    const editor = document.getElementById('notesEditor');
    const titleInput = document.getElementById('noteTitleInput');

    if (editor) {
      editor.addEventListener('input', () => { scheduleNoteSave(); updateWordCount(); });
      editor.addEventListener('keyup', updateToolbarState);
      editor.addEventListener('mouseup', updateToolbarState);
    }

    if (titleInput) {
      titleInput.addEventListener('input', scheduleNoteSave);
    }
  });
})();

// ============================================
// FILES VIEW
// ============================================

function setupFileDragDrop() {
  const dropZone = document.getElementById('fileDropZone');
  const fileInput = document.getElementById('fileInput');
  if (!dropZone || !fileInput) return;

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });

  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('drag-over');
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length > 0) handleFileUploads(files);
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
      handleFileUploads(fileInput.files);
      fileInput.value = '';
    }
  });
}

async function handleFileUploads(fileList) {
  if (!currentEventId) {
    showToast('Please select an event first', 'error');
    return;
  }

  const dropZone = document.getElementById('fileDropZone');
  const originalHtml = dropZone.innerHTML;
  dropZone.innerHTML = '<i class="fas fa-spinner fa-spin"></i><p>Uploading...</p>';

  let successCount = 0;
  let errorCount = 0;
  const pdfAttachmentIds = [];

  for (const file of fileList) {
    try {
      const result = await uploadSingleFile(file);
      successCount++;
      const ext = file.name?.split('.').pop()?.toLowerCase() || '';
      if (ext === 'pdf') pdfAttachmentIds.push(result.id);
    } catch (error) {
      errorCount++;
      console.error('Upload failed:', file.name, error);
    }
  }

  dropZone.innerHTML = originalHtml;
  setupFileDragDrop();

  if (successCount > 0) {
    showToast(`Uploaded ${successCount} file${successCount > 1 ? 's' : ''}`, 'success');
    await loadFilesV2();
    for (const attId of pdfAttachmentIds) {
      pollIndexingStatus(attId);
    }
  }
  if (errorCount > 0) {
    showToast(`${errorCount} file${errorCount > 1 ? 's' : ''} failed to upload`, 'error');
  }
}

async function uploadSingleFile(file, metadata = {}) {
  const formData = new FormData();
  formData.append('file', file);
  if (metadata.description) formData.append('description', metadata.description);
  if (metadata.category) formData.append('category', metadata.category);
  if (metadata.vendor_id) formData.append('vendor_id', metadata.vendor_id);
  if (metadata.payment_id) formData.append('payment_id', metadata.payment_id);

  const response = await fetch(`${API_BASE}/api/events/${currentEventId}/attachments`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Upload failed');
  }

  const result = await response.json();
  return result;
}

async function loadFilesV2() {
  if (!currentEventId) return;

  const categoryFilter = document.getElementById('fileCategoryFilter')?.value || '';
  const vendorFilter = document.getElementById('fileVendorFilter')?.value || '';
  const sortBy = document.getElementById('fileSortBy')?.value || 'created_at';

  const params = new URLSearchParams();
  if (categoryFilter) params.set('category', categoryFilter);
  if (vendorFilter) params.set('vendor_id', vendorFilter);
  params.set('sort_by', sortBy);
  params.set('sort_order', fileSortOrder);

  try {
    const [filesResponse, vendorsResponse] = await Promise.all([
      fetch(`${API_BASE}/api/events/${currentEventId}/attachments?${params}`),
      fetch(`${API_BASE}/api/events/${currentEventId}/vendors`),
    ]);

    const files = await filesResponse.json();
    const vendors = await vendorsResponse.json();

    populateVendorFilter(vendors);
    renderFileGrid(files, vendors);
  } catch (error) {
    console.error('Failed to load files:', error);
  }
}

function populateVendorFilter(vendors) {
  const select = document.getElementById('fileVendorFilter');
  if (!select) return;

  const currentValue = select.value;
  const options = '<option value="">All Vendors</option>' +
    vendors.map(v => `<option value="${v.id}">${escapeHtml(v.name)}</option>`).join('');
  select.innerHTML = options;
  select.value = currentValue;
}

function renderFileGrid(files, vendors) {
  const container = document.getElementById('fileGrid');
  if (!container) return;

  if (files.length === 0) {
    container.innerHTML = `
      <div class="empty-state-v2">
        <div class="empty-state-icon"><i class="fas fa-folder-open"></i></div>
        <p>No files yet. Upload contracts, receipts, or photos.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = files.map(file => renderFileCard(file, vendors)).join('');
}

function renderFileCard(file, vendors) {
  const icon = getFileIcon(file.content_type, file.original_filename);
  const iconClass = getFileIconClass(file.content_type, file.original_filename);
  const size = formatFileSize(file.file_size);
  const date = formatShortDate(new Date(file.created_at));
  const category = file.category || 'other';
  const categoryLabel = category.charAt(0).toUpperCase() + category.slice(1);
  const ext = file.original_filename?.split('.').pop()?.toLowerCase() || '';
  const isPdf = ext === 'pdf';

  const vendorOptions = vendors.map(v =>
    `<option value="${v.id}" ${file.vendor_id === v.id ? 'selected' : ''}>${escapeHtml(v.name)}</option>`
  ).join('');

  return `
    <div class="file-card" id="file-card-${file.id}">
      <div class="file-card-icon ${iconClass}">
        <i class="${icon}"></i>
      </div>
      <div class="file-card-body">
        <div class="file-card-name" title="${escapeHtml(file.original_filename)}">${escapeHtml(file.original_filename)}</div>
        <div class="file-card-meta">
          <span>${size}</span>
          <span>${date}</span>
        </div>
        <div class="file-card-tags">
          <span class="file-category-tag tag-${category}">${categoryLabel}</span>
          ${file.vendor_name ? `<span class="file-vendor-tag"><i class="fas fa-store"></i> ${escapeHtml(file.vendor_name)}</span>` : ''}
        </div>
        ${isPdf ? `<div class="indexing-bar-container" id="indexing-bar-${file.id}"></div>` : ''}
      </div>
      <div class="file-card-actions">
        <button class="btn btn-ghost btn-sm" onclick="downloadFile('${file.id}')" title="Download">
          <i class="fas fa-download"></i>
        </button>
        <button class="btn btn-ghost btn-sm" onclick="showEditFileModal('${file.id}')" title="Edit">
          <i class="fas fa-pen"></i>
        </button>
        <button class="btn btn-ghost btn-sm" onclick="deleteFile('${file.id}')" title="Delete">
          <i class="fas fa-trash"></i>
        </button>
      </div>
    </div>
  `;
}

const INDEXING_STAGE_LABELS = {
  pending: 'Queued for indexing…',
  extracting: 'Extracting text…',
  chunking: 'Splitting into sections…',
  embedding: 'Generating embeddings…',
  done: 'Indexed & searchable',
  error: 'Indexing failed',
};

const _activePollers = new Set();

function pollIndexingStatus(attachmentId) {
  if (_activePollers.has(attachmentId)) return;
  _activePollers.add(attachmentId);

  const container = document.getElementById(`indexing-bar-${attachmentId}`);
  if (!container) { _activePollers.delete(attachmentId); return; }

  container.innerHTML = `
    <div class="indexing-progress">
      <div class="indexing-progress-track">
        <div class="indexing-progress-fill" style="width: 0%"></div>
      </div>
      <span class="indexing-progress-label">Queued for indexing…</span>
    </div>`;

  async function tick() {
    try {
      const res = await fetch(`${API_BASE}/api/events/${currentEventId}/attachments/${attachmentId}/indexing-status`);
      const data = await res.json();
      const el = document.getElementById(`indexing-bar-${attachmentId}`);
      if (!el) { _activePollers.delete(attachmentId); return; }

      const fill = el.querySelector('.indexing-progress-fill');
      const label = el.querySelector('.indexing-progress-label');
      if (!fill || !label) { _activePollers.delete(attachmentId); return; }

      fill.style.width = `${data.percent}%`;
      label.textContent = INDEXING_STAGE_LABELS[data.stage] || data.stage;

      if (data.stage === 'done') {
        fill.classList.add('indexing-complete');
        setTimeout(() => {
          el.style.transition = 'opacity 0.6s ease, max-height 0.6s ease';
          el.style.opacity = '0';
          el.style.maxHeight = '0';
          setTimeout(() => { el.remove(); }, 600);
        }, 2000);
        _activePollers.delete(attachmentId);
        return;
      }

      if (data.stage === 'error') {
        fill.classList.add('indexing-error');
        label.textContent = `Indexing failed: ${data.error || 'unknown'}`;
        _activePollers.delete(attachmentId);
        return;
      }

      setTimeout(tick, 800);
    } catch {
      _activePollers.delete(attachmentId);
    }
  }

  tick();
}

function getFileIcon(contentType, filename) {
  const ext = filename?.split('.').pop()?.toLowerCase() || '';
  if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) return 'fas fa-image';
  if (ext === 'pdf') return 'fas fa-file-pdf';
  if (['doc', 'docx'].includes(ext)) return 'fas fa-file-word';
  if (['xls', 'xlsx', 'csv'].includes(ext)) return 'fas fa-file-excel';
  if (ext === 'txt') return 'fas fa-file-alt';
  return 'fas fa-file';
}

function getFileIconClass(contentType, filename) {
  const ext = filename?.split('.').pop()?.toLowerCase() || '';
  if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) return 'icon-image';
  if (ext === 'pdf') return 'icon-pdf';
  if (['doc', 'docx'].includes(ext)) return 'icon-doc';
  if (['xls', 'xlsx', 'csv'].includes(ext)) return 'icon-spreadsheet';
  return 'icon-other';
}

function formatFileSize(bytes) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let size = bytes;
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024;
    i++;
  }
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function filterFiles() {
  loadFilesV2();
}

function toggleFileSortOrder() {
  fileSortOrder = fileSortOrder === 'desc' ? 'asc' : 'desc';
  const icon = document.getElementById('fileSortOrderIcon');
  if (icon) {
    icon.className = fileSortOrder === 'desc' ? 'fas fa-sort-amount-down' : 'fas fa-sort-amount-up';
  }
  loadFilesV2();
}

function downloadFile(attachmentId) {
  if (!currentEventId) return;
  const url = `${API_BASE}/api/events/${currentEventId}/attachments/${attachmentId}/download`;
  const a = document.createElement('a');
  a.href = url;
  a.download = '';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

async function deleteFile(attachmentId) {
  if (!currentEventId) return;
  if (!confirm('Delete this file? This cannot be undone.')) return;

  try {
    const response = await fetch(`${API_BASE}/api/events/${currentEventId}/attachments/${attachmentId}`, {
      method: 'DELETE',
    });

    if (response.ok) {
      showToast('File deleted', 'success');
      loadFilesV2();
      if (currentView === 'payments') loadPaymentsV2();
    } else {
      showToast('Failed to delete file', 'error');
    }
  } catch (error) {
    console.error('Delete file error:', error);
    showToast('Failed to delete file', 'error');
  }
}

let editingFileId = null;

async function showEditFileModal(attachmentId) {
  if (!currentEventId) return;

  try {
    const [fileResponse, vendorsResponse] = await Promise.all([
      fetch(`${API_BASE}/api/events/${currentEventId}/attachments/${attachmentId}`),
      fetch(`${API_BASE}/api/events/${currentEventId}/vendors`),
    ]);

    const file = await fileResponse.json();
    const vendors = await vendorsResponse.json();

    editingFileId = attachmentId;

    const modal = document.getElementById('editFileModal');
    document.getElementById('editFileDescription').value = file.description || '';
    document.getElementById('editFileCategory').value = file.category || '';

    const vendorSelect = document.getElementById('editFileVendor');
    vendorSelect.innerHTML = '<option value="">None</option>' +
      vendors.map(v => `<option value="${v.id}" ${file.vendor_id === v.id ? 'selected' : ''}>${escapeHtml(v.name)}</option>`).join('');

    modal.classList.add('show');
  } catch (error) {
    console.error('Failed to load file details:', error);
    showToast('Failed to load file details', 'error');
  }
}

function hideEditFileModal() {
  document.getElementById('editFileModal').classList.remove('show');
  editingFileId = null;
}

async function saveFileChanges(e) {
  e.preventDefault();
  if (!editingFileId || !currentEventId) return;

  const data = {
    description: document.getElementById('editFileDescription').value.trim() || null,
    category: document.getElementById('editFileCategory').value || null,
    vendor_id: document.getElementById('editFileVendor').value || null,
  };

  try {
    const response = await fetch(`${API_BASE}/api/events/${currentEventId}/attachments/${editingFileId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    if (response.ok) {
      showToast('File updated', 'success');
      hideEditFileModal();
      loadFilesV2();
    } else {
      showToast('Failed to update file', 'error');
    }
  } catch (error) {
    console.error('Update file error:', error);
    showToast('Failed to update file', 'error');
  }
}

async function uploadFileForVendor(vendorId) {
  const input = document.createElement('input');
  input.type = 'file';
  input.multiple = true;
  input.accept = '.pdf,.jpg,.jpeg,.png,.gif,.webp,.doc,.docx,.xls,.xlsx,.csv,.txt';

  input.addEventListener('change', async () => {
    if (input.files.length === 0) return;

    let successCount = 0;
    const pdfIds = [];
    for (const file of input.files) {
      try {
        const result = await uploadSingleFile(file, { vendor_id: vendorId });
        successCount++;
        const ext = file.name?.split('.').pop()?.toLowerCase() || '';
        if (ext === 'pdf') pdfIds.push(result.id);
      } catch (error) {
        console.error('Vendor upload failed:', error);
      }
    }

    if (successCount > 0) {
      showToast(`Uploaded ${successCount} file${successCount > 1 ? 's' : ''} for vendor`, 'success');
      await loadFilesV2();
      loadPaymentsV2();
      for (const attId of pdfIds) pollIndexingStatus(attId);
    }
  });

  input.click();
}

/* ── AI Ops Panel ── */

function openAiOpsPanel() {
  const overlay = document.getElementById('opsOverlay');
  if (!overlay) return;
  overlay.classList.add('show');
  loadOpsData();
}

function closeAiOpsPanel() {
  const overlay = document.getElementById('opsOverlay');
  if (overlay) overlay.classList.remove('show');
}

async function loadOpsData() {
  try {
    const [summaryRes, recentRes, healthRes] = await Promise.all([
      fetch(`${API_BASE}/api/admin/metrics/summary?days=7`),
      fetch(`${API_BASE}/api/admin/metrics/recent?limit=50`),
      fetch(`${API_BASE}/api/admin/metrics/health`),
    ]);
    const summary = await summaryRes.json();
    const recent = await recentRes.json();
    const health = await healthRes.json();

    renderOpsHealth(health);
    renderOpsModel(summary);
    renderOpsStats(summary);
    renderOpsActivityChart(summary.daily);
    renderOpsIntentChart(summary.intent_breakdown);
    renderOpsLatencyChart(summary.daily);
    renderOpsRag(summary);
    renderOpsLog(recent);
  } catch (err) {
    console.error('Failed to load AI Ops data:', err);
  }
}

function renderOpsHealth(h) {
  const el = document.getElementById('opsHealthBar');
  let cls = 'healthy', icon = 'fa-check-circle', label = 'All Systems Operational';
  if (h.error_rate_1h > 0.5) { cls = 'down'; icon = 'fa-exclamation-triangle'; label = 'High Error Rate'; }
  else if (h.error_rate_1h > 0.1) { cls = 'degraded'; icon = 'fa-exclamation-circle'; label = 'Degraded Performance'; }
  const p50 = h.p50_latency_ms != null ? `${h.p50_latency_ms}ms` : '—';
  const p95 = h.p95_latency_ms != null ? `${h.p95_latency_ms}ms` : '—';
  el.className = `ops-health-bar ${cls}`;
  el.innerHTML = `<i class="fas ${icon}"></i> ${label} <span style="margin-left:auto;font-weight:400;opacity:0.8">p50 ${p50} · p95 ${p95} · ${h.total_calls_1h} calls/hr</span>`;
}

function renderOpsModel(s) {
  const el = document.getElementById('opsModelBar');
  const tiers = s.model_tiers || [];
  const counts = s.models_used || {};
  if (tiers.length === 0 && !s.primary_model) { el.innerHTML = ''; return; }

  if (tiers.length === 0) {
    el.innerHTML = `<span style="color:#a08070">Model</span> <span class="ops-model-badge"><i class="fas fa-microchip"></i> ${s.primary_model}</span>`;
    return;
  }

  const tierColors = { Fast: '#87A878', Balanced: '#FF9F1C', Strong: '#CB997E', Embedding: '#A0C9CB' };
  const tierIcons = { Fast: 'fa-bolt', Balanced: 'fa-microchip', Strong: 'fa-brain', Embedding: 'fa-vector-square' };
  const badges = tiers.map(t => {
    const short = t.model.replace(/^google\//, '').replace(/^openai\//, '');
    const color = tierColors[t.tier] || '#FF9F1C';
    const icon = tierIcons[t.tier] || 'fa-microchip';
    const callCount = counts[t.model] || 0;
    const countTag = callCount > 0 ? ` <span style="opacity:0.5">(${callCount})</span>` : '';
    return `<span class="ops-model-badge" style="background:${color}22;color:${color};border:1px solid ${color}33" title="${t.purpose}">
      <i class="fas ${icon}" style="font-size:0.65rem"></i>
      <span style="font-weight:600;text-transform:uppercase;font-size:0.55rem;letter-spacing:0.5px;opacity:0.7">${t.tier}</span>
      ${short}${countTag}
    </span>`;
  }).join('');
  el.innerHTML = `<span style="color:#a08070">Model Tiers</span> ${badges}`;
}

function renderOpsStats(s) {
  const el = document.getElementById('opsStatsRow');
  const errPct = (s.error_rate * 100).toFixed(1);
  const lbt = s.latency_by_type || {};
  const extMs = lbt.extraction_ms != null ? `${lbt.extraction_ms.toFixed(0)}ms` : '—';
  const ragMs = lbt.rag_query_ms != null ? `${lbt.rag_query_ms.toFixed(0)}ms` : '—';
  const embMs = lbt.embedding_ms != null ? `${lbt.embedding_ms.toFixed(0)}ms` : '—';
  el.innerHTML = `
    <div class="ops-stat"><span class="ops-stat-value">${s.total_llm_calls}</span><span class="ops-stat-label">Total Calls</span></div>
    <div class="ops-stat"><span class="ops-stat-value">${formatNumber(s.total_tokens)}</span><span class="ops-stat-label">Tokens Used</span></div>
    <div class="ops-stat"><span class="ops-stat-value">$${s.estimated_cost_usd.toFixed(4)}</span><span class="ops-stat-label">Est. Cost</span></div>
    <div class="ops-stat"><span class="ops-stat-value">${s.avg_latency_ms.toFixed(0)}<small>ms</small></span><span class="ops-stat-label">Avg Latency</span></div>
    <div class="ops-stat"><span class="ops-stat-value">${errPct}%</span><span class="ops-stat-label">Error Rate</span></div>
  `;

  let breakdownEl = document.getElementById('opsLatencyBreakdown');
  if (!breakdownEl) {
    breakdownEl = document.createElement('div');
    breakdownEl.id = 'opsLatencyBreakdown';
    breakdownEl.className = 'ops-stats-row';
    breakdownEl.style.marginTop = '8px';
    el.parentNode.insertBefore(breakdownEl, el.nextSibling);
  }
  breakdownEl.innerHTML = `
    <div class="ops-stat"><span class="ops-stat-value">${extMs}</span><span class="ops-stat-label">Extraction</span></div>
    <div class="ops-stat"><span class="ops-stat-value">${ragMs}</span><span class="ops-stat-label">RAG Query</span></div>
    <div class="ops-stat"><span class="ops-stat-value">${embMs}</span><span class="ops-stat-label">Embedding</span></div>
  `;
}

function renderOpsActivityChart(daily) {
  const el = document.getElementById('opsActivityChart');
  if (!daily || daily.length === 0) { el.innerHTML = '<div style="color:#a08070;font-size:0.8rem;padding:20px">No data yet</div>'; return; }
  const maxVal = Math.max(...daily.map(d => d.extractions + d.rag_queries + d.embeddings), 1);
  const vw = 500, h = 120;
  const padBot = 20, padTop = 22;
  const barW = vw / Math.max(daily.length, 1);
  let bars = '';
  daily.forEach((d, i) => {
    const total = d.extractions + d.rag_queries + d.embeddings;
    const barH = Math.max((total / maxVal) * (h - padTop - padBot), 3);
    const x = i * barW + barW * 0.15;
    const w = barW * 0.7;
    const barY = h - padBot - barH;
    const dayLabel = d.date.slice(5);
    bars += `<rect x="${x}" y="${barY}" width="${w}" height="${barH}" rx="3" fill="var(--accent-orange,#FF9F1C)" opacity="0.85"/>`;
    bars += `<text x="${x + w / 2}" y="${barY - 5}" text-anchor="middle" fill="#e8ddd4" font-size="12" font-weight="600" font-family="var(--font-body)">${total}</text>`;
    bars += `<text x="${x + w / 2}" y="${h - 4}" text-anchor="middle" fill="#a08070" font-size="11" font-family="var(--font-body)">${dayLabel}</text>`;
  });
  el.innerHTML = `<svg width="100%" height="${h}" viewBox="0 0 ${vw} ${h}" preserveAspectRatio="xMidYMid meet">${bars}</svg>`;
}

function renderOpsIntentChart(breakdown) {
  const el = document.getElementById('opsIntentChart');
  if (!breakdown || breakdown.length === 0) { el.innerHTML = '<div style="color:#a08070;font-size:0.8rem;padding:20px">No data yet</div>'; return; }
  const maxCount = Math.max(...breakdown.map(b => b.count), 1);
  const colors = ['#FF9F1C', '#733635', '#CB997E', '#A0C9CB', '#87A878', '#FFBF69', '#D4A373', '#B4A7D6'];
  let html = '';
  breakdown.slice(0, 8).forEach((b, i) => {
    const pct = (b.count / maxCount) * 100;
    const c = colors[i % colors.length];
    html += `<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
      <span style="width:110px;flex-shrink:0;font-size:0.75rem;color:#d5ccc4">${b.intent}</span>
      <div style="flex:1;height:14px;background:rgba(255,255,255,0.08);border-radius:7px;overflow:hidden">
        <div style="width:${pct}%;height:100%;background:${c};border-radius:7px;transition:width 0.6s ease"></div>
      </div>
      <span style="width:28px;flex-shrink:0;text-align:right;font-size:0.72rem;color:#a08070">${b.count}</span>
    </div>`;
  });
  el.innerHTML = html;
}

function renderOpsLatencyChart(daily) {
  const el = document.getElementById('opsLatencyChart');
  if (!daily || daily.length === 0) { el.innerHTML = '<div style="color:#a08070;font-size:0.8rem;padding:20px">No data yet</div>'; return; }
  const latencies = daily.map(d => d.avg_latency_ms);
  const maxL = Math.max(...latencies, 1);
  const vw = 500, h = 120;
  const padTop = 22, padBot = 20;
  const usableH = h - padTop - padBot;
  let points = '';
  let area = `M 0 ${h - padBot} `;
  daily.forEach((d, i) => {
    const x = daily.length > 1 ? (i / (daily.length - 1)) * vw : vw / 2;
    const y = padTop + usableH - (d.avg_latency_ms / maxL) * usableH;
    const ms = d.avg_latency_ms;
    const label = ms >= 1000 ? (ms / 1000).toFixed(1) + 's' : ms.toFixed(0) + 'ms';
    const color = ms > 10000 ? '#e85d5d' : ms > 5000 ? '#FF9F1C' : '#87A878';
    points += `<circle cx="${x}" cy="${y}" r="5" fill="${color}"/>`;
    points += `<text x="${x}" y="${y - 10}" text-anchor="middle" fill="#e8ddd4" font-size="12" font-weight="600" font-family="var(--font-body)">${label}</text>`;
    points += `<text x="${x}" y="${h - 4}" text-anchor="middle" fill="#a08070" font-size="11" font-family="var(--font-body)">${d.date.slice(5)}</text>`;
    area += `L ${x} ${y} `;
  });
  area += `L ${vw} ${h - padBot} Z`;
  const line = daily.map((d, i) => {
    const x = daily.length > 1 ? (i / (daily.length - 1)) * vw : vw / 2;
    const y = padTop + usableH - (d.avg_latency_ms / maxL) * usableH;
    return `${x},${y}`;
  }).join(' ');
  el.innerHTML = `<svg width="100%" height="${h}" viewBox="0 0 ${vw} ${h}" preserveAspectRatio="xMidYMid meet">
    <path d="${area}" fill="rgba(255,159,28,0.12)"/>
    <polyline points="${line}" fill="none" stroke="var(--accent-orange,#FF9F1C)" stroke-width="2.5" stroke-linejoin="round"/>
    ${points}
  </svg>`;
}

function renderOpsRag(s) {
  const el = document.getElementById('opsRagStats');
  const score = s.avg_rag_score != null ? s.avg_rag_score.toFixed(3) : '—';
  const chunks = s.avg_rag_chunks_returned != null ? s.avg_rag_chunks_returned.toFixed(1) : '—';
  el.innerHTML = `
    <div class="ops-rag-item"><span class="ops-stat-value">${s.total_rag_queries}</span><span class="ops-stat-label">Queries</span></div>
    <div class="ops-rag-item"><span class="ops-stat-value">${score}</span><span class="ops-stat-label">Avg Score</span></div>
    <div class="ops-rag-item"><span class="ops-stat-value">${chunks}</span><span class="ops-stat-label">Avg Chunks</span></div>
    <div class="ops-rag-item">
      <span class="ops-stat-value">${Object.entries(s.extraction_statuses).map(([k,v]) => `${v}`).join(' / ')}</span>
      <span class="ops-stat-label">${Object.keys(s.extraction_statuses).map(k => k.replace(/.*\./, '')).join(' / ')}</span>
    </div>
  `;
}

function renderOpsLog(recent) {
  const tbody = document.getElementById('opsLogBody');
  if (!recent || recent.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#a08070;padding:20px">No activity yet — start chatting with Eve!</td></tr>';
    return;
  }
  tbody.innerHTML = recent.map(r => {
    const t = new Date(r.created_at);
    const timeStr = t.toLocaleString('en-US', { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' });
    const typeLabel = r.metric_type.replace('_', ' ');
    const tokens = r.total_tokens != null ? formatNumber(r.total_tokens) : '—';
    const latency = r.latency_ms != null ? `${formatNumber(r.latency_ms)}ms` : '—';
    const statusCls = r.status === 'success' ? 'success' : r.status === 'error' ? 'error' : 'pending';
    return `<tr>
      <td>${timeStr}</td>
      <td>${typeLabel}</td>
      <td>${r.intent || '—'}</td>
      <td>${tokens}</td>
      <td>${latency}</td>
      <td><span class="ops-status-badge ${statusCls}">${r.status || '—'}</span></td>
    </tr>`;
  }).join('');
}

document.getElementById('opsOverlay')?.addEventListener('click', (e) => {
  if (e.target.id === 'opsOverlay') closeAiOpsPanel();
});

async function triggerReindex() {
  const btn = document.getElementById('opsReindexBtn');
  const icon = btn.querySelector('.fa-sync-alt');
  btn.disabled = true;
  icon.classList.add('spinning');
  btn.innerHTML = '<i class="fas fa-sync-alt spinning"></i> Re-indexing…';

  try {
    const res = await fetch(`${API_BASE}/api/admin/reindex`, { method: 'POST' });
    const data = await res.json();
    if (data.status === 'already_running') {
      btn.innerHTML = '<i class="fas fa-sync-alt spinning"></i> In progress…';
    } else if (data.status === 'no_pdfs') {
      btn.innerHTML = '<i class="fas fa-sync-alt"></i> No PDFs';
      setTimeout(() => { btn.disabled = false; btn.innerHTML = '<i class="fas fa-sync-alt"></i> Re-index'; }, 3000);
      return;
    }
    pollReindexStatus();
  } catch (err) {
    console.error('Re-index trigger failed:', err);
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-sync-alt"></i> Re-index';
  }
}

async function pollReindexStatus() {
  const btn = document.getElementById('opsReindexBtn');
  const poll = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/admin/reindex/status`);
      const data = await res.json();
      if (data.running) {
        btn.innerHTML = `<i class="fas fa-sync-alt spinning"></i> ${data.done}/${data.total}`;
        setTimeout(poll, 1500);
      } else {
        const errCount = data.errors ? data.errors.length : 0;
        const label = errCount ? `Done (${errCount} errors)` : 'Done!';
        btn.innerHTML = `<i class="fas fa-check"></i> ${label}`;
        setTimeout(() => {
          btn.disabled = false;
          btn.innerHTML = '<i class="fas fa-sync-alt"></i> Re-index';
        }, 4000);
      }
    } catch {
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-sync-alt"></i> Re-index';
    }
  };
  setTimeout(poll, 1500);
}
