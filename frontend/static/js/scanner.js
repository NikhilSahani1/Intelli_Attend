/**
 * QR Scanner Module
 * Handles QR code scanning, camera access, and attendance processing
 */

class QRScanner {
    constructor() {
        this.codeReader = null;
        this.videoDeviceId = null;
        this.scanning = false;
        this.videoElement = document.getElementById('scanner-video');
        this.eventSelect = document.getElementById('eventSelect');
        this.lectureSelect = document.getElementById('lectureSelect');
        this.recentScans = [];
    }

    /**
     * Initialize the scanner
     */
    async initialize() {
        try {
            // Load ZXing library
            await this.loadZXing();
            
            // Check camera availability
            const devices = await navigator.mediaDevices.enumerateDevices();
            const videoDevices = devices.filter(device => device.kind === 'videoinput');
            
            if (videoDevices.length === 0) {
                throw new Error('No camera found');
            }
            
            this.codeReader = new ZXing.BrowserMultiFormatReader();
            return true;
        } catch (error) {
            console.error('Scanner initialization failed:', error);
            this.showError('Camera initialization failed: ' + error.message);
            return false;
        }
    }

    /**
     * Load ZXing library dynamically
     */
    loadZXing() {
        return new Promise((resolve, reject) => {
            if (window.ZXing) {
                resolve();
                return;
            }
            
            const script = document.createElement('script');
            script.src = 'https://unpkg.com/@zxing/library@0.19.1/umd/index.min.js';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    /**
     * Start scanning
     */
    async start() {
        if (!this.validateSelection()) {
            return;
        }

        try {
            const videoInputDevices = await this.codeReader.listVideoInputDevices();
            
            if (videoInputDevices.length === 0) {
                throw new Error('No camera found');
            }
            
            // Prefer back camera if available
            this.videoDeviceId = videoInputDevices.find(d => 
                d.label.toLowerCase().includes('back') || 
                d.label.toLowerCase().includes('environment')
            )?.deviceId || videoInputDevices[0].deviceId;
            
            await this.codeReader.decodeFromVideoDevice(
                this.videoDeviceId,
                'scanner-video',
                (result, error) => this.handleScan(result, error)
            );
            
            this.scanning = true;
            this.updateUI();
            
        } catch (error) {
            console.error('Failed to start scanner:', error);
            this.showError('Failed to start camera: ' + error.message);
        }
    }

    /**
     * Stop scanning
     */
    stop() {
        if (this.codeReader) {
            this.codeReader.reset();
        }
        this.scanning = false;
        this.updateUI();
    }

    /**
     * Validate event and lecture selection
     */
    validateSelection() {
        if (!this.eventSelect || !this.eventSelect.value) {
            this.showError('Please select an event first');
            return false;
        }
        
        if (!this.lectureSelect || !this.lectureSelect.value) {
            this.showError('Please select a lecture first');
            return false;
        }
        
        return true;
    }

    /**
     * Handle QR scan result
     */
    async handleScan(result, error) {
        if (result) {
            this.stop();
            await this.processQRCode(result.text);
        }
        
        if (error && !(error instanceof ZXing.NotFoundException)) {
            console.error('Scan error:', error);
        }
    }

    /**
     * Process scanned QR code
     */
    async processQRCode(qrData) {
        const eventId = this.eventSelect.value;
        const lectureId = this.lectureSelect.value;
        
        try {
            // Check if face verification is needed
            if (qrData.startsWith('MANUAL-')) {
                await this.processAttendance(qrData, eventId, lectureId);
            } else {
                // Show face verification modal for regular QR
                await this.showFaceVerification(qrData, eventId, lectureId);
            }
        } catch (error) {
            console.error('QR processing failed:', error);
            this.showError('Failed to process QR code: ' + error.message);
        }
    }

    /**
     * Process attendance marking
     */
    async processAttendance(qrData, eventId, lectureId, faceVerified = false) {
        try {
            const response = await fetch('/attendance/mark', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    qr_data: qrData,
                    event_id: eventId,
                    lecture_id: lectureId,
                    face_verified: faceVerified
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess(result.message);
                this.addToRecentScans(result.attendance);
                
                // Check for fraud detection
                if (result.fraud_detection && result.fraud_detection.has_fraud) {
                    this.showFraudAlert(result.fraud_detection);
                }
            } else {
                this.showError(result.message);
            }
            
        } catch (error) {
            console.error('Attendance marking failed:', error);
            this.showError('Failed to mark attendance: ' + error.message);
        }
    }

    /**
     * Show face verification modal
     */
    async showFaceVerification(qrData, eventId, lectureId) {
        // Store data for later use
        this.pendingQR = { qrData, eventId, lectureId };
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('faceModal'));
        modal.show();
        
        // Start face camera
        await this.startFaceCamera();
    }

    /**
     * Start face camera for verification
     */
    async startFaceCamera() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ 
                video: { 
                    width: 640,
                    height: 480,
                    facingMode: 'user'
                } 
            });
            
