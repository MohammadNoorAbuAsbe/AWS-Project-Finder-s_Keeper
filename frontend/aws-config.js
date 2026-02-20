const AWS_CONFIG = {
    region: 'us-east-1',
    
    API_GW_BASE_URL_STR:'https://ueyu3r0khi.execute-api.us-east-1.amazonaws.com/prod',
    
    COGNITO_LOGIN_BASE_URL_STR:'https://us-east-1_kfNTDWsQD.auth.us-east-1.amazoncognito.com',
    
    cognito: {
        userPoolId:'us-east-1_kfNTDWsQD',
        clientId:'12qbjhkba4p5jqk3ongepmjkvo',
        identityPoolId: null  // Set to null for AWS Academy (no IAM role creation allowed)
    },
    
    s3: {
        bucketName:'finders-keeper-images-2026',
        region: 'us-east-1'
    },
    
    api: {
        endpoint:'https://ueyu3r0khi.execute-api.us-east-1.amazonaws.com/prod',
        endpoints: {
            items: '/items',
            item: '/items/{id}',
            contact: '/contact',
            messages: '/messages'
        }
    }
};

/**
 * AWS Service Class - Serverless Backend Integration
 * Handles all AWS service interactions without localStorage fallbacks
 */
class AWSService {
    constructor() {
        this.initialized = false;
        this.currentUser = null;
        this.userToken = null;
        this.userAttributes = null;
    }

    /**
     * Initialize AWS SDK and Cognito
     * Must be called before any other operations
     */
    async initialize() {
        if (this.initialized) return;

        try {
            // Validate configuration
            if (!AWS || !AmazonCognitoIdentity) {
                throw new Error('AWS SDK or Cognito SDK not loaded. Include required scripts in HTML.');
            }

            // Configure AWS SDK region
            AWS.config.region = AWS_CONFIG.region;
            
            // Initialize Cognito User Pool
            this.userPool = new AmazonCognitoIdentity.CognitoUserPool({
                UserPoolId: AWS_CONFIG.cognito.userPoolId,
                ClientId: AWS_CONFIG.cognito.clientId
            });
            
            // Check for existing authenticated session
            await this.checkExistingSession();
            
            // Configure AWS credentials via Cognito Identity Pool (if available)
            if (AWS_CONFIG.cognito.identityPoolId) {
                if (this.userToken) {
                    // Authenticated user credentials
                    AWS.config.credentials = new AWS.CognitoIdentityCredentials({
                        IdentityPoolId: AWS_CONFIG.cognito.identityPoolId,
                        Logins: {
                            [`cognito-idp.${AWS_CONFIG.region}.amazonaws.com/${AWS_CONFIG.cognito.userPoolId}`]: this.userToken
                        }
                    });
                } else {
                    // Unauthenticated credentials (read-only browsing)
                    AWS.config.credentials = new AWS.CognitoIdentityCredentials({
                        IdentityPoolId: AWS_CONFIG.cognito.identityPoolId
                    });
                }

                // Refresh AWS credentials
                await new Promise((resolve, reject) => {
                    AWS.config.credentials.get((err) => {
                        if (err) {
                            console.error('Failed to get AWS credentials:', err);
                            reject(err);
                        } else {
                            resolve();
                        }
                    });
                });

                // Initialize S3 client for image uploads
                this.s3 = new AWS.S3({
                    apiVersion: '2006-03-01',
                    params: { Bucket: AWS_CONFIG.s3.bucketName }
                });
            } else {
                this.s3 = null;
            }

            this.initialized = true;
            
        } catch (error) {
            console.error('AWS initialization failed:', error);
            throw new Error('Failed to initialize AWS services. Please check your configuration.');
        }
    }

