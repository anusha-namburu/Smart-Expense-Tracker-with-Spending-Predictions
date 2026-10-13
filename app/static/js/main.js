// Smart Expense Tracker - Core Interactive Utilities
document.addEventListener('DOMContentLoaded', () => {
  // 1. Sidebar Toggle
  const sidebar = document.getElementById('appSidebar');
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebarBackdrop = document.getElementById('sidebarBackdrop');

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', () => {
      sidebar.classList.toggle('show');
      if (sidebarBackdrop) {
        sidebarBackdrop.classList.toggle('show');
      }
    });
  }

  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener('click', () => {
      sidebar.classList.remove('show');
      sidebarBackdrop.classList.remove('show');
    });
  }

  // 2. Auto-dismiss Flash Alerts
  const autoAlerts = document.querySelectorAll('.alert-dismissible');
  autoAlerts.forEach((alert) => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) {
        bsAlert.close();
      }
    }, 6000);
  });

  // 3. Category Color Preview
  const colorInput = document.getElementById('colorInput');
  const colorPreview = document.getElementById('colorPreview');
  if (colorInput && colorPreview) {
    colorInput.addEventListener('input', (e) => {
      colorPreview.style.backgroundColor = e.target.value;
    });
  }
});
