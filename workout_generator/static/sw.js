// Deliberately does no caching: every page here is behind the passcode
// gate and reflects live workout history, so serving a cached copy could
// show stale data or -- on a shared device -- another session's page after
// logout. This exists purely so Chrome's installability check (which wants
// a registered service worker with a fetch handler) is satisfied, letting
// "Add to Home Screen" install a standalone app rather than opening a tab.
self.addEventListener("fetch", (event) => {
  event.respondWith(fetch(event.request));
});
