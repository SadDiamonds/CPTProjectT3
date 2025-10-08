// Initialize Swup for smooth transitions
document.addEventListener("DOMContentLoaded", function () {
  const swup = new Swup({
    containers: ["#swup"],
    animationSelector: '[class*="transition-"]',
    linkSelector: 'a[href^="/"]:not([data-no-swup])' // only internal links
  });
});
