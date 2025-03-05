document.addEventListener('DOMContentLoaded', function() {
  // Add image click handler for lightbox effect
  const images = document.querySelectorAll('.image-item img');
  
  images.forEach(img => {
    img.addEventListener('click', function() {
      // Create lightbox
      const lightbox = document.createElement('div');
      lightbox.className = 'lightbox';
      lightbox.style.position = 'fixed';
      lightbox.style.top = '0';
      lightbox.style.left = '0';
      lightbox.style.width = '100%';
      lightbox.style.height = '100%';
      lightbox.style.backgroundColor = 'rgba(0,0,0,0.9)';
      lightbox.style.display = 'flex';
      lightbox.style.alignItems = 'center';
      lightbox.style.justifyContent = 'center';
      lightbox.style.zIndex = '1000';
      
      // Create image element
      const fullImg = document.createElement('img');
      fullImg.src = this.src;
      fullImg.style.maxHeight = '90%';
      fullImg.style.maxWidth = '90%';
      fullImg.style.objectFit = 'contain';
      
      // Add close on click
      lightbox.addEventListener('click', function() {
        document.body.removeChild(lightbox);
      });
      
      // Append to lightbox and body
      lightbox.appendChild(fullImg);
      document.body.appendChild(lightbox);
    });
  });
  
  // Lazy loading for images
  if ('IntersectionObserver' in window) {
    const lazyImages = document.querySelectorAll('img[loading="lazy"]');
    const imageObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target;
          img.src = img.dataset.src || img.src;
          imageObserver.unobserve(img);
        }
      });
    });
    
    lazyImages.forEach(img => {
      imageObserver.observe(img);
    });
  }
});
