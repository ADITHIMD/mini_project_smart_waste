// ============= AUDIO FUNCTIONS =============

/**
 * Play buzzer sound (FULL bin - 100%)
 * Frequency: 800Hz, Duration: 2 seconds, Type: Square wave
 */
function playBuzzer() {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const duration = 2;
    const frequency = 800;
    
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    oscillator.type = 'square';
    oscillator.frequency.value = frequency;
    
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + duration);
    
    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + duration);
    
    console.log('🔊 Buzzer sound played (FULL bin)');
}

/**
 * Play warning beep sound (ALMOST_FULL bin - 80%)
 * Frequency: 1000Hz, 3 beeps, Type: Sine wave
 */
function playBeep() {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const beepDuration = 0.3;
    const pauseDuration = 0.2;
    const frequency = 1000;
    const beepCount = 3;
    
    for (let i = 0; i < beepCount; i++) {
        const startTime = audioContext.currentTime + (i * (beepDuration + pauseDuration));
        
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.type = 'sine';
        oscillator.frequency.value = frequency;
        
        gainNode.gain.setValueAtTime(0.2, startTime);
        gainNode.gain.setValueAtTime(0.2, startTime + beepDuration);
        gainNode.gain.setValueAtTime(0, startTime + beepDuration + 0.01);
        
        oscillator.start(startTime);
        oscillator.stop(startTime + beepDuration);
    }
    
    console.log('⚠️ Warning beep sound played (ALMOST_FULL bin)');
}

/**
 * Test buzzer sound
 */
function testBuzzer() {
    playBuzzer();
}

/**
 * Test beep sound
 */
function testBeep() {
    playBeep();
}

// ============= DRAG & DROP FUNCTIONS =============

/**
 * Setup drag and drop listeners for upload area
 */
function setupDragAndDrop() {
    const uploadArea = document.getElementById('uploadArea');
    
    if (!uploadArea) return;
    
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });
    
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('drag-over');
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].type.startsWith('image/')) {
            const input = document.getElementById('imageInput');
            if (input) {
                input.files = files;
                input.dispatchEvent(new Event('change'));
            }
        }
    });
}

// ============= UTILITY FUNCTIONS =============

/**
 * Format date to readable string
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

/**
 * Format confidence as percentage
 */
function formatConfidence(confidence) {
    return (confidence * 100).toFixed(2) + '%';
}

/**
 * Get bin status color
 */
function getBinStatusColor(status) {
    switch(status) {
        case 'OK':
            return '#4CAF50';
        case 'ALMOST_FULL':
            return '#FFC107';
        case 'FULL':
            return '#f44336';
        default:
            return '#999';
    }
}

