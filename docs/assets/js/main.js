document.addEventListener('DOMContentLoaded', function() {
  // Add any interactive features here
  console.log('GitHub Pages for NOCTURN X-ray loaded');
  
  // Add click event to expandable sections if needed
  const expandButtons = document.querySelectorAll('.expand-button');
  expandButtons.forEach(button => {
    button.addEventListener('click', function() {
      const content = this.nextElementSibling;
      content.style.display = content.style.display === 'none' ? 'block' : 'none';
      this.textContent = content.style.display === 'none' ? 'Show Details' : 'Hide Details';
    });
  });
});
