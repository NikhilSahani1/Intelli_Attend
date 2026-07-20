/**
 * Face Recognition Module
 * Handles face detection, enrollment, and verification
 */

class FaceRecognition {
    constructor() {
        this.video = null;
        this.canvas = null;
        this.stream = null;
        this.faceDetector = null;
        this.detectionInterval = null;
        this.onFaceDetected = null;
        this.onQualityUpdate = null;
        
        // Configuration
        this.minFaceSize = 100;
        this.qualityThreshold = 0.6;
        this.captureInterval = 500; // ms between quality checks
    }

    /**
     * Initialize face recognition
     */
    async initialize(videoElement, canvasElement) {
        this.video = videoElement;
        this.canvas = canvasElement;
        
        // Check for face detection API
        if ('FaceDetector' in window) {
            this.faceDetector = new FaceDetector({
                fastMode: true,
                maxDetectedFaces: 1
            });
        } else {
            console.warn('FaceDetector API not available, using fallback');
            await this.loadMediaPipe();
        }
        
        return true;
    }

    /**
     * Load MediaPipe as fallback
     */
    async loadMediaPipe() {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/@mediapipe/face_detection/face_detection.js';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    /**
     * Start camera
     */
    async startCamera(deviceId = null, facingMode = 'user') {
        try {
            const constraints = {
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: facingMode
                }
            };
            
            if (deviceId) {
                constraints.video.deviceId = { exact: deviceId };
            }
            
            this.stream = await navigator.mediaDevices.getUserMedia(constraints);
            this.video.srcObject = this.stream;
            await this.video.play();
            
            // Start face detection
            this.startDetection();
            
            return true;
            
        } catch (error) {
            console.error('Camera start failed:', error);
            throw error;
        }
    }

    /**
     * Stop camera
     */
    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        
        this.stopDetection();
        
