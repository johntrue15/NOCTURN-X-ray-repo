function saveRatingToGitHub(releaseId, releaseTag, rating, comment) {
    showStatusMessage("Saving your feedback...");
    
    // Use the token from the environment variable that will be injected during build
    const token = "{{COMMENT_API_TOKEN}}";
    
    // If no token, save to localStorage only
    if (!token || token === "{{COMMENT_API_TOKEN}}") {
        showStatusMessage("Saving locally only (no API token available)");
        return saveToLocalStorage(releaseId, releaseTag, rating, comment);
    }
    
    // ... existing code ...
} 