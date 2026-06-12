/**
 * OpenBenchML - Charts JavaScript
 * =================================
 * Chart.js integration for benchmark visualizations.
 */

// ─── Accuracy Bar Chart ─────────────────────────────────────────────────────
function renderAccuracyChart(canvasId, labels, values) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Accuracy',
                data: values,
                backgroundColor: [
                    'rgba(59, 130, 246, 0.7)',
                    'rgba(34, 197, 94, 0.7)',
                    'rgba(234, 179, 8, 0.7)',
                    'rgba(239, 68, 68, 0.7)',
                    'rgba(6, 182, 212, 0.7)',
                ],
                borderColor: [
                    'rgba(59, 130, 246, 1)',
                    'rgba(34, 197, 94, 1)',
                    'rgba(234, 179, 8, 1)',
                    'rgba(239, 68, 68, 1)',
                    'rgba(6, 182, 212, 1)',
                ],
                borderWidth: 2,
                borderRadius: 6,
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                title: {
                    display: true,
                    text: 'Model Accuracy Comparison',
                    color: '#f1f5f9',
                    font: { size: 16, weight: 'bold' }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: { color: '#94a3b8', callback: v => v + '%' },
                    grid: { color: 'rgba(51, 65, 85, 0.5)' }
                },
                x: {
                    ticks: { color: '#94a3b8' },
                    grid: { color: 'rgba(51, 65, 85, 0.3)' }
                }
            }
        }
    });
}

// ─── Latency Comparison Chart ────────────────────────────────────────────────
function renderLatencyChart(canvasId, labels, values) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Latency (ms)',
                data: values,
                backgroundColor: 'rgba(6, 182, 212, 0.7)',
                borderColor: 'rgba(6, 182, 212, 1)',
                borderWidth: 2,
                borderRadius: 6,
            }]
        },
        options: {
            responsive: true,
            indexAxis: 'y',
            plugins: {
                legend: { display: false },
                title: {
                    display: true,
                    text: 'Inference Latency',
                    color: '#f1f5f9',
                    font: { size: 16, weight: 'bold' }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: { color: '#94a3b8', callback: v => v + ' ms' },
                    grid: { color: 'rgba(51, 65, 85, 0.5)' }
                },
                y: {
                    ticks: { color: '#94a3b8' },
                    grid: { color: 'rgba(51, 65, 85, 0.3)' }
                }
            }
        }
    });
}

// ─── Memory Usage Chart ──────────────────────────────────────────────────────
function renderMemoryChart(canvasId, labels, values) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: [
                    'rgba(59, 130, 246, 0.8)',
                    'rgba(34, 197, 94, 0.8)',
                    'rgba(234, 179, 8, 0.8)',
                    'rgba(239, 68, 68, 0.8)',
                    'rgba(168, 85, 247, 0.8)',
                ],
                borderColor: '#1e293b',
                borderWidth: 3,
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Memory Usage (MB)',
                    color: '#f1f5f9',
                    font: { size: 16, weight: 'bold' }
                },
                legend: {
                    position: 'bottom',
                    labels: { color: '#94a3b8', padding: 15 }
                }
            }
        }
    });
}

// ─── Multi-Metric Radar Chart ────────────────────────────────────────────────
function renderRadarChart(canvasId, modelNames, metricsData) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    const colors = [
        { bg: 'rgba(59, 130, 246, 0.2)', border: 'rgba(59, 130, 246, 1)' },
        { bg: 'rgba(34, 197, 94, 0.2)', border: 'rgba(34, 197, 94, 1)' },
        { bg: 'rgba(234, 179, 8, 0.2)', border: 'rgba(234, 179, 8, 1)' },
    ];

    const datasets = modelNames.map((name, i) => ({
        label: name,
        data: metricsData[i],
        backgroundColor: colors[i % colors.length].bg,
        borderColor: colors[i % colors.length].border,
        borderWidth: 2,
        pointBackgroundColor: colors[i % colors.length].border,
    }));

    new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['Accuracy', 'Precision', 'Recall', 'F1 Score', 'Speed', 'Efficiency'],
            datasets: datasets,
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Model Comparison Radar',
                    color: '#f1f5f9',
                    font: { size: 16, weight: 'bold' }
                },
                legend: {
                    labels: { color: '#94a3b8' }
                }
            },
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    ticks: { color: '#94a3b8', backdropColor: 'transparent' },
                    grid: { color: 'rgba(51, 65, 85, 0.5)' },
                    angleLines: { color: 'rgba(51, 65, 85, 0.5)' },
                    pointLabels: { color: '#f1f5f9', font: { size: 12 } }
                }
            }
        }
    });
}

// ─── Benchmark History Line Chart ────────────────────────────────────────────
function renderHistoryChart(canvasId, dates, accuracyValues, latencyValues) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'Accuracy',
                    data: accuracyValues,
                    borderColor: 'rgba(59, 130, 246, 1)',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0.4,
                    yAxisID: 'y',
                },
                {
                    label: 'Latency (ms)',
                    data: latencyValues,
                    borderColor: 'rgba(234, 179, 8, 1)',
                    backgroundColor: 'rgba(234, 179, 8, 0.1)',
                    fill: true,
                    tension: 0.4,
                    yAxisID: 'y1',
                }
            ]
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                title: {
                    display: true,
                    text: 'Benchmark History',
                    color: '#f1f5f9',
                    font: { size: 16, weight: 'bold' }
                },
                legend: { labels: { color: '#94a3b8' } }
            },
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    ticks: { color: '#94a3b8', callback: v => v + '%' },
                    grid: { color: 'rgba(51, 65, 85, 0.5)' }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    ticks: { color: '#94a3b8', callback: v => v + ' ms' },
                    grid: { drawOnChartArea: false }
                },
                x: {
                    ticks: { color: '#94a3b8' },
                    grid: { color: 'rgba(51, 65, 85, 0.3)' }
                }
            }
        }
    });
}

// ─── Export ──────────────────────────────────────────────────────────────────
window.OpenBenchCharts = {
    renderAccuracyChart,
    renderLatencyChart,
    renderMemoryChart,
    renderRadarChart,
    renderHistoryChart,
};
