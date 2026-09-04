/* Offline capture + sync for low-connectivity field use.
   Loaded as a plain script on every page; exposes window.AnimalHealthOffline.
   Native Room/SQLite clients POST the same timestamped batch payload. */
(function () {
  'use strict';
  var QUEUE_KEY = 'mah-animal-health-offline-queue';

  function readQueue() {
    try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]'); } catch (e) { return []; }
  }
  function writeQueue(q) { localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); }

  function queueReport(report) {
    var q = readQueue();
    q.push(Object.assign({}, report, { updated_at: Date.now() }));
    writeQueue(q);
    return q.length;
  }

  function pendingCount() { return readQueue().length; }

  async function syncReports() {
    var reports = readQueue();
    if (!reports.length || !navigator.onLine) return { synced: 0, pending: reports.length };
    try {
      var r = await fetch('/api/v1/reports/mobile/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reports: reports })
      });
      if (r.ok) { localStorage.removeItem(QUEUE_KEY); return { synced: reports.length, pending: 0 }; }
    } catch (e) { /* stay queued until next reconnect */ }
    return { synced: 0, pending: reports.length };
  }

  // Register the service worker (root scope; app.py serves it from '/service-worker.js').
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/service-worker.js').catch(function () {});
    });
  }

  // Flush the queue whenever connectivity returns, and once on load if already online.
  window.addEventListener('online', syncReports);
  window.addEventListener('load', function () { if (navigator.onLine) syncReports(); });

  window.AnimalHealthOffline = {
    queueReport: queueReport,
    syncReports: syncReports,
    pendingCount: pendingCount
  };
})();
