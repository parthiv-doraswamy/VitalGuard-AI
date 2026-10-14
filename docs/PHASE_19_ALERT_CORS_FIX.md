# Phase 19 — Alert inbox request headers

The alert inbox previously attached `Content-Type: application/json` to every request, including GET requests with no body. That can cause unnecessary browser CORS preflight requests. The client now sets Content-Type only when sending a request body, and a frontend test guards this behavior.

The backend still needs to allow the deployed frontend origin for actual JSON POST requests. This change reduces unnecessary preflights; it does not replace the server's CORS configuration.
