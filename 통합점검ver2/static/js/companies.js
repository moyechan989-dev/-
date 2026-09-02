document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".company-link").forEach((link) => {
    link.addEventListener("click", () => {
      link.dataset.detailReady = "true";
    });
  });
});
