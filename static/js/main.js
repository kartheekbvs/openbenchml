/**
 * OpenBenchML - Main JavaScript
 * ===============================
 * Client-side utilities for the platform.
 */

document.addEventListener('DOMContentLoaded', () => {
    initMobileNav();
    initAlertDismiss();
    initConfirmDialogs();
    initAnimations();
});

// ─── Mobile Navigation Toggle ────────────────────────────────────────────────
function initMobileNav() {
    const toggle = document.querySelector('.nav-toggle');
    const links = document.querySelector('.navbar-links');
    if (toggle && links) {
        toggle.addEventListener('click', () => {
            links.classList.toggle('active');
            toggle.classList.toggle('active');
        });
    }
}

// ─── Alert Dismiss ───────────────────────────────────────────────────────────
function initAlertDismiss() {
    document.querySelectorAll('.alert-dismissible .alert-close').forEach(btn => {
        btn.addEventListener('click', () => {
            const alert = btn.closest('.alert');
            alert.style.animation = 'slide-down 0.3s ease reverse';
            setTimeout(() => alert.remove(), 300);
        });
    });

    // Auto-dismiss alerts after 5 seconds
    document.querySelectorAll('.alert-dismissible').forEach(alert => {
        setTimeout(() => {
            if (alert.parentNode) {
                alert.style.animation = 'slide-down 0.3s ease reverse';
                setTimeout(() => alert.remove(), 300);
            }
        }, 5000);
    });
}

// ─── Confirm Dialogs ─────────────────────────────────────────────────────────
function initConfirmDialogs() {
    document.querySelectorAll('[data-confirm]').forEach(el => {
        el.addEventListener('click', (e) => {
            const message = el.getAttribute('data-confirm');
            if (!confirm(message)) {
                e.preventDefault();
                e.stopImmediatePropagation();
            }
        });
    });
}

// ─── Scroll Animations ───────────────────────────────────────────────────────
function initAnimations() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1 });

    document.querySelectorAll('.card, .stat-card, .metric-card').forEach(el => {
        el.classList.add('animate-target');
        observer.observe(el);
    });
}

// ─── Utility: Format Numbers ─────────────────────────────────────────────────
function formatNumber(num, decimals = 2) {
    if (num === null || num === undefined) return 'N/A';
    return Number(num).toFixed(decimals);
}

function formatSize(kb) {
    if (kb === null || kb === undefined) return 'N/A';
    if (kb >= 1024 * 1024) return (kb / (1024 * 1024)).toFixed(2) + ' GB';
    if (kb >= 1024) return (kb / 1024).toFixed(2) + ' MB';
    return kb.toFixed(2) + ' KB';
}

function formatLatency(ms) {
    if (ms === null || ms === undefined) return 'N/A';
    if (ms >= 1000) return (ms / 1000).toFixed(2) + ' s';
    return ms.toFixed(2) + ' ms';
}

// ─── Utility: Relative Time ──────────────────────────────────────────────────
function relativeTime(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffSec < 60) return 'just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHour < 24) return `${diffHour}h ago`;
    if (diffDay < 30) return `${diffDay}d ago`;
    return date.toLocaleDateString();
}

// ─── Utility: Copy to Clipboard ──────────────────────────────────────────────
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!');
    }).catch(() => {
        // Fallback
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast('Copied to clipboard!');
    });
}

// ─── Toast Notification ──────────────────────────────────────────────────────
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} alert-dismissible`;
    toast.innerHTML = `${message} <button class="alert-close" onclick="this.parentElement.remove()">&times;</button>`;
    
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        container.style.cssText = 'position:fixed;top:80px;right:20px;z-index:9999;max-width:400px;';
        document.body.appendChild(container);
    }
    
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'slide-down 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ─── Auto-Refresh for Running Jobs ───────────────────────────────────────────
function autoRefreshWhenRunning(checkIntervalMs = 5000) {
    const runningBadges = document.querySelectorAll('.badge-running');
    if (runningBadges.length > 0) {
        setTimeout(() => location.reload(), checkIntervalMs);
    }
}

// ─── Export: Make functions globally available ────────────────────────────────
window.OpenBenchML = {
    formatNumber,
    formatSize,
    formatLatency,
    relativeTime,
    copyToClipboard,
    showToast,
    autoRefreshWhenRunning,
};
