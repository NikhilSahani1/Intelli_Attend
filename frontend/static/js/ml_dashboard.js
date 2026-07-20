/**
 * ML Dashboard Module
 * Handles ML analytics, charts, and fraud detection visualization
 */

class MLDashboard {
    constructor() {
        this.charts = {};
        this.updateInterval = null;
        this.fraudThreshold = 0.6;
    }

    /**
     * Initialize dashboard
     */
    initialize() {
        this.initCharts();
        this.startRealTimeUpdates();
        this.setupEventListeners();
    }

    /**
     * Initialize all charts
     */
    initCharts() {
        // Fraud Trend Chart
        if (document.getElementById('fraudTrendChart')) {
            this.charts.fraudTrend = this.createFraudTrendChart();
        }
        
        // Risk Distribution Chart
        if (document.getElementById('riskPieChart')) {
            this.charts.riskPie = this.createRiskPieChart();
        }
        
        // Anomaly Heatmap
        if (document.getElementById('anomalyHeatmap')) {
            this.initHeatmap();
        }
        
        // Model Performance Chart
        if (document.getElementById('modelPerformanceChart')) {
            this.charts.modelPerformance = this.createModelPerformanceChart();
        }
    }

    /**
     * Create fraud trend chart
     */
    createFraudTrendChart() {
        const ctx = document.getElementById('fraudTrendChart').getContext('2d');
        return new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'High Risk',
                        data: [],
                        borderColor: '#f72585',
                        backgroundColor: 'rgba(247, 37, 133, 0.1)',
                        tension: 0.4,
                        fill: true
                    },
                    {
                        label: 'Medium Risk',
                        data: [],
                        borderColor: '#f8961e',
                        backgroundColor: 'rgba(248, 150, 30, 0.1)',
                        tension: 0.4,
                        fill: true
                    },
                    {
                        label: 'Low Risk',
                        data: [],
                        borderColor: '#4cc9f0',
                        backgroundColor: 'rgba(76, 201, 240, 0.1)',
                        tension: 0.4,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                return `${context.dataset.label}: ${context.raw} incidents`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                }
            }
        });
    }

    /**
     * Create risk distribution pie chart
     */
    createRiskPieChart() {
        const ctx = document.getElementById('riskPieChart').getContext('2d');
        return new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['High Risk', 'Medium Risk', 'Low Risk'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: ['#f72585', '#f8961e', '#4cc9f0'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const value = context.raw;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                                return `${context.label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                },
                cutout: '60%'
            }
        });
    }

    /**
     * Create model performance chart
     */
    createModelPerformanceChart() {
        const ctx = document.getElementById('modelPerformanceChart').getContext('2d');
        return new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['Accuracy', 'Precision', 'Recall', 'F1 Score', 'Specificity'],
                datasets: [{
                    label: 'Current Model',
                    data: [0.95, 0.92, 0.89, 0.91, 0.94],
                    backgroundColor: 'rgba(67, 97, 238, 0.2)',
                    borderColor: '#4361ee',
                    pointBackgroundColor: '#4361ee',
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: '#4361ee'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                elements: {
                    line: {
                        borderWidth: 3
                    }
                },
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 1,
                        ticks: {
                            stepSize: 0.2,
                            callback: (value) => (value * 100) + '%'
                        }
                    }
                }
            }
        });
    }

    /**
     * Initialize heatmap
     */
    initHeatmap() {
        const heatmapData = this.generateHeatmapData();
        // Heatmap initialization would go here
        // This could use libraries like heatmap.js or custom implementation
    }

    /**
     * Generate heatmap data
     */
    generateHeatmapData() {
        const data = [];
        for (let hour = 0; hour < 24; hour++) {
            for (let day = 0; day < 7; day++) {
                data.push({
                    x: day,
                    y: hour,
                    value: Math.random() * 10
                });
            }
        }
        return data;
    }

    /**
     * Start real-time updates
     */
    startRealTimeUpdates() {
        this.updateInterval = setInterval(() => {
            this.fetchLatestData();
        }, 30000); // Update every 30 seconds
    }

    /**
     * Stop real-time updates
     */
    stopRealTimeUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
    }

    /**
     * Fetch latest data from API
     */
    async fetchLatestData() {
        try {
            const response = await fetch('/ml/stats');
            const data = await response.json();
            
            if (data.success) {
                this.updateCharts(data);
                this.updateStats(data);
                this.checkAnomalies(data);
            }
        } catch (error) {
            console.error('Failed to fetch ML stats:', error);
        }
    }

    /**
     * Update charts with new data
     */
    updateCharts(data) {
        // Update fraud trend chart
        if (this.charts.fraudTrend && data.trend) {
            this.charts.fraudTrend.data.labels = data.trend.labels;
            this.charts.fraudTrend.data.datasets[0].data = data.trend.high;
            this.charts.fraudTrend.data.datasets[1].data = data.trend.medium;
            this.charts.fraudTrend.data.datasets[2].data = data.trend.low;
            this.charts.fraudTrend.update();
        }
        
        // Update risk distribution
        if (this.charts.riskPie && data.distribution) {
            this.charts.riskPie.data.datasets[0].data = [
                data.distribution.high,
                data.distribution.medium,
                data.distribution.low
            ];
            this.charts.riskPie.update();
        }
    }

    /**
     * Update statistics
     */
    updateStats(data) {
        const elements = {
            totalAnomalies: document.getElementById('totalAnomalies'),
            avgFraudScore: document.getElementById('avgFraudScore'),
            modelAccuracy: document.getElementById('modelAccuracy'),
            pendingAlerts: document.getElementById('pendingAlerts')
        };
        
        if (elements.totalAnomalies) {
            elements.totalAnomalies.textContent = data.stats?.total || 0;
        }
        
        if (elements.avgFraudScore) {
            elements.avgFraudScore.textContent = (data.stats?.avg_fraud * 100).toFixed(1) + '%';
        }
        
        if (elements.modelAccuracy) {
            elements.modelAccuracy.textContent = (data.model?.accuracy * 100).toFixed(1) + '%';
        }
        
        if (elements.pendingAlerts) {
            elements.pendingAlerts.textContent = data.alerts?.pending || 0;
        }
    }

    /**
     * Check for anomalies
     */
    checkAnomalies(data) {
        if (data.anomalies && data.anomalies.length > 0) {
            this.showAnomalyAlert(data.anomalies);
        }
    }

    /**
     * Show anomaly alert
     */
    showAnomalyAlert(anomalies) {
        const criticalCount = anomalies.filter(a => a.severity === 'CRITICAL').length;
        
        if (criticalCount > 0) {
            const alert = document.createElement('div');
            alert.className = 'alert alert-critical alert-dismissible fade show position-fixed top-0 end-0 m-3';
            alert.style.zIndex = 9999;
            alert.innerHTML = `
                <strong><i class="fas fa-exclamation-triangle me-2"></i>Critical Anomalies Detected!</strong>
                <p class="mb-0">${criticalCount} critical anomalies require immediate attention.</p>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;
            document.body.appendChild(alert);
            
            setTimeout(() => alert.remove(), 10000);
        }
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Filter changes
        const filterSelects = document.querySelectorAll('.ml-filter');
        filterSelects.forEach(select => {
            select.addEventListener('change', () => this.applyFilters());
        });
        
        // Refresh button
        const refreshBtn = document.getElementById('refreshMLData');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshData());
        }
        
        // Export button
        const exportBtn = document.getElementById('exportMLReport');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportReport());
        }
    }

    /**
     * Apply filters
     */
    applyFilters() {
        const filters = {
            dateRange: document.getElementById('dateRangeFilter')?.value,
            riskLevel: document.getElementById('riskLevelFilter')?.value,
            modelType: document.getElementById('modelTypeFilter')?.value
        };
        
        // Update charts based on filters
        this.fetchFilteredData(filters);
    }

    /**
     * Fetch filtered data
     */
    async fetchFilteredData(filters) {
        const params = new URLSearchParams(filters);
        
        try {
            const response = await fetch(`/ml/filtered-stats?${params}`);
            const data = await response.json();
            
            if (data.success) {
                this.updateCharts(data);
            }
        } catch (error) {
            console.error('Failed to fetch filtered data:', error);
        }
    }

    /**
     * Refresh data
     */
    async refreshData() {
        await this.fetchLatestData();
        this.showNotification('Dashboard refreshed', 'success');
    }

    /**
     * Export report
     */
    async exportReport() {
        const format = document.getElementById('exportFormat')?.value || 'csv';
        window.location.href = `/ml/export-report?format=${format}`;
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
     * Train models
     */
    async trainModels() {
        if (!confirm('This will retrain all ML models. This may take a few minutes. Continue?')) {
            return;
        }
        
        try {
            const response = await fetch('/ml/train-models', { method: 'POST' });
            const data = await response.json();
            
            if (data.success) {
                this.showNotification('Models trained successfully!', 'success');
                setTimeout(() => location.reload(), 2000);
            } else {
                this.showNotification('Training failed: ' + data.message, 'danger');
            }
        } catch (error) {
            console.error('Training failed:', error);
            this.showNotification('Training failed', 'danger');
        }
    }

    /**
     * View model details
     */
    async viewModelDetails(modelId) {
        try {
            const response = await fetch(`/ml/model/${modelId}`);
            const data = await response.json();
            
            if (data.success) {
                this.showModelDetailsModal(data.model);
            }
        } catch (error) {
            console.error('Failed to load model details:', error);
        }
    }

    /**
     * Show model details modal
     */
    showModelDetailsModal(model) {
        const modal = new bootstrap.Modal(document.getElementById('modelDetailsModal'));
        document.getElementById('modelDetailsBody').innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    <h6>Model Information</h6>
                    <table class="table table-sm">
                        <tr><th>Name:</th><td>${model.name}</td></tr>
                        <tr><th>Type:</th><td>${model.type}</td></tr>
                        <tr><th>Version:</th><td>${model.version}</td></tr>
                        <tr><th>Trained:</th><td>${model.trained_at}</td></tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h6>Performance Metrics</h6>
                    <table class="table table-sm">
                        <tr><th>Accuracy:</th><td>${(model.accuracy * 100).toFixed(2)}%</td></tr>
                        <tr><th>Precision:</th><td>${(model.precision * 100).toFixed(2)}%</td></tr>
                        <tr><th>Recall:</th><td>${(model.recall * 100).toFixed(2)}%</td></tr>
                        <tr><th>F1 Score:</th><td>${(model.f1_score * 100).toFixed(2)}%</td></tr>
                    </table>
                </div>
            </div>
            
            <h6 class="mt-3">Feature Importance</h6>
            <div class="progress-vertical-stack">
                ${Object.entries(model.feature_importance).map(([feature, importance]) => `
                    <div class="mb-2">
                        <div class="d-flex justify-content-between">
                            <small>${feature}</small>
                            <small>${(importance * 100).toFixed(1)}%</small>
                        </div>
                        <div class="progress" style="height: 5px;">
                            <div class="progress-bar bg-primary" style="width: ${importance * 100}%"></div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
        modal.show();
    }

    /**
     * Cleanup
     */
    destroy() {
        this.stopRealTimeUpdates();
        
        // Destroy charts
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.mlDashboard = new MLDashboard();
    window.mlDashboard.initialize();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.mlDashboard) {
        window.mlDashboard.destroy();
    }
});