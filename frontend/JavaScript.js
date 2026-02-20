/**
 * Main Index Page Controller
 * Manages the lost and found items feed with filtering, sorting, and authentication
 */

let items = [];
let activeStatus = 'all';
let sortOrder = 'newest';

/**
 * Renders filtered and sorted items to the feed
 * Applies all active filters (search, category, location, date, status)
 */
function renderItems() {
    const feed = document.getElementById('feed');
    if (!feed) return;

    const mainSearch = document.getElementById('searchInput').value.toLowerCase();
    const advancedSearch = document.getElementById('advancedSearch').value.toLowerCase();
    const category = document.getElementById('categoryFilter').value;
    const date = document.getElementById('dateFilter').value;
    const location = document.getElementById('locationFilter').value;

    feed.innerHTML = '';

    let filtered = items.filter(it => {
        if (it.resolved === true) return false;
        
        const matchesStatus = activeStatus === 'all' || it.status === activeStatus;
        const matchesCategory = category === 'all' || it.category === category;
        const matchesLocation = location === 'all' || it.location === location;
        const matchesDate = !date || it.date === date;

        const matchesMainSearch = !mainSearch ||
            it.title.toLowerCase().includes(mainSearch) ||
            it.location.toLowerCase().includes(mainSearch) ||
            it.description.toLowerCase().includes(mainSearch);

        const matchesAdvancedSearch = !advancedSearch ||
            it.title.toLowerCase().includes(advancedSearch) ||
            it.description.toLowerCase().includes(advancedSearch) ||
            (it.color && it.color.toLowerCase().includes(advancedSearch));

        return matchesStatus && matchesCategory && matchesLocation && matchesDate && matchesMainSearch && matchesAdvancedSearch;
    });

    filtered.sort((a, b) => {
        const dateA = new Date(a.date);
        const dateB = new Date(b.date);
        return sortOrder === 'newest' ? dateB - dateA : dateA - dateB;
    });

    if (filtered.length === 0) {
        utils.showEmptyState(feed, 'No matches found');
    } else {
        filtered.forEach(it => {
            const card = utils.createItemCard(it);
            feed.appendChild(card);
        });
    }

    const statsDiv = document.getElementById('stats');
    if (statsDiv) statsDiv.innerText = `${filtered.length} items found`;
}

/**
 * Populates location filter dropdown with unique locations from all items
 */
function populateLocations() {
    const locSelect = document.getElementById('locationFilter');
    const locations = [...new Set(items.map(item => item.location))];
    locations.forEach(loc => {
        locSelect.innerHTML += `<option value="${utils.escapeHtml(loc)}">${utils.escapeHtml(loc)}</option>`;
    });
}

/**
 * Updates UI elements based on user authentication state
 * Configures hero button behavior for authenticated vs unauthenticated users
 */