/**
 * Show notification message
 */
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 25px;
        border-radius: 10px;
        color: white;
        font-weight: 600;
        z-index: 10000;
        animation: slideInRight 0.3s ease;
        background: ${type === 'success' ? '#4CAF50' : type === 'warning' ? '#FFC107' : '#f44336'};
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    `;
    
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

/**
 * Validate image file
 */
function validateImageFile(file) {
    const maxSize = 16 * 1024 * 1024; // 16MB
    const validTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    
    if (!file) {
        return { valid: false, error: 'No file selected' };
    }
    
    if (!validTypes.includes(file.type)) {
        return { valid: false, error: 'Invalid image format. Please use JPEG, PNG, GIF, or WebP' };
    }
    
    if (file.size > maxSize) {
        return { valid: false, error: 'Image size exceeds 16MB limit' };
    }
    
    return { valid: true };
}

// ============= API FUNCTIONS =============

/**
 * Detect waste from image
 */
async function detectWaste(formData) {
    try {
        const response = await fetch('/detect-waste', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Detection error:', error);
        throw error;
    }
}

/**
 * Get current bin status
 */
async function getBinStatus() {
    try {
        const response = await fetch('/get-bins');
        const data = await response.json();
        return data.bins;
    } catch (error) {
        console.error('Error fetching bins:', error);
        return [];
    }
}

/**
 * Get detection history
 */
async function getHistory() {
    try {
        const response = await fetch('/get-history');
        const data = await response.json();
        return data.history;
    } catch (error) {
        console.error('Error fetching history:', error);
        return [];
    }
}

/**
 * Get statistics
 */
async function getStats() {
    try {
        const response = await fetch('/get-stats');
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error fetching stats:', error);
        return null;
    }
}

/**
 * Reset all data
 */
async function resetAllData() {
    if (!confirm('⚠️ Are you sure you want to reset all data? This action cannot be undone.')) {
        return false;
    }
    
    try {
        const response = await fetch('/reset-data', {
            method: 'POST'
        });
        const data = await response.json();
        showNotification(data.message, 'success');
        return true;
    } catch (error) {
        console.error('Error resetting data:', error);
        showNotification('Error resetting data', 'error');
        return false;
    }
}

// ============= DASHBOARD REFRESH =============

/**
 * Refresh all dashboard elements
 */
async function refreshDashboard() {
    try {
        // Refresh bins
        const bins = await getBinStatus();
        if (bins && bins.length > 0) {
            bins.forEach(bin => {
                updateBinDisplay(bin);
            });
        }
        
        // Refresh stats
        const stats = await getStats();
        if (stats) {
            updateStatsDisplay(stats);
        }
        
        // Refresh history
        const history = await getHistory();
        if (history) {
            updateHistoryDisplay(history);
        }
    } catch (error) {
        console.error('Error refreshing dashboard:', error);
    }
}

/**
 * Update bin display
 */
function updateBinDisplay(bin) {
    const binElement = document.getElementById(bin.bin_name.toLowerCase().split(' ')[0] + 'Bin');
    if (!binElement) return;
    
    // Update progress bar
    const progressBar = binElement.querySelector('.progress-fill');
    if (progressBar) {
        progressBar.style.width = bin.fill_level + '%';
        progressBar.textContent = bin.fill_level + '%';
    }
    
    // Update status badge
    const statusBadge = binElement.querySelector('.status');
    if (statusBadge) {
        statusBadge.textContent = bin.status;
        statusBadge.className = 'status';
        if (bin.status === 'ALMOST_FULL') {
            statusBadge.classList.add('almost-full');
        } else if (bin.status === 'FULL') {
            statusBadge.classList.add('full');
        }
    }
}

/**
 * Update stats display
 */
function updateStatsDisplay(stats) {
    const elements = {
        'totalWaste': stats.total_detections,
        'metalCount': stats.metal_count,
        'organicCount': stats.organic_count,
        'plasticCount': stats.plastic_count
    };
    
    for (const [id, value] of Object.entries(elements)) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }
}

/**
 * Update history display
 */
function updateHistoryDisplay(history) {
    const tbody = document.getElementById('historyBody');
    if (!tbody) return;
    
    if (history.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #999;">No detections yet</td></tr>';
        return;
    }
    
    tbody.innerHTML = history.map(item => `
        <tr>
            <td>${formatDate(item.detection_time)}</td>
            <td><strong>${item.waste_type}</strong></td>
            <td>${formatConfidence(item.confidence)}</td>
            <td>
                <span class="status-badge ${
                    item.status === 'ALMOST_FULL' ? 'almost-full' : 
                    item.status === 'FULL' ? 'full' : ''
                }">
                    ${item.status}
                </span>
            </td>
        </tr>
    `).join('');
}

// ============= INITIALIZATION =============

/**
 * Initialize on page load
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('Smart Waste Management System - JavaScript loaded');
    setupDragAndDrop();
    
    // Auto-refresh dashboard if on dashboard page
    const dashboard = document.getElementById('historyBody');
    if (dashboard) {
        refreshDashboard();
        setInterval(refreshDashboard, 3000);
    }
});

// ============= CSS ANIMATIONS =============

const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Export functions for console testing
window.wasteApp = {
    detectWaste,
    getBinStatus,
    getHistory,
    getStats,
    resetAllData,
    refreshDashboard,
    playBuzzer,
    playBeep,
    showNotification,
    validateImageFile
};