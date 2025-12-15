console.log("app.js loaded");

document.addEventListener("DOMContentLoaded", function () {
  const toggleBtn = document.getElementById("mobile-menu-toggle");
  const overlay = document.getElementById("sidebar-overlay");

  function closeSidebar() {
    document.body.classList.remove("sidebar-open");
  }
  function toggleSidebar() {
    document.body.classList.toggle("sidebar-open");
  }

  // Sidebar toggle + overlay
  if (toggleBtn) toggleBtn.addEventListener("click", toggleSidebar);
  if (overlay) overlay.addEventListener("click", closeSidebar);

  // Close sidebar when clicking a menu link (mobile)
  document.querySelectorAll(".sidebar a").forEach((a) => {
    a.addEventListener("click", closeSidebar);
  });

  // ESC closes sidebar
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeSidebar();
  });

  // Ctrl+K focuses global search
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      const input = document.querySelector(".erp-search input");
      if (input) input.focus();
    }
  });

  // Auto-show Bootstrap toasts (flash messages)
  if (window.bootstrap) {
    document.querySelectorAll(".toast.erp-toast").forEach((t) => {
      try {
        new bootstrap.Toast(t).show();
      } catch (_) {}
    });
  }
});