    /**
     * Check for existing Cognito session (auto-login)
     */
    async checkExistingSession() {
        return new Promise((resolve) => {
            const cognitoUser = this.userPool.getCurrentUser();
            
            if (!cognitoUser) {
                resolve(null);
                return;
            }

            cognitoUser.getSession((err, session) => {
                if (err || !session.isValid()) {
                    resolve(null);
                    return;
                }
                
                // Session is valid - restore user state
                this.userToken = session.getIdToken().getJwtToken();
                this.currentUser = cognitoUser;
                
                // Parse JWT token to get groups and other claims
                const idTokenPayload = session.getIdToken().payload;
                
                // Fetch user attributes
                cognitoUser.getUserAttributes((err, attributes) => {
                    if (!err && attributes) {
                        this.userAttributes = {};
                        attributes.forEach(attr => {
                            this.userAttributes[attr.Name] = attr.Value;
                        });
                        
                        // Add JWT claims (including groups) to userAttributes
                        if (idTokenPayload['cognito:groups']) {
                            this.userAttributes['cognito:groups'] = idTokenPayload['cognito:groups'];
                        }
                        if (idTokenPayload.sub) {
                            this.userAttributes.sub = idTokenPayload.sub;
                        }
                    }
                    resolve(session);
                });
            });
        });
    }

    /**
     * Register new user via Cognito User Pool
     * @param {string} email - User's email address
     * @param {string} password - Password (min 8 chars, requires uppercase, lowercase, number)
     * @param {string} fullName - User's full name
     */
    async register(email, password, fullName) {
        if (!this.initialized) {
            throw new Error('AWS Service not initialized. Call initialize() first.');
        }

        return new Promise((resolve, reject) => {
            const attributeList = [
                new AmazonCognitoIdentity.CognitoUserAttribute({
                    Name: 'email',
                    Value: email
                }),
                new AmazonCognitoIdentity.CognitoUserAttribute({
                    Name: 'name',
                    Value: fullName
                })
            ];

            this.userPool.signUp(email, password, attributeList, null, (err, result) => {
                if (err) {
                    console.error('Registration failed:', err);
                    reject(err);
                    return;
                }
                
                resolve({
                    success: true,
                    user: result.user,
                    userConfirmed: result.userConfirmed,
                    message: 'Registration successful! Please check your email to verify your account.'
                });
            });
        });
    }

    /**
     * Confirm user registration with verification code
     * @param {string} email - User's email
     * @param {string} code - Verification code from email
     */
    async confirmRegistration(email, code) {
        if (!this.initialized) {
            throw new Error('AWS Service not initialized. Call initialize() first.');
        }

        return new Promise((resolve, reject) => {
            const cognitoUser = new AmazonCognitoIdentity.CognitoUser({
                Username: email,
                Pool: this.userPool
            });

            cognitoUser.confirmRegistration(code, true, (err, result) => {
                if (err) {
                    console.error('Verification failed:', err);
                    reject(err);
                    return;
                }
                
                resolve(result);
            });
        });
    }

    /**
     * Resend confirmation code to user's email
     * @param {string} email - User's email
     */
    async resendConfirmationCode(email) {
        if (!this.initialized) {
            throw new Error('AWS Service not initialized. Call initialize() first.');
        }

        return new Promise((resolve, reject) => {
            const cognitoUser = new AmazonCognitoIdentity.CognitoUser({
                Username: email,
                Pool: this.userPool
            });

            cognitoUser.resendConfirmationCode((err, result) => {
                if (err) {
                    console.error('Resend code failed:', err);
                    reject(err);
                    return;
                }
                
                resolve(result);
            });
        });
    }

