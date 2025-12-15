console.log("app.js loaded");

document.addEventListener("DOMContentLoaded", () => {
  const toggleBtn = document.getElementById("mobile-menu-toggle");
  const overlay = document.getElementById("sidebar-overlay");
  const sidebar = document.querySelector(".sidebar");

  const isMobile = () => window.matchMedia("(max-width: 768px)").matches;

  function setExpanded(isOpen) {
    if (toggleBtn) toggleBtn.setAttribute("aria-expanded", isOpen ? "true" : "false");
  }

  function openSidebar() {
    document.body.classList.add("sidebar-open");
    if (isMobile()) document.body.style.overflow = "hidden"; // lock scroll only on mobile
    setExpanded(true);
  }

  function closeSidebar() {
    document.body.classList.remove("sidebar-open");
    document.body.style.overflow = ""; // restore scroll
    setExpanded(false);
  }

  function toggleSidebar(e) {
    if (e) e.preventDefault();
    if (document.body.classList.contains("sidebar-open")) closeSidebar();
    else openSidebar();
  }

  // Toggle button
  if (toggleBtn) {
    toggleBtn.addEventListener("click", toggleSidebar, { passive: false });
  }

  // Overlay click closes
  if (overlay) {
    overlay.addEventListener("click", closeSidebar);
    overlay.addEventListener("touchstart", closeSidebar, { passive: true });
  }

  // Close when clicking a sidebar link (mobile only)
  document.querySelectorAll(".sidebar a").forEach((link) => {
    link.addEventListener("click", () => {
      if (isMobile()) closeSidebar();
    });
  });

  // ESC closes sidebar
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeSidebar();
  });

  // Safety: if user resizes to desktop, don’t leave mobile-open state
  window.addEventListener("resize", () => {
    if (!isMobile()) closeSidebar();
  });

  // Optional: click outside sidebar closes (fallback if overlay gets blocked)
  document.addEventListener("click", (e) => {
    if (!isMobile()) return;
    if (!document.body.classList.contains("sidebar-open")) return;
    if (!sidebar) return;

    const clickedToggle = e.target.closest("#mobile-menu-toggle");
    const clickedInsideSidebar = sidebar.contains(e.target);
    const clickedOverlay = e.target.closest("#sidebar-overlay");

    if (clickedOverlay) return;

    if (!clickedInsideSidebar && !clickedToggle) {
      closeSidebar();
    }
  });

  // Ctrl+K focuses the global search (like real dashboards)
  document.addEventListener("keydown", (e) => {
    const isCmdK = (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k";
    if (!isCmdK) return;

    const search = document.querySelector(".erp-search input");
    if (search) {
      e.preventDefault();
      search.focus();
      if (typeof search.select === "function") search.select();
    }
  });

  // Bootstrap toasts
  if (window.bootstrap) {
    document.querySelectorAll(".toast.erp-toast").forEach((t) => {
      try {
        new bootstrap.Toast(t).show();
      } catch (_) {}
    });
  }
});