            const video = document.getElementById('face-video');
            video.srcObject = stream;
            video.play();
            
            this.faceStream = stream;
            
        } catch (error) {
            console.error('Face camera failed:', error);
            this.showError('Failed to start face camera');
        }
    }

    /**
     * Capture face image for verification
     */
    async captureFace() {
        const video = document.getElementById('face-video');
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        
        // Show loading
        document.getElementById('faceProgress').style.display = 'block';
        document.getElementById('captureFaceBtn').disabled = true;
        
        // Convert to blob
        const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg'));
        
        // Send for verification
        const formData = new FormData();
        formData.append('face_image', blob, 'face.jpg');
        formData.append('user_id', this.extractUserIdFromQR(this.pendingQR.qrData));
        
        try {
            const response = await fetch('/ml/face/verify', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.match) {
                await this.processAttendance(
                    this.pendingQR.qrData,
                    this.pendingQR.eventId,
                    this.pendingQR.lectureId,
                    true
                );
            } else {
                this.showError('Face verification failed: ' + result.message);
            }
            
        } catch (error) {
            console.error('Face verification failed:', error);
            this.showError('Face verification failed');
            
        } finally {
            // Cleanup
            document.getElementById('faceProgress').style.display = 'none';
            document.getElementById('captureFaceBtn').disabled = false;
            
            if (this.faceStream) {
                this.faceStream.getTracks().forEach(track => track.stop());
            }
            
            bootstrap.Modal.getInstance(document.getElementById('faceModal')).hide();
        }
    }

    /**
     * Extract user ID from QR data
     */
    extractUserIdFromQR(qrData) {
        return qrData.split('-')[0];
    }

    /**
     * Add scan to recent list
     */
    addToRecentScans(attendance) {
        const container = document.getElementById('recentScans');
        if (!container) return;
        
        const item = document.createElement('a');
        item.href = '#';
        item.className = 'list-group-item list-group-item-action';
        item.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <h6 class="mb-1">${attendance.user_name}</h6>
                    <small>${attendance.event_name} - ${attendance.lecture_name}</small>
                </div>
                <small class="text-muted">${new Date().toLocaleTimeString()}</small>
            </div>
        `;
        
        container.insertBefore(item, container.firstChild);
        
        // Keep only last 10
        while (container.children.length > 10) {
            container.removeChild(container.lastChild);
        }
    }

    /**
     * Show fraud alert
     */
    showFraudAlert(fraudDetection) {
        const alert = document.createElement('div');
        alert.className = `alert alert-${fraudDetection.risk_level === 'HIGH' ? 'danger' : 'warning'} alert-dismissible fade show position-fixed bottom-0 end-0 m-3`;
        alert.style.zIndex = 9999;
        alert.innerHTML = `
            <strong><i class="fas fa-exclamation-triangle me-2"></i>Fraud Alert!</strong>
            <p class="mb-0">Risk Level: ${fraudDetection.risk_level}</p>
            <p class="mb-0">Score: ${fraudDetection.fraud_score}</p>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(alert);
        
        setTimeout(() => alert.remove(), 5000);
    }

    /**
     * Show success message
     */
    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    /**
     * Show error message
     */
    showError(message) {
        this.showNotification(message, 'danger');
    }

    /**
     * Show notification
     */
    showNotification(message, type) {
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 end-0 m-3`;
        alert.style.zIndex = 9999;
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(alert);
        
        setTimeout(() => alert.remove(), 3000);
    }

    /**
     * Update UI based on scanning state
     */
    updateUI() {
        const startBtn = document.getElementById('startScanner');
        const stopBtn = document.getElementById('stopScanner');
        const container = document.getElementById('scanner-container');
        
        if (startBtn) startBtn.style.display = this.scanning ? 'none' : 'inline-block';
        if (stopBtn) stopBtn.style.display = this.scanning ? 'inline-block' : 'none';
        if (container) container.style.display = this.scanning ? 'block' : 'none';
    }
}

// Initialize scanner when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.qrScanner = new QRScanner();
    
    // Setup event listeners
    const startBtn = document.getElementById('startScanner');
    const stopBtn = document.getElementById('stopScanner');
    const captureFaceBtn = document.getElementById('captureFaceBtn');
    
    if (startBtn) {
        startBtn.addEventListener('click', () => window.qrScanner.start());
    }
    
    if (stopBtn) {
        stopBtn.addEventListener('click', () => window.qrScanner.stop());
    }
    
    if (captureFaceBtn) {
        captureFaceBtn.addEventListener('click', () => window.qrScanner.captureFace());
    }
});