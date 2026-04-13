# EventOps — Potential Local Improvements

Five actionable improvements for the EventOps platform, ordered by impact and feasibility.

---

## 1. Budget Tracker with Visual Spend Analysis

**What:** Add a real-time budget overview to the dashboard that computes total budget, amount spent, amount remaining, and per-category spend breakdowns — all derived from existing payment data. Display it as a progress bar and a per-vendor-category breakdown (venue: $X, decor: $Y, etc.). Include an optional "budget cap" field on the event model so users can set a target and see how close they are.

**Why it's useful:** Wedding planning is fundamentally a budgeting exercise. Right now EventOps tracks individual payments and vendors, but there's no aggregate "how am I doing financially?" view. Users have to mentally sum everything up. A budget tracker closes that gap and makes the financial summary cards on the dashboard far more meaningful.

**Why it's unique:** Most wedding planners show a flat spreadsheet of costs. A category-level breakdown with real-time progress against a user-set budget cap — populated automatically from chatbot-entered payments — is a differentiator that combines AI data entry with financial visibility.

---

## 2. Smart Notifications & Deadline Alerts Service

**What:** Create a backend service that, on each API request (or on a lightweight background check), computes upcoming deadlines — payments due within 7 days, overdue tasks, calendar events tomorrow — and returns them as a structured "alerts" payload alongside the dashboard response. The frontend renders these as dismissible notification banners or a notification bell dropdown.

**Why it's useful:** Users currently have to scan the dashboard, payments, and calendar separately to notice urgent items. Proactive alerts surface what needs attention without the user having to look for it.

**Why it's cool:** Alerts are computed from real data (not hardcoded). Overdue payments turn red, tomorrow's events get highlighted, tasks past their deadline get flagged. It turns EventOps from a passive tracker into an active assistant.

---

## 3. Event Timeline / Milestone Tracker

**What:** Add a timeline visualization that plots key milestones chronologically: booking dates, payment dates (past and future), calendar events, and the wedding date itself. Render it as a vertical or horizontal timeline on the dashboard, where each node is a completed or upcoming milestone with its date, label, and status (done / upcoming / overdue).

**Why it's useful:** Wedding planning spans months. A timeline gives users a bird's-eye view of their entire journey — what they've accomplished and what's ahead. It's the kind of view that makes users feel organized and in control.

**Why it's unique:** The data already exists across vendors, payments, tasks, and calendar events. Aggregating it into a single chronological timeline is something most wedding tools don't do automatically. Combining AI-entered data into a visual storyline is a strong UX differentiator.

---

## 4. Vendor Comparison & Scoring

**What:** When a user has multiple vendors in the same category (e.g., two photographer quotes), provide a comparison view that side-by-side shows pricing, payment terms, notes, and uploaded document summaries (via RAG). Add a simple scoring mechanism where users can rate vendors on criteria like price, availability, and reviews, and see a weighted total.

**Why it's useful:** Before booking, couples often compare 2-3 vendors per category. Right now they'd have to flip between vendor cards manually. A comparison view streamlines the decision-making process.

**Why it's cool:** Combined with RAG, the system could auto-extract key contract terms (cancellation policy, deposit amount, included services) and display them side-by-side — saving users from reading through multiple contracts.

---

## 5. Export & Share Event Summary

**What:** Add an API endpoint and UI button that generates a shareable event summary — either as a downloadable PDF or a copyable rich-text block. The summary includes: event details, vendor list with contact info, payment schedule (paid + pending), upcoming calendar events, and open tasks. Optionally include a QR code linking to a read-only share URL.

**Why it's useful:** Couples frequently need to share their planning status with family members, wedding planners, or co-planners. Currently there's no way to export the information. A one-click summary export is a huge convenience.

**Why it's cool:** The summary is generated from live data, not a static template. It reflects the real-time state of planning — vendors booked, payments made, tasks outstanding. It's like a "state of the wedding" report.

---

## Recommended First Pick: #1 — Budget Tracker with Visual Spend Analysis

This is the highest-impact, lowest-risk improvement because:
- All the data already exists (payments, vendors, categories)
- It's purely computational — no LLM calls, no new external dependencies
- It adds immediate visible value to the dashboard
- It's fully testable with the existing test infrastructure
- It complements the existing financial summary cards on the dashboard
