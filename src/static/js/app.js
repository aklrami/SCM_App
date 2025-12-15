console.log("app.js loaded");

document.addEventListener("DOMContentLoaded", () => {
  const toggleBtn = document.getElementById("mobile-menu-toggle");
  const overlay = document.getElementById("sidebar-overlay");

  const isMobile = () => window.matchMedia("(max-width: 768px)").matches;

  function openSidebar() {
    document.body.classList.add("sidebar-open");
    document.body.style.overflow = "hidden"; // lock scroll
  }

  function closeSidebar() {
    document.body.classList.remove("sidebar-open");
    document.body.style.overflow = ""; // restore scroll
  }

  function toggleSidebar() {
    document.body.classList.contains("sidebar-open")
      ? closeSidebar()
      : openSidebar();
  }

  // Toggle button
  if (toggleBtn) {
    toggleBtn.addEventListener("click", toggleSidebar);
  }

  // Overlay click closes
  if (overlay) {
    overlay.addEventListener("click", closeSidebar);
  }

  // Close when clicking a sidebar link (mobile only)
  document.querySelectorAll(".sidebar a").forEach((link) => {
    link.addEventListener("click", () => {
      if (isMobile()) closeSidebar();
    });
  });

  // ESC key closes
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeSidebar();
  });

  // Resize safety: never stuck
  window.addEventListener("resize", () => {
    if (!isMobile()) closeSidebar();
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
