/**
 * OpenBenchML - Main JavaScript
 * ===============================
 * Minimal, progressive-enhancement utilities for the platform.
 *
 * Per the project's design policy: vanilla JS is only used for tiny
 * progressive enhancements that degrade gracefully.  All interactive
 * pages (forms, leaderboards, datasets, competitions) work fully
 * server-side without this file.  Heavy client-side logic lives only
 * in /notebook and /terminal (which require a JS runtime by design).
 */

document.addEventListener('DOMContentLoaded', () => {
    initMobileNav();
    initAlertDismiss();
    initConfirmDialogs();
});

// ─── Mobile Navigation Toggle ────────────────────────────────────────────────
// The only piece of "vanilla JS" needed across every page — the mobile
// navbar hamburger toggle.  Falls back to a permanently-expanded navbar
// on browsers without JS (acceptable degradation).
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
// Auto-dismiss flash messages after 5 seconds.  Purely cosmetic —
// without JS the messages just stay visible until the next page load.
function initAlertDismiss() {
    document.querySelectorAll('.alert-dismissible .alert-close').forEach(btn => {
        btn.addEventListener('click', () => {
            const alert = btn.closest('.alert');
            if (alert) alert.remove();
        });
    });

    document.querySelectorAll('.alert-dismissible').forEach(alert => {
        setTimeout(() => {
            if (alert.parentNode) alert.remove();
        }, 5000);
    });
}

// ─── Confirm Dialogs ─────────────────────────────────────────────────────────
// Adds a "Are you sure?" prompt to any element with data-confirm.
// Without JS the action proceeds without confirmation (server-side
// validation still applies).
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

// ─── Utility: Format Numbers ─────────────────────────────────────────────────
// Used by a few inline templates.  Safe to call from anywhere.
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

// ─── Export: Make functions globally available ────────────────────────────────
window.OpenBenchML = {
    formatNumber,
    formatSize,
    formatLatency,
};