function updateAuthUI() {
    utils.setupAuthUI({
        onAuthenticated: () => {
            const heroPostBtn = document.getElementById('heroPostBtn');
            if (heroPostBtn) {
                heroPostBtn.onclick = () => window.location.href = 'postItem.html';
            }
        },
        onUnauthenticated: () => {
            const heroPostBtn = document.getElementById('heroPostBtn');
            if (heroPostBtn) {
                heroPostBtn.onclick = () => {
                    alert('Please log in to post an item');
                    const loginModal = document.getElementById('loginModal');
                    if (loginModal) loginModal.classList.remove('hidden');
                };
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    await utils.initializeAWS();
    
    if (awsService.isAdmin()) {
        window.location.href = 'adminPage.html';
        return;
    }
    
    items = await awsService.getItems(25);
    updateAuthUI();
    populateLocations();

    utils.setupFilterListeners(
        ['searchInput', 'advancedSearch', 'categoryFilter', 'dateFilter', 'locationFilter'],
        renderItems
    );

    const sortSelect = document.getElementById('sortSelect');
    if (sortSelect) {
        sortSelect.addEventListener('change', (e) => {
            sortOrder = e.target.value;
            renderItems();
        });
    }

    document.querySelectorAll('.filter').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.filter').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            activeStatus = e.target.dataset.filter;
            renderItems();
        });
    });

    document.getElementById('clearFilters').addEventListener('click', () => {
        document.getElementById('advancedSearch').value = '';
        document.getElementById('categoryFilter').value = 'all';
        document.getElementById('dateFilter').value = '';
        document.getElementById('locationFilter').value = 'all';
        document.getElementById('searchInput').value = '';
        activeStatus = 'all';
        renderItems();
    });

    const loginModal = document.getElementById('loginModal');
    const loginBtn = document.getElementById('loginBtn');
    const closeLogin = document.getElementById('closeLogin');
    const signInArea = document.getElementById('signInArea');
    const signUpArea = document.getElementById('signUpArea');

    if (loginBtn) loginBtn.onclick = () => loginModal.classList.remove('hidden');
    if (closeLogin) closeLogin.onclick = () => loginModal.classList.add('hidden');
    document.getElementById('toRegister').onclick = () => {
        signInArea.style.display = 'none';
        signUpArea.style.display = 'block';
        document.getElementById('verifyArea').style.display = 'none';
    };
    document.getElementById('toSignIn').onclick = () => {
        signUpArea.style.display = 'none';
        signInArea.style.display = 'block';
        document.getElementById('verifyArea').style.display = 'none';
    };
    document.getElementById('backToSignIn').onclick = () => {
        document.getElementById('verifyArea').style.display = 'none';
        signInArea.style.display = 'block';
    };

    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        utils.setupFormHandler(loginForm, async (e) => {
            const email = e.target.querySelector('input[type="email"]').value;
            const password = e.target.querySelector('input[type="password"]').value;
            
            const result = await awsService.login(email, password);
            
            if (result.success) {
                if (awsService.isAdmin()) {
                    alert(`Welcome back, Admin ${result.name}!`);
                    window.location.href = 'adminPage.html';
                    return;
                }
                
                alert(`Welcome back, ${result.name}!`);
                loginModal.classList.add('hidden');
                updateAuthUI();
                
                items = await awsService.getItems(25);
                renderItems();
            }
        }, 'Signing in...');
    }

    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        utils.setupFormHandler(registerForm, async (e) => {
            const fullName = document.getElementById('regFullName').value;
            const email = document.getElementById('regEmail').value;
            const password = document.getElementById('regPassword').value;
            
            const validation = utils.validatePassword(password);
            if (!validation.valid) {
                alert(validation.error);
                throw new Error(validation.error);
            }
            
            const result = await awsService.register(email, password, fullName);
            
            if (result.success) {
                signUpArea.style.display = 'none';
                document.getElementById('verifyArea').style.display = 'block';
                document.getElementById('verifyEmail').textContent = email;
                
                window.pendingVerificationEmail = email;
                
                alert('Registration successful! Please check your email for a verification code.');
            }
        }, 'Registering...');
    }

    const verifyForm = document.getElementById('verifyForm');
    if (verifyForm) {
        utils.setupFormHandler(verifyForm, async (e) => {
            const code = document.getElementById('verificationCode').value;
            
            if (!window.pendingVerificationEmail) {
                alert('No pending verification. Please register first.');
                throw new Error('No pending verification');
            }
            
            await awsService.confirmRegistration(window.pendingVerificationEmail, code);
            
            alert('Email verified successfully! You can now sign in.');
            
            delete window.pendingVerificationEmail;
            
            document.getElementById('verifyArea').style.display = 'none';
            signInArea.style.display = 'block';
            
            verifyForm.reset();
        }, 'Verifying...');
    }

    const resendCodeBtn = document.getElementById('resendCode');
    if (resendCodeBtn) {
        resendCodeBtn.onclick = async () => {
            if (!window.pendingVerificationEmail) {
                alert('No pending verification. Please register first.');
                return;
            }
            
            try {
                await awsService.resendConfirmationCode(window.pendingVerificationEmail);
                alert('Verification code sent! Please check your email.');
            } catch (error) {
                alert('Failed to resend code: ' + error.message);
            }
        };
    }

    utils.setupLogoutButton();
    renderItems();
});