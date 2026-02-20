/**
 * Shared Utility Functions for Finder's Keeper Frontend
 * Centralizes common functionality to follow DRY principles
 */

/**
 * XSS Protection - Sanitize user input for safe HTML display
 * @param {string} text - Text to sanitize
 * @returns {string} Sanitized HTML-safe text
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Initialize AWS service and ensure it's ready
 * @returns {Promise<void>}
 */
async function initializeAWS() {
    if (!awsService.initialized) {
        await awsService.initialize();
    }
}

/**
 * Check authentication and redirect if not logged in
 * @param {string} redirectUrl - URL to redirect to (default: index.html)
 * @returns {boolean} True if authenticated, false otherwise
 */
async function requireAuth(redirectUrl = 'index.html') {
    await initializeAWS();
    
    if (!awsService.isAuthenticated()) {
        alert('Please log in to access this page');
        window.location.href = redirectUrl;
        return false;
    }
    return true;
}

/**
 * Format date for display
 * @param {string|Date} date - Date to format
 * @param {boolean} includeTime - Include time in output
 * @returns {string} Formatted date string
 */
function formatDate(date, includeTime = false) {
    const d = new Date(date);
    
    if (isNaN(d.getTime())) {
        return 'Invalid date';
    }
    
    const options = {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    };
    
    if (includeTime) {
        options.hour = '2-digit';
        options.minute = '2-digit';
    }
    
    return d.toLocaleDateString('en-US', options);
}

/**
 * Show loading state on a button
 * @param {HTMLButtonElement} button - Button element
 * @param {string} loadingText - Text to show while loading
 * @returns {Function} Restore function to call when done
 */
function setButtonLoading(button, loadingText = 'Loading...') {
    const originalText = button.textContent;
    const originalDisabled = button.disabled;
    
    button.disabled = true;
    button.textContent = loadingText;
    
    // Return restore function
    return () => {
        button.disabled = originalDisabled;
        button.textContent = originalText;
    };
}

/**
 * Handle form submission with loading state and error handling
 * @param {HTMLFormElement} form - Form element
 * @param {Function} handler - Async function to handle form data
 * @param {string} loadingText - Loading button text
 */
function setupFormHandler(form, handler, loadingText = 'Processing...') {
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const submitBtn = form.querySelector('button[type="submit"]');
        const restoreButton = setButtonLoading(submitBtn, loadingText);
        
        try {
            await handler(e);
        } catch (error) {
            console.error('Form submission error:', error);
            alert(error.message || 'An error occurred. Please try again.');
        } finally {
            restoreButton();
        }
    });
}

/**
 * Validate image file
 * @param {File} file - Image file to validate
 * @param {number} maxSizeMB - Maximum file size in MB (default: 5)
 * @returns {Object} { valid: boolean, error: string|null }
 */
function validateImageFile(file, maxSizeMB = 5) {
    const validTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    
    if (!validTypes.includes(file.type)) {
        return {
            valid: false,
            error: 'Please upload a valid image file (JPEG, PNG, GIF, or WebP)'
        };
    }
    
    const maxSize = maxSizeMB * 1024 * 1024;
    if (file.size > maxSize) {
        return {
            valid: false,
            error: `Image size must be less than ${maxSizeMB}MB`
        };
    }
    
    return { valid: true, error: null };
}

/**
 * Setup image preview functionality
 * @param {HTMLInputElement} input - File input element
 * @param {HTMLElement} preview - Preview element
 * @returns {Function} Get selected file function
 */
function setupImagePreview(input, preview) {
    let selectedFile = null;
    
    input.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        const validation = validateImageFile(file);
        if (!validation.valid) {
            alert(validation.error);
            input.value = '';
            return;
        }
        
        selectedFile = file;
        const reader = new FileReader();
        reader.onload = (event) => {
            preview.style.backgroundImage = `url('${event.target.result}')`;
            preview.innerHTML = ''; // Remove placeholder icon
        };
        reader.readAsDataURL(file);
    });
    
    // Return function to get selected file
    return () => selectedFile;
}

/**
 * Validate date is not in the future
 * @param {string} dateString - Date string to validate
 * @returns {Object} { valid: boolean, error: string|null }
 */
function validateDate(dateString) {
    if (!dateString) {
        return { valid: false, error: 'Please select a date' };
    }
    
    const selectedDate = new Date(dateString);
    const today = new Date();
    today.setHours(23, 59, 59, 999);
    
    if (selectedDate > today) {
        return { valid: false, error: 'Date cannot be in the future' };
    }
    
    return { valid: true, error: null };
}

/**
 * Validate text input
 * @param {string} text - Text to validate
 * @param {number} minLength - Minimum length
 * @param {string} fieldName - Name of field for error message
 * @returns {Object} { valid: boolean, error: string|null }
 */
