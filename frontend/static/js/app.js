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
  setupWelcomeCardHover();
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
    case 'tasks': loadTasksV2(); break;
    case 'calendar': loadCalendarV2(); break;
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
  
  container.innerHTML = payments.map((p, i) => {
    const displayName = p.vendor_name || p.description || 'Payment';
    const amount = parseFloat(p.amount_paid || p.amount || 0);
    return `
    <div class="item-row">
      <div class="item-icon ${COLORS[i % COLORS.length]}">
        <i class="fas fa-dollar-sign"></i>
      </div>
      <div class="item-content">
        <div class="item-title">${escapeHtml(displayName)}</div>
        <div class="item-subtitle">${p.paid_date ? formatShortDate(new Date(p.paid_date)) : 'Pending'} · $${formatNumber(amount)}</div>
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
  
  expandChat();
  resetChatCollapseTimer();
  
  addMessage(text, 'user');
  input.value = '';
  clearPlaceholder();
  
  addToConversationHistory('user', text);
  
  showTypingIndicator('Got it, let me process that...');
  
  setTimeout(() => {
    if (isAITyping) updateTypingStatus('Analyzing your request...');
  }, 3000);
  
  setTimeout(() => {
    if (isAITyping) updateTypingStatus('Processing details...');
  }, 6000);
  
  setTimeout(() => {
    if (isAITyping) updateTypingStatus('Almost there...');
  }, 10000);
  
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
    html += '<ul class="extraction-list">';
    for (const [key, value] of Object.entries(result.data)) {
      if (value !== null && value !== undefined && value !== '') {
        const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        html += `<li><strong>${label}:</strong> ${value}</li>`;
      }
    }
    html += '</ul>';
    
    if (result.follow_up_question) {
      html += `<div class="follow-up-question">${result.follow_up_question}</div>`;
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
  html += `<div style="margin-bottom: 8px;">Got it! Here's what I extracted:</div>`;
  html += '<ul class="extraction-list">';
  
  for (const [key, value] of Object.entries(result.data)) {
    if (value !== null && value !== undefined && value !== '') {
      const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
      html += `<li><strong>${label}:</strong> ${value}</li>`;
    }
  }
  
  html += '</ul>';
  
  html += `<div class="follow-up-question">${result.follow_up_question}</div>`;
  
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
  
  switch (action) {
    case 'add':
      actionDescription = `Add new sub-event "${data.new_name || 'New Sub-Event'}"`;
      break;
    case 'cancel':
      actionDescription = `Cancel sub-event "${data.sub_event_name}"`;
      break;
    case 'reschedule':
      actionDescription = `Reschedule "${data.sub_event_name}"`;
      break;
    case 'update':
      if (data.new_name) {
        actionDescription = `Change "${data.sub_event_name}" to "${data.new_name}"`;
      } else {
        actionDescription = `Update "${data.sub_event_name}"`;
      }
      break;
    default:
      actionDescription = `Update sub-event`;
  }
  
  let html = `<div style="margin-bottom: 8px;">${actionDescription}</div>`;
  html += '<ul class="extraction-list">';
  
  if (data.new_date) {
    html += `<li><strong>New Date:</strong> ${formatShortDate(new Date(data.new_date))}</li>`;
  }
  if (data.new_start_time) {
    html += `<li><strong>Start Time:</strong> ${formatTime(data.new_start_time)}</li>`;
  }
  if (data.new_end_time) {
    html += `<li><strong>End Time:</strong> ${formatTime(data.new_end_time)}</li>`;
  }
  if (data.new_location) {
    html += `<li><strong>Location:</strong> ${escapeHtml(data.new_location)}</li>`;
  }
  
  html += '</ul>';
  
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
  
  let html = `<div style="margin-bottom: 8px;">Update Event Details:</div>`;
  html += '<ul class="extraction-list">';
  
  for (const [key, value] of Object.entries(data)) {
    if (value != null && value !== '') {
      html += `<li><strong>${formatLabel(key)}:</strong> ${formatValue(key, value)}</li>`;
    }
  }
  
  html += '</ul>';
  
  html += `<div class="confirm-actions">
    <button class="btn btn-secondary btn-sm" onclick="cancelExtraction()">Cancel</button>
    <button class="btn btn-primary btn-sm" onclick="confirmExtraction()">Save Changes</button>
  </div>`;
  
  return html;
}

function renderStandardExtractionPreview(result) {
  let html = `<div style="margin-bottom: 8px;">Got it! Here's what I found:</div>`;
  html += '<ul class="extraction-list">';
  
  for (const [key, value] of Object.entries(result.data)) {
    if (value != null && value !== '') {
      html += `<li><strong>${formatLabel(key)}:</strong> ${formatValue(key, value)}</li>`;
    }
  }
  html += '</ul>';
  
  if (result.missing_fields?.length > 0) {
    html += `<div style="margin-top: 8px; font-size: 0.85rem; opacity: 0.8;">
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
  
  showTypingIndicator('Saving...');
  
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

// ============================================
// UI V2 FUNCTIONS
// ============================================

async function loadDashboardV2() {
  if (!currentEventId) return;
  
  try {
    const [dashResponse, tasksResponse, calendarResponse, paymentsResponse, vendorsResponse, eventResponse] = await Promise.all([
      fetch(`${API_BASE}/api/events/${currentEventId}/dashboard`),
      fetch(`${API_BASE}/api/events/${currentEventId}/tasks`),
      fetch(`${API_BASE}/api/events/${currentEventId}/calendar`),
      fetch(`${API_BASE}/api/events/${currentEventId}/payments`),
      fetch(`${API_BASE}/api/events/${currentEventId}/vendors`),
      fetch(`${API_BASE}/api/events/${currentEventId}`)
    ]);
    
    const dashboard = await dashResponse.json();
    const tasks = await tasksResponse.json();
    const calendar = await calendarResponse.json();
    const payments = await paymentsResponse.json();
    const vendors = await vendorsResponse.json();
    const event = await eventResponse.json();
    
    // Subtle Stats
    const subeventsCount = event.sub_events?.length || 0;
    const vendorsCount = vendors.length;
    const totalPaid = parseFloat(dashboard.financial_summary?.total_paid || 0);
    const totalPending = parseFloat(dashboard.financial_summary?.total_upcoming || 0);
    
    const statSubevents = document.getElementById('stat-subevents');
    const statVendors = document.getElementById('stat-vendors');
    const statPaid = document.getElementById('stat-paid');
    const statPending = document.getElementById('stat-pending');
    
    if (statSubevents) statSubevents.textContent = subeventsCount;
    if (statVendors) statVendors.textContent = vendorsCount;
    if (statPaid) statPaid.textContent = `$${formatNumber(totalPaid)}`;
    if (statPending) statPending.textContent = `$${formatNumber(totalPending)}`;
    
    // 3-Column Layout
    renderDashboardTasks(tasks);
    renderDashboardPayments(payments);
    renderDashboardSchedule(calendar, event.sub_events || []);
    
  } catch (error) {
    console.error('Failed to load dashboard V2:', error);
  }
}

function renderDashboardTasks(tasks) {
  const container = document.getElementById('dashboardTasks');
  if (!container) return;
  
  const pendingTasks = tasks.filter(t => t.status !== 'completed').slice(0, 8);
  
  if (pendingTasks.length === 0) {
    container.innerHTML = '<div class="task-item-simple"><span class="task-checkbox completed"></span><span class="task-text completed">All tasks complete!</span></div>';
    return;
  }
  
  container.innerHTML = pendingTasks.map(task => `
    <div class="task-item-simple">
      <span class="task-checkbox"></span>
      <div>
        <span class="task-text">${escapeHtml(task.title)}</span>
        ${task.due_date ? `<div class="task-due">Due ${formatShortDate(new Date(task.due_date))}</div>` : ''}
      </div>
    </div>
  `).join('');
}

function renderDashboardPayments(payments) {
  const container = document.getElementById('dashboardPayments');
  if (!container) return;
  
  const recentPayments = payments.slice(0, 8);
  
  if (recentPayments.length === 0) {
    container.innerHTML = '<div class="payment-item-simple"><span class="payment-vendor">No payments yet</span></div>';
    return;
  }
  
  container.innerHTML = recentPayments.map(p => {
    const displayName = p.vendor_name || p.description || 'Payment';
    const amount = parseFloat(p.amount_paid || p.amount || 0);
    return `
    <div class="payment-item-simple">
      <span class="payment-vendor">${escapeHtml(displayName)}</span>
      <span class="payment-amount">$${formatNumber(amount)}</span>
    </div>
  `;}).join('');
}

function renderDashboardSchedule(calendar, subEvents) {
  const container = document.getElementById('dashboardSchedule');
  if (!container) return;
  
  const items = [];
  
  // Add sub-events
  subEvents.forEach(se => {
    if (se.date) {
      items.push({
        name: se.name,
        date: new Date(se.date),
        type: 'subevent'
      });
    }
  });
  
  // Add calendar events
  calendar.forEach(c => {
    if (c.event_date) {
      items.push({
        name: c.title,
        date: new Date(c.event_date),
        type: 'calendar'
      });
    }
  });
  
  items.sort((a, b) => a.date - b.date);
  const upcoming = items.filter(i => i.date >= new Date()).slice(0, 6);
  
  if (upcoming.length === 0) {
    container.innerHTML = '<div class="schedule-item-simple"><span class="schedule-name">No upcoming events</span></div>';
    return;
  }
  
  container.innerHTML = upcoming.map(item => `
    <div class="schedule-item-simple">
      <span class="schedule-name">${escapeHtml(item.name)}</span>
      <span class="schedule-date">${formatShortDate(item.date)}</span>
    </div>
  `).join('');
}

async function loadPaymentsV2() {
  if (!currentEventId) return;
  
  try {
    const [paymentsResponse, vendorsResponse] = await Promise.all([
      fetch(`${API_BASE}/api/events/${currentEventId}/payments`),
      fetch(`${API_BASE}/api/events/${currentEventId}/vendors`)
    ]);
    
    const payments = await paymentsResponse.json();
    const vendors = await vendorsResponse.json();
    
    // Render vendors
    const vendorsContainer = document.getElementById('vendorsList');
    if (vendorsContainer) {
      if (vendors.length === 0) {
        vendorsContainer.innerHTML = '<div class="empty-state-v2"><p>No vendors yet</p></div>';
      } else {
        vendorsContainer.innerHTML = vendors.map((v, i) => `
          <div class="vendor-item-v2">
            <div class="vendor-avatar" style="background: ${['#A0C9CB', '#FF6037', '#733635', '#F5F4ED'][i % 4]}">
              ${v.name.charAt(0).toUpperCase()}
            </div>
            <div class="vendor-info">
              <div class="vendor-name">${escapeHtml(v.name)}</div>
              <div class="vendor-category">${escapeHtml(v.category || 'Vendor')}</div>
            </div>
          </div>
        `).join('');
      }
    }
    
    // Split payments into completed and pending
    const completedPayments = payments.filter(p => p.paid_date);
    const pendingPayments = payments.filter(p => !p.paid_date && p.due_date);
    
    // Render completed payments
    const paymentsContainer = document.getElementById('paymentsList');
    if (paymentsContainer) {
      if (completedPayments.length === 0) {
        paymentsContainer.innerHTML = '<div class="empty-state-v2"><p>No payments recorded</p></div>';
      } else {
        paymentsContainer.innerHTML = completedPayments.map(p => {
          const displayName = p.vendor_name || p.description || 'Payment';
          const amount = parseFloat(p.amount_paid || p.amount || 0);
          return `
          <div class="payment-item-v2">
            <div class="payment-details">
              <div class="payment-vendor-name">${escapeHtml(displayName)}</div>
              <div class="payment-date">${p.paid_date ? formatShortDate(new Date(p.paid_date)) : ''}</div>
            </div>
            <div class="payment-amount-v2">$${formatNumber(amount)}</div>
          </div>
        `;}).join('');
      }
    }
    
    // Render pending payments
    const pendingContainer = document.getElementById('pendingPaymentsList');
    if (pendingContainer) {
      if (pendingPayments.length === 0) {
        pendingContainer.innerHTML = '<div class="empty-state-v2"><p>No pending payments</p></div>';
      } else {
        pendingContainer.innerHTML = pendingPayments.map(p => {
          const displayName = p.vendor_name || p.description || 'Payment due';
          const amount = parseFloat(p.amount || 0);
          return `
          <div class="payment-item-v2">
            <div class="payment-details">
              <div class="payment-vendor-name">${escapeHtml(displayName)}</div>
              <div class="payment-date">Due ${formatShortDate(new Date(p.due_date))}</div>
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

async function loadTasksV2() {
  if (!currentEventId) return;
  
  try {
    const response = await fetch(`${API_BASE}/api/events/${currentEventId}/tasks`);
    const tasks = await response.json();
    
    const container = document.getElementById('allTasksList');
    if (!container) return;
    
    if (tasks.length === 0) {
      container.innerHTML = '<div class="empty-state-v2"><p>No tasks yet</p></div>';
      return;
    }
    
    // Sort: pending first, then by priority
    const priorityOrder = { high: 0, medium: 1, low: 2 };
    const sortedTasks = [...tasks].sort((a, b) => {
      if (a.status === 'completed' && b.status !== 'completed') return 1;
      if (a.status !== 'completed' && b.status === 'completed') return -1;
      return (priorityOrder[a.priority] || 2) - (priorityOrder[b.priority] || 2);
    });
    
    container.innerHTML = sortedTasks.map(task => `
      <div class="task-item-full">
        <span class="task-checkbox ${task.status === 'completed' ? 'completed' : ''}"></span>
        <div class="task-content">
          <div class="task-title ${task.status === 'completed' ? 'completed' : ''}">${escapeHtml(task.title)}</div>
          <div class="task-meta">
            ${task.priority ? `<span class="task-priority ${task.priority}">${task.priority}</span>` : ''}
            ${task.due_date ? `<span>Due ${formatShortDate(new Date(task.due_date))}</span>` : ''}
          </div>
        </div>
      </div>
    `).join('');
    
  } catch (error) {
    console.error('Failed to load tasks V2:', error);
  }
}

async function loadCalendarV2() {
  if (!currentEventId) return;
  
  try {
    const [eventResponse, calendarResponse] = await Promise.all([
      fetch(`${API_BASE}/api/events/${currentEventId}`),
      fetch(`${API_BASE}/api/events/${currentEventId}/calendar`)
    ]);
    
    const event = await eventResponse.json();
    const calendar = await calendarResponse.json();
    
    // Update event details card
    const nameEl = document.getElementById('eventDetailsName');
    const dateEl = document.getElementById('eventDetailsDate');
    const locationEl = document.getElementById('eventDetailsLocation');
    
    if (nameEl) nameEl.textContent = event.name;
    if (dateEl) dateEl.innerHTML = `<i class="fas fa-calendar"></i> ${formatDateRange(event.start_date, event.end_date)}`;
    if (locationEl) locationEl.innerHTML = `<i class="fas fa-map-marker-alt"></i> ${escapeHtml(event.location || 'Location TBD')}`;
    
    // Render sub-events
    const subEventsContainer = document.getElementById('calendarSubEventsList');
    if (subEventsContainer) {
      const subEvents = event.sub_events || [];
      if (subEvents.length === 0) {
        subEventsContainer.innerHTML = '<div class="empty-state-v2"><p>No sub-events yet</p></div>';
      } else {
        subEventsContainer.innerHTML = subEvents.map(se => `
          <div class="subevent-item-v2">
            <div class="subevent-name">${escapeHtml(se.name)}</div>
            <div class="subevent-meta">
              ${se.date ? `<span><i class="fas fa-calendar"></i> ${formatShortDate(new Date(se.date))}</span>` : ''}
              ${se.start_time ? `<span><i class="fas fa-clock"></i> ${se.start_time}</span>` : ''}
              ${se.location ? `<span><i class="fas fa-map-marker-alt"></i> ${escapeHtml(se.location)}</span>` : ''}
            </div>
          </div>
        `).join('');
      }
    }
    
    // Render calendar events
    const calendarContainer = document.getElementById('calendarList');
    if (calendarContainer) {
      if (calendar.length === 0) {
        calendarContainer.innerHTML = '<div class="empty-state-v2"><p>No calendar events yet</p></div>';
      } else {
        // Sort by date
        const sortedCalendar = [...calendar].sort((a, b) => new Date(a.event_date) - new Date(b.event_date));
        
        calendarContainer.innerHTML = sortedCalendar.map(c => {
          const date = new Date(c.event_date);
          const day = date.getDate();
          const month = date.toLocaleDateString('en-US', { month: 'short' });
          
          return `
            <div class="calendar-item-v2">
              <div class="calendar-date-badge">
                <span class="calendar-date-day">${day}</span>
                <span class="calendar-date-month">${month}</span>
              </div>
              <div class="calendar-event-info">
                <div class="calendar-event-title">${escapeHtml(c.title)}</div>
                <div class="calendar-event-time">${c.event_time || ''} ${c.location ? '· ' + escapeHtml(c.location) : ''}</div>
              </div>
            </div>
          `;
        }).join('');
      }
    }
    
  } catch (error) {
    console.error('Failed to load calendar V2:', error);
  }
}