    /**
     * Login user via Cognito User Pool
     * @param {string} email - User's email
     * @param {string} password - User's password
     */
    async login(email, password) {
        if (!this.initialized) {
            throw new Error('AWS Service not initialized. Call initialize() first.');
        }

        return new Promise((resolve, reject) => {
            const authenticationDetails = new AmazonCognitoIdentity.AuthenticationDetails({
                Username: email,
                Password: password
            });

            const cognitoUser = new AmazonCognitoIdentity.CognitoUser({
                Username: email,
                Pool: this.userPool
            });

            cognitoUser.authenticateUser(authenticationDetails, {
                onSuccess: async (result) => {
                    this.userToken = result.getIdToken().getJwtToken();
                    this.currentUser = cognitoUser;
                    
                    // Parse JWT token to get groups and other claims
                    const idTokenPayload = result.getIdToken().payload;
                    
                    // Fetch user attributes - wait for completion
                    await new Promise((resolveAttrs, rejectAttrs) => {
                        cognitoUser.getUserAttributes((err, attributes) => {
                            if (err) {
                                console.warn('Could not fetch user attributes:', err);
                                this.userAttributes = {};
                                resolveAttrs();
                            } else if (attributes) {
                                this.userAttributes = {};
                                attributes.forEach(attr => {
                                    this.userAttributes[attr.Name] = attr.Value;
                                });
                                resolveAttrs();
                            } else {
                                this.userAttributes = {};
                                resolveAttrs();
                            }
                        });
                    });
                    
                    // Add JWT claims (including groups) to userAttributes
                    if (idTokenPayload['cognito:groups']) {
                        this.userAttributes['cognito:groups'] = idTokenPayload['cognito:groups'];
                    }
                    if (idTokenPayload.sub) {
                        this.userAttributes.sub = idTokenPayload.sub;
                    }

                    // Update AWS credentials with authenticated token (if Identity Pool exists)
                    if (AWS_CONFIG.cognito.identityPoolId) {
                        AWS.config.credentials = new AWS.CognitoIdentityCredentials({
                            IdentityPoolId: AWS_CONFIG.cognito.identityPoolId,
                            Logins: {
                                [`cognito-idp.${AWS_CONFIG.region}.amazonaws.com/${AWS_CONFIG.cognito.userPoolId}`]: this.userToken
                            }
                        });

                        // Refresh credentials
                        await new Promise((resolve2, reject2) => {
                            AWS.config.credentials.get((err) => {
                                if (err) reject2(err);
                                else resolve2();
                            });
                        });
                    }

                    resolve({
                        success: true,
                        token: this.userToken,
                        email: email,
                        name: this.userAttributes?.name || email.split('@')[0]
                    });
                },
                onFailure: (err) => {
                    console.error('Login failed:', err);
                    reject(err);
                },
                newPasswordRequired: (userAttributes, requiredAttributes) => {
                    reject(new Error('New password required. Please contact support.'));
                }
            });
        });
    }

    /**
     * Logout current user
     */
    logout() {
        if (this.currentUser) {
            this.currentUser.signOut();
        }
        
        this.currentUser = null;
        this.userToken = null;
        this.userAttributes = null;
        
        // Reset to unauthenticated credentials (if Identity Pool exists)
        if (this.initialized && AWS_CONFIG.cognito.identityPoolId) {
            AWS.config.credentials = new AWS.CognitoIdentityCredentials({
                IdentityPoolId: AWS_CONFIG.cognito.identityPoolId
            });
        }
        
    }

    /**
     * Check if user is authenticated
     * @returns {boolean}
     */
    isAuthenticated() {
        return !!(this.userToken && this.currentUser);
    }

    /**
     * Get current user information
     * @returns {Object|null} User object with email, name, userId
     */
    getCurrentUser() {
        if (!this.userAttributes) return null;
        
        return {
            email: this.userAttributes.email,
            name: this.userAttributes.name,
            userId: this.userAttributes.sub
        };
    }

    /**
     * Check if current user has admin privileges
     * @returns {boolean} True if user is an admin
     */
    isAdmin() {
        if (!this.isAuthenticated()) return false;
        
        // Check if userAttributes is loaded
        if (!this.userAttributes) return false;
        
        // Check if user belongs to 'Admins' Cognito group
        const groups = this.userAttributes['cognito:groups'];
        
        // Return false if groups attribute doesn't exist (user not in any groups)
        if (!groups) return false;
        
        // cognito:groups can be a string or array depending on how it's parsed
        if (Array.isArray(groups)) {
            return groups.includes('Admins');
        } else if (typeof groups === 'string') {
            return groups.split(',').includes('Admins');
        }
        
        return false;
    }