function validateText(text, minLength = 3, fieldName = 'Field') {
    const trimmed = text.trim();
    
    if (!trimmed || trimmed.length < minLength) {
        return {
            valid: false,
            error: `${fieldName} must be at least ${minLength} characters`
        };
    }
    
    return { valid: true, error: null };
}

/**
 * Validate password
 * @param {string} password - Password to validate
 * @returns {Object} { valid: boolean, error: string|null }
 */
function validatePassword(password) {
    if (password.length < 8) {
        return {
            valid: false,
            error: 'Password must be at least 8 characters long'
        };
    }
    
    return { valid: true, error: null };
}

/**
 * Setup logout button functionality
 * @param {string} buttonId - ID of logout button
 */
function setupLogoutButton(buttonId = 'logoutBtn') {
    const logoutBtn = document.getElementById(buttonId);
    if (logoutBtn) {
        logoutBtn.onclick = () => {
            awsService.logout();
            alert('You have been logged out successfully');
            window.location.href = 'index.html';
        };
    }
}

/**
 * Get user's first initial for avatar
 * @param {string} name - User's name
 * @returns {string} First letter uppercased
 */
function getUserInitial(name) {
    if (!name) return '?';
    return name.charAt(0).toUpperCase();
}

/**
 * Debounce function for search inputs
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in ms
 * @returns {Function} Debounced function
 */
function debounce(func, wait = 300) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Setup real-time filter listeners
 * @param {Array<string>} inputIds - Array of input element IDs
 * @param {Function} filterFunction - Function to call on input change
 */
function setupFilterListeners(inputIds, filterFunction) {
    const debouncedFilter = debounce(filterFunction, 300);
    
    inputIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', debouncedFilter);
        }
    });
}

/**
 * Create item card HTML
 * @param {Object} item - Item object
 * @param {boolean} includeClick - Add click handler
 * @returns {HTMLElement} Card element
 */
function createItemCard(item, includeClick = true) {
    const card = document.createElement('div');
    card.className = 'card';
    
    if (includeClick) {
        card.onclick = () => window.location.href = `itemDetails.html?id=${item.id}`;
    }
    
    const sanitizedTitle = escapeHtml(item.title);
    const sanitizedLocation = escapeHtml(item.location);
    const sanitizedImg = escapeHtml(item.img);
    
    card.innerHTML = `
        <div class="card-preview" style="background-image: url('${sanitizedImg}')"></div>
        <div class="card-body">
            <div class="card-meta">
                <span class="badge ${item.status}">${item.status}</span>
                <span class="date">📅 ${item.date}</span>
            </div>
            <h3>${sanitizedTitle}</h3>
            <p class="location">📍 ${sanitizedLocation}</p>
        </div>
    `;
    
    return card;
}

/**
 * Show empty state message
 * @param {HTMLElement} container - Container element
 * @param {string} message - Message to display
 * @param {string} emoji - Emoji to show
 */
function showEmptyState(container, message = 'No items found', emoji = '😕') {
    container.innerHTML = `
        <div class="no-results">
            <h3>${emoji} ${message}</h3>
        </div>
    `;
}

/**
 * Get URL parameter value
 * @param {string} param - Parameter name
 * @returns {string|null} Parameter value or null
 */
function getUrlParam(param) {
    const params = new URLSearchParams(window.location.search);
    return params.get(param);
}

/**
 * Setup authentication UI visibility
 * @param {Object} options - { loginBtnId, userNavId, onAuthenticated, onUnauthenticated }
 */
function setupAuthUI(options = {}) {
    const {
        loginBtnId = 'loginBtn',
        userNavId = 'userNav',
        onAuthenticated = null,
        onUnauthenticated = null
    } = options;
    
    const loginBtn = document.getElementById(loginBtnId);
    const userNav = document.getElementById(userNavId);
    
    if (!loginBtn || !userNav) return;
    
    if (awsService.isAuthenticated()) {
        loginBtn.style.display = 'none';
        userNav.style.display = 'flex';
        
        if (onAuthenticated) {
            onAuthenticated(awsService.getCurrentUser());
        }
    } else {
        loginBtn.style.display = 'block';
        userNav.style.display = 'none';
        
        if (onUnauthenticated) {
            onUnauthenticated();
        }
    }
}

// Export as global for use in other scripts
window.utils = {
    escapeHtml,
    initializeAWS,
    requireAuth,
    formatDate,
    setButtonLoading,
    setupFormHandler,
    validateImageFile,
    setupImagePreview,
    validateDate,
    validateText,
    validatePassword,
    setupLogoutButton,
    getUserInitial,
    debounce,
    setupFilterListeners,
    createItemCard,
    showEmptyState,
    getUrlParam,
    setupAuthUI
};
