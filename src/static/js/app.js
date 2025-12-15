console.log("app.js loaded");

document.addEventListener("DOMContentLoaded", function () {
  const toggleBtn = document.getElementById("mobile-menu-toggle");
  const overlay = document.getElementById("sidebar-overlay");

  function openSidebar() {
    document.body.classList.add("sidebar-open");
  }
  function closeSidebar() {
    document.body.classList.remove("sidebar-open");
  }
  function toggleSidebar() {
    document.body.classList.toggle("sidebar-open");
  }

  if (toggleBtn) toggleBtn.addEventListener("click", toggleSidebar);
  if (overlay) overlay.addEventListener("click", closeSidebar);

  document.querySelectorAll(".sidebar a").forEach((a) => {
    a.addEventListener("click", closeSidebar);
  });
});
