# Phase 12 — Alert audit timeline UI

The backend alert inbox now has an expandable audit timeline per alert. It loads `GET /api/v1/alerts/{id}/audit` on demand and displays the event action, actor label, and timestamp. Loaded timelines are cached in the current page state.

The current actor value is a demo label, not authenticated identity. Audit records are useful for demonstrating the workflow but do not constitute a regulated or tamper-resistant audit system.
