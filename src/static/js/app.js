
console.log("app.js loaded");

document.addEventListener("DOMContentLoaded", function () {
    const toggleBtn = document.getElementById("mobile-menu-toggle");
    const overlay = document.getElementById("sidebar-overlay");

    function toggleSidebar() {
        document.body.classList.toggle("sidebar-open");
    }

    if (toggleBtn) {
        toggleBtn.addEventListener("click", toggleSidebar);
    }

    if (overlay) {
        overlay.addEventListener("click", toggleSidebar);
    }
});
