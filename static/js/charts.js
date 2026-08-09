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
                    'rgba(160, 192, 0, 0.7)',
                    'rgba(128, 160, 0, 0.7)',
                    'rgba(192, 160, 0, 0.7)',
                    'rgba(192, 64, 64, 0.7)',
                    'rgba(96, 128, 128, 0.7)',
                ],
                borderColor: [
                    'rgba(160, 192, 0, 1)',
                    'rgba(128, 160, 0, 1)',
                    'rgba(192, 160, 0, 1)',
                    'rgba(192, 64, 64, 1)',
                    'rgba(96, 128, 128, 1)',
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
                    color: '#e0e0e0',
                    font: { size: 16, weight: 'bold' }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: { color: '#a0a0a0', callback: v => v + '%' },
                    grid: { color: 'rgba(64, 64, 64, 0.5)' }
                },
                x: {
                    ticks: { color: '#a0a0a0' },
                    grid: { color: 'rgba(64, 64, 64, 0.3)' }
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
                backgroundColor: 'rgba(96, 128, 128, 0.7)',
                borderColor: 'rgba(96, 128, 128, 1)',
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
                    color: '#e0e0e0',
                    font: { size: 16, weight: 'bold' }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: { color: '#a0a0a0', callback: v => v + ' ms' },
                    grid: { color: 'rgba(64, 64, 64, 0.5)' }
                },
                y: {
                    ticks: { color: '#a0a0a0' },
                    grid: { color: 'rgba(64, 64, 64, 0.3)' }
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
                    'rgba(160, 192, 0, 0.8)',
                    'rgba(128, 160, 0, 0.8)',
                    'rgba(192, 160, 0, 0.8)',
                    'rgba(192, 64, 64, 0.8)',
                    'rgba(64, 96, 96, 0.8)',
                ],
                borderColor: '#2a2a2a',
                borderWidth: 3,
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Memory Usage (MB)',
                    color: '#e0e0e0',
                    font: { size: 16, weight: 'bold' }
                },
                legend: {
                    position: 'bottom',
                    labels: { color: '#a0a0a0', padding: 15 }
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
        { bg: 'rgba(160, 192, 0, 0.2)', border: 'rgba(160, 192, 0, 1)' },
        { bg: 'rgba(128, 160, 0, 0.2)', border: 'rgba(128, 160, 0, 1)' },
        { bg: 'rgba(192, 160, 0, 0.2)', border: 'rgba(192, 160, 0, 1)' },
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
                    color: '#e0e0e0',
                    font: { size: 16, weight: 'bold' }
                },
                legend: {
                    labels: { color: '#a0a0a0' }
                }
            },
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    ticks: { color: '#a0a0a0', backdropColor: 'transparent' },
                    grid: { color: 'rgba(64, 64, 64, 0.5)' },
                    angleLines: { color: 'rgba(64, 64, 64, 0.5)' },
                    pointLabels: { color: '#e0e0e0', font: { size: 12 } }
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
                    borderColor: 'rgba(160, 192, 0, 1)',
                    backgroundColor: 'rgba(160, 192, 0, 0.1)',
                    fill: true,
                    tension: 0.4,
                    yAxisID: 'y',
                },
                {
                    label: 'Latency (ms)',
                    data: latencyValues,
                    borderColor: 'rgba(192, 160, 0, 1)',
                    backgroundColor: 'rgba(192, 160, 0, 0.1)',
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
                    color: '#e0e0e0',
                    font: { size: 16, weight: 'bold' }
                },
                legend: { labels: { color: '#a0a0a0' } }
            },
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    ticks: { color: '#a0a0a0', callback: v => v + '%' },
                    grid: { color: 'rgba(64, 64, 64, 0.5)' }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    ticks: { color: '#a0a0a0', callback: v => v + ' ms' },
                    grid: { drawOnChartArea: false }
                },
                x: {
                    ticks: { color: '#a0a0a0' },
                    grid: { color: 'rgba(64, 64, 64, 0.3)' }
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
