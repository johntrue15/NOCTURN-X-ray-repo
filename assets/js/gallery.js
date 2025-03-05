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
  
  // Handle star ratings
  const starContainers = document.querySelectorAll('.stars');
  starContainers.forEach(container => {
    const stars = container.querySelectorAll('.star');
    
    // Set up star hover and click behavior
    stars.forEach((star, index) => {
      star.addEventListener('mouseover', () => {
        // Highlight stars up to current
        for (let i = 0; i <= index; i++) {
          stars[i].classList.add('hover');
        }
      });
      
      star.addEventListener('mouseout', () => {
        // Remove hover class
        stars.forEach(s => s.classList.remove('hover'));
      });
      
      star.addEventListener('click', () => {
        // Set active stars
        stars.forEach((s, i) => {
          if (i <= index) {
            s.classList.add('active');
          } else {
            s.classList.remove('active');
          }
        });
        
        // Store the selected rating
        container.setAttribute('data-rating', index + 1);
      });
    });
  });
  
  // Handle comment form submissions
  const commentForms = document.querySelectorAll('.comment-form');
  commentForms.forEach(form => {
    form.addEventListener('submit', async function(e) {
      e.preventDefault();
      
      const galleryItem = form.closest('.gallery-item');
      const releaseId = galleryItem.getAttribute('data-release-id');
      const releaseTag = galleryItem.getAttribute('data-release-tag');
      const commentText = form.querySelector('textarea').value.trim();
      const starsContainer = galleryItem.querySelector('.stars');
      const rating = starsContainer.getAttribute('data-rating') || 0;
      const statusMessage = galleryItem.querySelector('.status-message');
      
      if (!commentText) {
        showStatus(statusMessage, 'Please enter a comment', 'error');
        return;
      }
      
      if (!rating || rating === '0') {
        showStatus(statusMessage, 'Please select a rating', 'error');
        return;
      }
      
      showStatus(statusMessage, 'Saving your feedback...', 'pending');
      
      // Create the feedback data
      const feedback = {
        releaseId: releaseId,
        releaseTag: releaseTag,
        rating: parseInt(rating),
        comment: commentText,
        timestamp: new Date().toISOString()
      };
      
      try {
        // Store in localStorage (GitHub Pages is static, so we use client-side storage)
        saveToLocalStorage(feedback);
        
        // Try to send to GitHub API if a token is available
        const token = getGitHubToken();
        if (token) {
          try {
            await saveRatingToGitHub(feedback, token);
          } catch (apiError) {
            console.warn('Could not save to GitHub API:', apiError);
            // Continue with local storage only
          }
        }
        
        // Show success message
        showStatus(statusMessage, 'Thank you for your feedback!', 'success');
        
        // Reset form
        form.reset();
        galleryItem.querySelectorAll('.star').forEach(s => s.classList.remove('active'));
        starsContainer.setAttribute('data-rating', '0');
        
        // Add comment to the display
        addCommentToList(galleryItem, feedback);
        
        // If you want to implement server-side storage later, you can add the API call here
      } catch (error) {
        console.error('Error saving feedback:', error);
        showStatus(statusMessage, 'Error saving feedback. Please try again.', 'error');
      }
    });
  });
  
  // Load existing comments from localStorage on page load
  loadCommentsFromLocalStorage();
  
  // Also try to load comments from the server
  loadCommentsFromServer();
  
  // Utility function to show status messages
  function showStatus(element, message, type) {
    if (!element) return;
    
    element.textContent = message;
    element.className = 'status-message';
    
    if (type === 'success') {
      element.classList.add('status-success');
    } else if (type === 'error') {
      element.classList.add('status-error');
    }
    
    element.style.display = 'block';
    
    if (type === 'success' || type === 'error') {
      setTimeout(() => {
        element.style.display = 'none';
      }, 5000);
    }
  }
  
  // Store in localStorage
  function saveToLocalStorage(feedback) {
    const storageKey = 'ct-feedback-all';
    const existingFeedback = JSON.parse(localStorage.getItem(storageKey) || '[]');
    existingFeedback.push(feedback);
    localStorage.setItem(storageKey, JSON.stringify(existingFeedback));
    
    // Also store by release ID for faster retrieval
    const releaseKey = `ct-feedback-${feedback.releaseId}`;
    const existingReleaseFeedback = JSON.parse(localStorage.getItem(releaseKey) || '[]');
    existingReleaseFeedback.push(feedback);
    localStorage.setItem(releaseKey, JSON.stringify(existingReleaseFeedback));
  }
  
  // Function to save rating to GitHub repository using repository_dispatch
  async function saveRatingToGitHub(feedback, token) {
    const owner = 'johntrue15';
    const repo = 'NOCTURN-X-ray-repo';
    
    const response = await fetch(`https://api.github.com/repos/${owner}/${repo}/dispatches`, {
      method: 'POST',
      headers: {
        'Authorization': `token ${token}`,
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        event_type: 'save-rating',
        client_payload: feedback
      })
    });
    
    if (!response.ok) {
      throw new Error(`GitHub API error: ${response.status}`);
    }
    
    return true;
  }
  
  // Function to get GitHub token from URL parameter
  function getGitHubToken() {
    // For security, this is not a recommended approach for a real application
    // but can be used for demonstration purposes
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('token');
  }
  
  // Function to load comments from localStorage
  function loadCommentsFromLocalStorage() {
    const galleryItems = document.querySelectorAll('.gallery-item');
    galleryItems.forEach(item => {
      const releaseId = item.getAttribute('data-release-id');
      if (!releaseId) return;
      
      const storageKey = `ct-feedback-${releaseId}`;
      const storedFeedback = JSON.parse(localStorage.getItem(storageKey) || '[]');
      
      storedFeedback.forEach(feedback => {
        addCommentToList(item, feedback);
      });
    });
  }
  
  // Function to load comments from the server (ratings.json)
  async function loadCommentsFromServer() {
    try {
      const response = await fetch('/assets/data/ratings.json');
      if (!response.ok) {
        console.warn('Could not load ratings from server:', response.status);
        return;
      }
      
      const data = await response.json();
      if (!data || !data.ratings || !Array.isArray(data.ratings)) {
        console.warn('Invalid ratings data format');
        return;
      }
      
      // Process each rating
      const galleryItems = document.querySelectorAll('.gallery-item');
      galleryItems.forEach(item => {
        const releaseId = item.getAttribute('data-release-id');
        if (!releaseId) return;
        
        // Find ratings for this release
        const releaseRatings = data.ratings.filter(r => r.releaseId === releaseId);
        releaseRatings.forEach(feedback => {
          // Check if this comment is already displayed (from localStorage)
          const commentList = item.querySelector('.comment-list');
          const commentExists = Array.from(commentList.querySelectorAll('.comment')).some(comment => {
            const commentDate = comment.querySelector('.comment-date').textContent;
            const feedbackDate = new Date(feedback.timestamp).toLocaleString();
            return commentDate === feedbackDate && 
                   comment.querySelector('.comment-content').textContent === feedback.comment;
          });
          
          if (!commentExists) {
            addCommentToList(item, feedback);
          }
        });
      });
    } catch (error) {
      console.warn('Error loading ratings from server:', error);
    }
  }
  
  // Function to add a comment to the UI
  function addCommentToList(galleryItem, feedback) {
    const commentList = galleryItem.querySelector('.comment-list');
    if (!commentList) return;
    
    const commentElement = document.createElement('div');
    commentElement.className = 'comment';
    
    const starIcons = '★'.repeat(feedback.rating) + '☆'.repeat(5 - feedback.rating);
    
    commentElement.innerHTML = `
      <div class="comment-header">
        <span class="comment-date">${new Date(feedback.timestamp).toLocaleString()}</span>
        <span class="comment-rating">${starIcons}</span>
      </div>
      <div class="comment-content">${feedback.comment}</div>
    `;
    
    commentList.appendChild(commentElement);
  }
  
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