        if (this.video) {
            this.video.srcObject = null;
        }
    }

    /**
     * Start face detection
     */
    startDetection() {
        this.detectionInterval = setInterval(async () => {
            await this.detectFaces();
        }, this.captureInterval);
    }

    /**
     * Stop face detection
     */
    stopDetection() {
        if (this.detectionInterval) {
            clearInterval(this.detectionInterval);
            this.detectionInterval = null;
        }
    }

    /**
     * Detect faces in video frame
     */
    async detectFaces() {
        if (!this.video || this.video.paused || this.video.ended) {
            return;
        }
        
        try {
            let faces = [];
            
            if (this.faceDetector) {
                // Use FaceDetector API
                faces = await this.faceDetector.detect(this.video);
            } else {
                // Use fallback detection
                faces = await this.detectFacesFallback();
            }
            
            if (faces.length > 0) {
                const face = faces[0];
                const quality = this.assessFaceQuality(face);
                
                if (this.onFaceDetected) {
                    this.onFaceDetected(face, quality);
                }
                
                if (this.onQualityUpdate) {
                    this.onQualityUpdate(quality);
                }
                
                return { face, quality };
            } else {
                if (this.onQualityUpdate) {
                    this.onQualityUpdate({ score: 0, message: 'No face detected' });
                }
                return null;
            }
            
        } catch (error) {
            console.error('Face detection error:', error);
            return null;
        }
    }

    /**
     * Fallback face detection using canvas and simple heuristics
     */
    async detectFacesFallback() {
        // Draw video frame to canvas
        const ctx = this.canvas.getContext('2d');
        ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
        
        // Get image data
        const imageData = ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
        
        // Simple skin tone detection (very basic fallback)
        const skinPixels = this.detectSkinTone(imageData);
        
        if (skinPixels.length > 1000) {
            // Return a simulated face object
            return [{
                boundingBox: {
                    x: this.canvas.width * 0.3,
                    y: this.canvas.height * 0.2,
                    width: this.canvas.width * 0.4,
                    height: this.canvas.height * 0.5
                },
                landmarks: []
            }];
        }
        
        return [];
    }

    /**
     * Detect skin tone pixels (very basic)
     */
    detectSkinTone(imageData) {
        const skinPixels = [];
        const data = imageData.data;
        
        for (let i = 0; i < data.length; i += 4) {
            const r = data[i];
            const g = data[i + 1];
            const b = data[i + 2];
            
            // Simple skin color range
            if (r > 60 && g > 40 && b > 20 && 
                r > g && r > b &&
                Math.abs(r - g) > 15) {
                skinPixels.push({ r, g, b });
            }
        }
        
        return skinPixels;
    }

    /**
     * Assess face quality
     */
    assessFaceQuality(face) {
        const box = face.boundingBox;
        let score = 0;
        const issues = [];
        
        // Check face size
        const faceSize = (box.width * box.height) / (this.video.videoWidth * this.video.videoHeight);
        if (faceSize < 0.1) {
            issues.push('Face too small');
            score += 0.2;
        } else if (faceSize > 0.5) {
            issues.push('Face too large');
            score += 0.3;
        } else {
            score += 0.4;
        }
        
        // Check face position (should be centered)
        const centerX = box.x + box.width / 2;
        const centerY = box.y + box.height / 2;
        const targetX = this.video.videoWidth / 2;
        const targetY = this.video.videoHeight / 2;
        
        const offsetX = Math.abs(centerX - targetX) / targetX;
        const offsetY = Math.abs(centerY - targetY) / targetY;
        
        if (offsetX > 0.3 || offsetY > 0.3) {
            issues.push('Face not centered');
            score += 0.2;
        } else {
            score += 0.3;
        }
        
        // Check for multiple faces
        if (face.landmarks && face.landmarks.length > 68) {
            score += 0.3; // Good landmark detection
        }
        
        // Normalize score
        const normalizedScore = Math.min(score, 1.0);
        
        // Determine quality level
        let level = 'Poor';
        if (normalizedScore > 0.8) level = 'Excellent';
        else if (normalizedScore > 0.6) level = 'Good';
        else if (normalizedScore > 0.4) level = 'Fair';
        
        return {
            score: normalizedScore,
            level: level,
            issues: issues,
            faceSize: faceSize,
            position: { x: centerX / this.video.videoWidth, y: centerY / this.video.videoHeight }
        };
    }

    /**
     * Capture face image
     */
    captureFace() {
        if (!this.video || !this.canvas) {
            throw new Error('Video or canvas not initialized');
        }
        
        const ctx = this.canvas.getContext('2d');
        ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
        
        return new Promise((resolve) => {
            this.canvas.toBlob(resolve, 'image/jpeg', 0.95);
        });
    }

    /**
     * Enroll face
     */
    async enrollFace(userId) {
        try {
            const blob = await this.captureFace();
            
            const formData = new FormData();
            formData.append('face_image', blob, 'face.jpg');
            formData.append('user_id', userId);
            
            const response = await fetch('/ml/face/enroll', {
                method: 'POST',
                body: formData
            });
            
            return await response.json();
            
        } catch (error) {
            console.error('Face enrollment failed:', error);
            throw error;
        }
    }

    /**
     * Verify face
     */
    async verifyFace(userId) {
        try {
            const blob = await this.captureFace();
            
            const formData = new FormData();
            formData.append('face_image', blob, 'face.jpg');
            formData.append('user_id', userId);
            
            const response = await fetch('/ml/face/verify', {
                method: 'POST',
                body: formData
            });
            
            return await response.json();
            
        } catch (error) {
            console.error('Face verification failed:', error);
            throw error;
        }
    }

    /**
     * Get available cameras
     */
    async getCameras() {
        const devices = await navigator.mediaDevices.enumerateDevices();
        return devices.filter(device => device.kind === 'videoinput');
    }

    /**
     * Set face detected callback
     */
    onFaceDetected(callback) {
        this.onFaceDetected = callback;
    }

    /**
     * Set quality update callback
     */
    onQualityUpdate(callback) {
        this.onQualityUpdate = callback;
    }

    /**
     * Draw face overlay
     */
    drawFaceOverlay(ctx, face, quality) {
        const box = face.boundingBox;
        
        // Draw bounding box
        ctx.strokeStyle = this.getQualityColor(quality.score);
        ctx.lineWidth = 3;
        ctx.strokeRect(box.x, box.y, box.width, box.height);
        
        // Draw landmarks if available
        if (face.landmarks) {
            ctx.fillStyle = '#4361ee';
            face.landmarks.forEach(landmark => {
                ctx.beginPath();
                ctx.arc(landmark.x, landmark.y, 2, 0, 2 * Math.PI);
                ctx.fill();
            });
        }
        
        // Draw quality text
        ctx.fillStyle = 'white';
        ctx.font = 'bold 14px Inter';
        ctx.shadowColor = 'black';
        ctx.shadowBlur = 4;
        ctx.fillText(`${quality.level} (${Math.round(quality.score * 100)}%)`, box.x, box.y - 5);
        ctx.shadowBlur = 0;
    }

    /**
     * Get color based on quality score
     */
    getQualityColor(score) {
        if (score > 0.8) return '#2ecc71'; // Success
        if (score > 0.6) return '#f1c40f'; // Warning
        if (score > 0.4) return '#e67e22'; // Danger
        return '#e74c3c'; // Critical
    }

    /**
     * Cleanup
     */
    destroy() {
        this.stopCamera();
        this.stopDetection();
        
        this.video = null;
        this.canvas = null;
        this.faceDetector = null;
        this.onFaceDetected = null;
        this.onQualityUpdate = null;
    }
}

// Export for use in other modules
window.FaceRecognition = FaceRecognition;
