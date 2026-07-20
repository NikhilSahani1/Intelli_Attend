// blink-detector.js - Automatic blink detection using MediaPipe

class BlinkDetector {
    constructor(options = {}) {
        this.blinkCount = 0;
        this.blinksRequired = options.blinksRequired || 3;
        this.earThreshold = options.earThreshold || 0.20;
        this.consecutiveFrames = options.consecutiveFrames || 2;
        this.onBlink = options.onBlink || (() => {});
        this.onComplete = options.onComplete || (() => {});
        this.onProgress = options.onProgress || (() => {});
        
        this.isBlinking = false;
        this.blinkFrameCount = 0;
        this.faceMesh = null;
        this.stream = null;
        this.isRunning = false;
        this.animationId = null;
    }
    
    async init(videoElement) {
        this.video = videoElement;
        
        // Initialize MediaPipe FaceMesh
        this.faceMesh = new FaceMesh({
            locateFile: (file) => {
                return `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`;
            }
        });
        
        this.faceMesh.setOptions({
            maxNumFaces: 1,
            refineLandmarks: true,
            minDetectionConfidence: 0.5,
            minTrackingConfidence: 0.5
        });
        
        this.faceMesh.onResults((results) => this.onFaceResults(results));
        
        // Start camera
        this.stream = await navigator.mediaDevices.getUserMedia({ video: true });
        this.video.srcObject = this.stream;
        await this.video.play();
        
        // Start detection loop
        this.isRunning = true;
        this.detectLoop();
        
        return true;
    }
    
    detectLoop() {
        if (!this.isRunning) return;
        
        if (this.video.readyState === this.video.HAVE_ENOUGH_DATA) {
            this.faceMesh.send({ image: this.video });
        }
        
        this.animationId = requestAnimationFrame(() => this.detectLoop());
    }
    
    onFaceResults(results) {
        if (!results.multiFaceLandmarks || results.multiFaceLandmarks.length === 0) {
            // No face detected
            return;
        }
        
        const landmarks = results.multiFaceLandmarks[0];
        
        // Calculate Eye Aspect Ratio (EAR)
        const leftEAR = this.calculateEAR(landmarks, this.getLeftEyeIndices());
        const rightEAR = this.calculateEAR(landmarks, this.getRightEyeIndices());
        const avgEAR = (leftEAR + rightEAR) / 2;
        
        // Detect blink
        this.detectBlink(avgEAR);
        
        // Update UI with EAR value for debugging
        if (this.onProgress) {
            this.onProgress({
                ear: avgEAR,
                blinkCount: this.blinkCount,
                isBlinking: avgEAR < this.earThreshold
            });
        }
    }
    
    calculateEAR(landmarks, eyeIndices) {
        // Get eye landmark coordinates
        const points = eyeIndices.map(idx => landmarks[idx]);
        
        // Calculate vertical distances (上下眼睑距离)
        const p2_p6 = Math.abs(points[1].y - points[5].y);
        const p3_p5 = Math.abs(points[2].y - points[4].y);
        
        // Calculate horizontal distance (眼角距离)
        const p1_p4 = Math.abs(points[0].x - points[3].x);
        
        // EAR formula
        const ear = (p2_p6 + p3_p5) / (2.0 * p1_p4);
        return ear;
    }
    
    getLeftEyeIndices() {
        // MediaPipe FaceMesh indices for left eye (using 468-point model)
        return [33, 133, 157, 158, 159, 160, 161, 173].map(idx => idx);
        // For EAR calculation we need specific points
        // Simplified: use min/max approach
    }
    
    getRightEyeIndices() {
        // MediaPipe FaceMesh indices for right eye
        return [362, 263, 387, 386, 385, 384, 398, 466].map(idx => idx);
    }
    
    detectBlink(ear) {
        if (ear < this.earThreshold) {
            // Eye is closing
            if (!this.isBlinking) {
                // Start of blink
                this.isBlinking = true;
                this.blinkFrameCount = 1;
            } else {
                this.blinkFrameCount++;
            }
        } else {
            // Eye is open
            if (this.isBlinking && this.blinkFrameCount >= this.consecutiveFrames) {
                // Blink completed!
                this.blinkCount++;
                this.onBlink(this.blinkCount);
                
                // Check if completed
                if (this.blinkCount >= this.blinksRequired) {
                    this.onComplete();
                    this.stop();
                }
            }
            this.isBlinking = false;
            this.blinkFrameCount = 0;
        }
    }
    
    stop() {
        this.isRunning = false;
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
        }
        if (this.video) {
            this.video.srcObject = null;
        }
    }
    
    reset() {
        this.blinkCount = 0;
        this.isBlinking = false;
        this.blinkFrameCount = 0;
    }
}