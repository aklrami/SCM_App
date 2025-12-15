console.log("app.js loaded");

document.addEventListener("DOMContentLoaded", function () {
  const toggleBtn = document.getElementById("mobile-menu-toggle");
  const overlay = document.getElementById("sidebar-overlay");

  const isMobile = () => window.matchMedia("(max-width: 768px)").matches;

  function closeSidebar() {
    document.body.classList.remove("sidebar-open");
    // restore scroll
    document.body.style.overflow = "";
  }

  function openSidebar() {
    document.body.classList.add("sidebar-open");
    // lock background scroll on mobile
    if (isMobile()) document.body.style.overflow = "hidden";
  }

  function toggleSidebar() {
    if (document.body.classList.contains("sidebar-open")) closeSidebar();
    else openSidebar();
  }

  // Sidebar toggle + overlay
  if (toggleBtn) toggleBtn.addEventListener("click", toggleSidebar);
  if (overlay) overlay.addEventListener("click", closeSidebar);

  // Close sidebar when clicking a menu link (mobile only)
  document.querySelectorAll(".sidebar a").forEach((a) => {
    a.addEventListener("click", () => {
      if (isMobile()) closeSidebar();
    });
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

  // If user resizes to desktop, ensure sidebar overlay state is cleared
  window.addEventListener("resize", () => {
    if (!isMobile()) closeSidebar();
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
