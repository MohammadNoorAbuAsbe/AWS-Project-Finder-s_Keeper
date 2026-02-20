/**
 * Post Item Page Controller
 * Handles new item submission with validation, image upload, and AWS integration
 */

document.addEventListener('DOMContentLoaded', async () => {
    if (!await utils.requireAuth()) {
        return;
    }
    
    const imgInput = document.getElementById('itemImage');
    const preview = document.getElementById('imagePreview');
    const form = document.getElementById('postItemForm');
    
    const getSelectedFile = utils.setupImagePreview(imgInput, preview);

    utils.setupFormHandler(form, async (e) => {
        const title = document.getElementById('title').value.trim();
        const location = document.getElementById('location').value.trim();
        const date = document.getElementById('date').value;
        const description = document.getElementById('description').value.trim();
        
        const titleValidation = utils.validateText(title, 3, 'Title');
        if (!titleValidation.valid) {
            alert(titleValidation.error);
            throw new Error(titleValidation.error);
        }
        
        const locationValidation = utils.validateText(location, 3, 'Location');
        if (!locationValidation.valid) {
            alert(locationValidation.error);
            throw new Error(locationValidation.error);
        }
        
        const dateValidation = utils.validateDate(date);
        if (!dateValidation.valid) {
            alert(dateValidation.error);
            throw new Error(dateValidation.error);
        }
        
        const selectedFile = getSelectedFile();
        if (!selectedFile) {
            alert('Please upload an image for the item');
            throw new Error('No image selected');
        }
        
        const imageBase64 = await awsService.uploadImage(selectedFile, Date.now());
        
        const newItem = {
            title: utils.escapeHtml(title),
            status: document.querySelector('input[name="itemStatus"]:checked').value,
            category: document.getElementById('category').value,
            date: date,
            location: utils.escapeHtml(location),
            description: utils.escapeHtml(description),
            color: '',
            contact: 'Contact via platform',
            createdAt: new Date().toISOString()
        };

        const result = await awsService.saveItem(newItem, imageBase64);
        
        if (result.success || result.id) {
            alert('Item Published Successfully!');
            window.location.href = 'index.html';
        } else {
            throw new Error('Failed to save item');
        }
    }, 'Publishing...');
});