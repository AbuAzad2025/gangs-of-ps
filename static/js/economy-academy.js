(function (global) {
    'use strict';

    var STORAGE_PREFIX = 'gop_academy_tip_';

    function userKey() {
        var el = document.body.getAttribute('data-user-id');
        return el ? String(el) : '0';
    }

    function shouldShowTip(lessonId) {
        try {
            return localStorage.getItem(STORAGE_PREFIX + userKey() + '_' + lessonId) !== '1';
        } catch (e) {
            return true;
        }
    }

    function dismissTip(lessonId) {
        try {
            localStorage.setItem(STORAGE_PREFIX + userKey() + '_' + lessonId, '1');
        } catch (e) { /* ignore */ }
    }

    function showLessonModal(cfg) {
        if (!cfg || !cfg.id || !shouldShowTip(cfg.id)) return;
        if (typeof Swal === 'undefined') return;

        Swal.fire({
            title: cfg.title || '',
            html: '<p class="text-left mb-2">' + (cfg.body || '') + '</p>'
                + (cfg.tip ? '<div class="alert alert-dark border border-warning text-warning text-left small mb-0"><i class="fas fa-lightbulb mr-1"></i> ' + cfg.tip + '</div>' : ''),
            icon: 'info',
            showCancelButton: !!cfg.tryUrl,
            confirmButtonText: cfg.tryLabel || 'حسناً',
            cancelButtonText: 'لاحقاً',
            background: 'rgba(20,20,20,0.97)',
            color: '#fff',
            confirmButtonColor: '#d4af37',
        }).then(function (result) {
            dismissTip(cfg.id);
            if (result.isConfirmed && cfg.tryUrl) {
                global.location.href = cfg.tryUrl;
            }
        });
    }

    function initFeeSimulator(root) {
        root = root || document;
        var box = root.querySelector('[data-fee-simulator]');
        if (!box) return;

        var input = box.querySelector('[data-fee-input]');
        var out = box.querySelector('[data-fee-output]');
        var reason = box.querySelector('[data-fee-reason]');
        var url = box.getAttribute('data-fee-url');
        if (!input || !out || !url) return;

        var timer;
        function update() {
            clearTimeout(timer);
            timer = setTimeout(function () {
                var val = parseInt(input.value || '0', 10);
                if (isNaN(val) || val < 0) val = 0;
                fetch(url + '?amount=' + encodeURIComponent(val), {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                })
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        out.textContent = (data.fee || 0).toLocaleString() + '$';
                        if (reason) reason.textContent = data.reason || '';
                    })
                    .catch(function () {});
            }, 280);
        }

        input.addEventListener('input', update);
        update();
    }

    function initPageTips() {
        var tipEl = document.getElementById('economy-lesson-tip-data');
        if (!tipEl) return;
        var cfg;
        try {
            cfg = JSON.parse(tipEl.textContent || '{}');
        } catch (e) {
            return;
        }
        if (!cfg.id) return;
        setTimeout(function () { showLessonModal(cfg); }, 600);
    }

    function init() {
        initFeeSimulator();
        initPageTips();
    }

    global.EconomyAcademy = {
        showLessonModal: showLessonModal,
        initFeeSimulator: initFeeSimulator,
        init: init
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(window);