    /**
     * Upload image to S3 bucket
     * @param {File} file - Image file to upload
     * @param {string} itemId - Unique identifier for the item
     * @returns {Promise<string>} Base64-encoded image data for Lambda upload
     */
    async uploadImage(file, itemId) {
        if (!this.initialized) {
            throw new Error('AWS Service not initialized. Call initialize() first.');
        }

        if (!this.isAuthenticated()) {
            throw new Error('You must be logged in to upload images');
        }

        // Convert image to base64 for Lambda upload (AWS Academy compatible)
        try {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => {
                    resolve(reader.result); // Returns data URL (data:image/png;base64,...)
                };
                reader.onerror = () => {
                    reject(new Error('Failed to read image file'));
                };
                reader.readAsDataURL(file);
            });
        } catch (error) {
            console.error('Image conversion failed:', error);
            throw new Error('Failed to process image: ' + error.message);
        }
    }

    /**
     * Create new item via API Gateway + Lambda
     * @param {Object} item - Item data (title, description, status, etc.)
     * @param {string} imageBase64 - Base64-encoded image data (optional)
     * @returns {Promise<Object>} API response with item ID
     */
    async saveItem(item, imageBase64 = null) {
        if (!this.initialized) {
            throw new Error('AWS Service not initialized. Call initialize() first.');
        }

        if (!this.isAuthenticated()) {
            throw new Error('You must be logged in to post an item');
        }

        try {
            // Add user metadata to item
            const userInfo = this.getCurrentUser();
            const itemData = {
                ...item,
                userId: userInfo.userId,
                userEmail: userInfo.email,
                userName: userInfo.name,
                createdAt: new Date().toISOString()
            };
            
            // Add base64 image if provided
            if (imageBase64) {
                itemData.imageBase64 = imageBase64;
            }

            const response = await fetch(AWS_CONFIG.api.endpoint + AWS_CONFIG.api.endpoints.items, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': this.userToken
                },
                body: JSON.stringify(itemData)
            });

            if (!response.ok) {
                const error = await response.text();
                throw new Error(`API request failed: ${response.status} - ${error}`);
            }

            const result = await response.json();
            return result;
            
        } catch (error) {
            console.error('Failed to save item:', error);
            throw new Error('Failed to save item: ' + error.message);
        }
    }

    /**
     * Get items from DynamoDB via API Gateway
     * Public endpoint - no authentication required for browsing
     * @param {number} limit - Maximum number of items to retrieve
     * @returns {Promise<Array>} Array of item objects
     */
    async getItems(limit = 25) {
        if (!this.initialized) {
            throw new Error('AWS Service not initialized. Call initialize() first.');
        }

        try {
            const url = `${AWS_CONFIG.api.endpoint}${AWS_CONFIG.api.endpoints.items}?limit=${limit}`;
            const headers = {};
            
            // Include auth token if available (for personalized results)
            if (this.userToken) {
                headers['Authorization'] = this.userToken;
            }

            const response = await fetch(url, { headers });
            
            if (!response.ok) {
                const error = await response.text();
                throw new Error(`API request failed: ${response.status} - ${error}`);
            }

            const data = await response.json();
            // Handle both array and object responses
            const items = Array.isArray(data) ? data : (data.items || []);
            return items;
            
        } catch (error) {
            console.error('Failed to fetch items:', error);
            // Return empty array on error instead of fallback
            return [];
        }
    }

    /**
     * Delete item from DynamoDB via API Gateway
     * Requires authentication and ownership verification (handled by Lambda)
     * @param {string} itemId - ID of item to delete
     * @returns {Promise<Object>} API response
     */
    /**
     * Update item status (mark as resolved/active)
     * @param {string} itemId - ID of item to update
     * @param {boolean} resolved - Whether item is resolved
     * @returns {Promise<Object>} API response
     */
    async updateItem(itemId, resolved = true) {
        if (!this.initialized) {
            throw new Error('AWS Service not initialized. Call initialize() first.');
        }

        if (!this.isAuthenticated()) {
            throw new Error('You must be logged in to update items');
        }

        try {
            const updateUrl = `${AWS_CONFIG.api.endpoint}${AWS_CONFIG.api.endpoints.items}/id?id=${itemId}`;
            
            const response = await fetch(updateUrl, {
                method: 'PATCH',
                headers: {
                    'Authorization': this.userToken,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ resolved }),
                mode: 'cors'
            });

            if (!response.ok) {
                const error = await response.text();
                throw new Error(`Update request failed: ${response.status} - ${error}`);
            }

            const result = await response.json();
            return result;
            
        } catch (error) {
            console.error('Failed to update item:', error);
            
            if (error.message.includes('Failed to fetch')) {
                throw new Error('Network error: Unable to connect to server. Please check your internet connection and try again.');
            } else if (error.message.includes('CORS')) {
                throw new Error('CORS error: The API is not properly configured. Please contact support.');
            } else {
                throw new Error('Failed to update item: ' + error.message);
            }
        }
    }

    async deleteItem(itemId) {
        if (!this.initialized) {
            throw new Error('AWS Service not initialized. Call initialize() first.');
        }

        if (!this.isAuthenticated()) {
            throw new Error('You must be logged in to delete items');
        }

        try {
            const deleteUrl = `${AWS_CONFIG.api.endpoint}${AWS_CONFIG.api.endpoints.items}/id?id=${itemId}`;
            
            const response = await fetch(deleteUrl, {
                method: 'DELETE',
                headers: {
                    'Authorization': this.userToken,
                    'Content-Type': 'application/json'
                },
                mode: 'cors'
            });

            if (!response.ok) {
                const error = await response.text();
                console.error('Delete error response:', error);
                throw new Error(`Delete request failed: ${response.status} - ${error}`);
            }

            const result = await response.json();
            return result;
            
        } catch (error) {
            console.error('Failed to delete item:', error);
            console.error('Error details:', {
                name: error.name,
                message: error.message,
                stack: error.stack
            });
            
            // Provide more specific error messages
            if (error.message.includes('Failed to fetch')) {
                throw new Error('Network error: Unable to connect to server. Please check your internet connection and try again.');
            } else if (error.message.includes('CORS')) {
                throw new Error('CORS error: The API is not properly configured. Please contact support.');
            } else {
                throw new Error('Failed to delete item: ' + error.message);
            }
        }
    }

    /**
     * Send contact notification via SES (Lambda function)
     * Allows users to contact item owners privately without exposing email addresses
     * @param {string} itemId - ID of the item
     * @param {string} message - Message to send
     * @param {string} senderName - Name of sender
     * @param {string} senderEmail - Email of sender
     * @returns {Promise<Object>} API response
     */
    async sendContactNotification(itemId, message, senderName, senderEmail) {
        if (!this.initialized) {
            throw new Error('AWS Service not initialized. Call initialize() first.');
        }

        if (!this.isAuthenticated()) {
            throw new Error('You must be logged in to contact item owners');
        }

        try {
            const response = await fetch(`${AWS_CONFIG.api.endpoint}${AWS_CONFIG.api.endpoints.contact}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': this.userToken
                },
                body: JSON.stringify({
                    itemId,
                    message,
                    senderName,
                    senderEmail
                })
            });

            if (!response.ok) {
                const error = await response.text();
                throw new Error(`Contact request failed: ${response.status} - ${error}`);
            }

            const result = await response.json();
            return result;
            
        } catch (error) {
            console.error('Failed to send notification:', error);
            throw new Error('Failed to send notification: ' + error.message);
        }
    }

    /**
     * List all users from Cognito User Pool (Admin only)
     * @returns {Promise<Array>} Array of user objects
     */
    async listUsers() {
        if (!this.initialized) {
            throw new Error('AWS Service not initialized. Call initialize() first.');
        }

        if (!this.isAdmin()) {
            throw new Error('Admin privileges required to list users');
        }

        try {
            // Make API call to Lambda function that lists users
            const response = await fetch(`${AWS_CONFIG.api.endpoint}/users`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': this.userToken
                }
            });

            if (!response.ok) {
                throw new Error(`Failed to fetch users: ${response.status}`);
            }

            const users = await response.json();
            return users;
            
        } catch (error) {
            console.error('Failed to load users:', error);
            // Return empty array if endpoint doesn't exist yet
            return [];
        }
    }

    /**
     * Get all messages for the current user
     * @returns {Promise<Object>} Object with messages array and counts
     */
    async getMessages() {
        if (!this.initialized) {
            throw new Error('AWS Service not initialized. Call initialize() first.');
        }

        if (!this.isAuthenticated()) {
            throw new Error('You must be logged in to view messages');
        }

        try {
            
            const response = await fetch(`${AWS_CONFIG.api.endpoint}${AWS_CONFIG.api.endpoints.messages}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': this.userToken
                }
            });
            
            if (!response.ok) {
                const error = await response.text();
                console.error('Response error:', error);
                throw new Error(`Failed to fetch messages: ${response.status} - ${error}`);
            }

            const result = await response.json();
            return result;
            
        } catch (error) {
            console.error('Failed to load messages:', error);
            throw new Error('Failed to load messages: ' + error.message);
        }
    }

    /**
     * Send a reply in a conversation thread
     * @param {Object} replyData - { itemId, recipientUserId, message }
     * @returns {Promise<Object>} API response
     */
    async sendReply(replyData) {
        if (!this.initialized) {
            throw new Error('AWS Service not initialized. Call initialize() first.');
        }

        if (!this.isAuthenticated()) {
            throw new Error('You must be logged in to send messages');
        }

        try {
            
            const response = await fetch(`${AWS_CONFIG.api.endpoint}/messages/reply`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': this.userToken
                },
                body: JSON.stringify(replyData)
            });

            if (!response.ok) {
                const error = await response.text();
                throw new Error(`Failed to send reply: ${response.status} - ${error}`);
            }

            const result = await response.json();
            return result;
            
        } catch (error) {
            console.error('Failed to send reply:', error);
            throw new Error('Failed to send reply: ' + error.message);
        }
    }

    /**
     * Update user status (Block/Unblock) - Admin only
     * @param {string} username - The username to update
     * @param {string} action - 'block' or 'unblock'
     * @returns {Promise<Object>} API response
     */
    async updateUserStatus(username, action) {
        if (!this.initialized) {
            throw new Error('AWS Service not initialized. Call initialize() first.');
        }

        if (!this.isAdmin()) {
            throw new Error('Admin privileges required to update user status');
        }

        if (!username) {
            throw new Error('Username is required');
        }

        if (!['block', 'unblock'].includes(action)) {
            throw new Error('Action must be "block" or "unblock"');
        }

        try {
            
            const response = await fetch(`${AWS_CONFIG.api.endpoint}/users/${username}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': this.userToken
                },
                body: JSON.stringify({ action })
            });

            if (!response.ok) {
                const error = await response.text();
                throw new Error(`Failed to ${action} user: ${response.status} - ${error}`);
            }

            const result = await response.json();
            return result;
            
        } catch (error) {
            console.error(`Failed to ${action} user:`, error);
            throw new Error(`Failed to ${action} user: ` + error.message);
        }
    }


}

// Create global instance
window.awsService = new AWSService();

// Auto-initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    try {
        await window.awsService.initialize();
    } catch (error) {
        console.error('Failed to auto-initialize AWS services:', error);
    }
});

