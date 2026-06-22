(function (global) {
    'use strict';

    function requestNotificationPermission() {
        if (!('Notification' in global)) return Promise.resolve('unsupported');
        if (Notification.permission === 'granted') return Promise.resolve('granted');
        if (Notification.permission === 'denied') return Promise.resolve('denied');
        return Notification.requestPermission();
    }

    function showLocalNotification(title, body, url) {
        if (!('Notification' in global) || Notification.permission !== 'granted') return;
        var n = new Notification(title, {
            body: body,
            icon: '/static/images/azad_logo_white_on_dark.png',
            badge: '/static/images/azad_logo_white_on_dark.png',
            tag: 'gop-reminder',
        });
        if (url) {
            n.onclick = function () {
                global.focus();
                global.location.href = url;
                n.close();
            };
        }
        if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
            navigator.serviceWorker.ready.then(function (reg) {
                if (reg.showNotification) {
                    reg.showNotification(title, {
                        body: body,
                        icon: '/static/images/azad_logo_white_on_dark.png',
                        data: { url: url || '/' },
                        tag: 'gop-reminder',
                    });
                }
            }).catch(function () {});
        }
    }

    function initPwaPrompt() {
        var btn = document.getElementById('gop-enable-notifications');
        if (!btn) return;
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            requestNotificationPermission().then(function (p) {
                if (p === 'granted') {
                    showLocalNotification(
                        btn.getAttribute('data-title') || 'Gangs of Palestine',
                        btn.getAttribute('data-body') || '',
                        btn.getAttribute('data-url') || '/'
                    );
                }
            });
        });
    }

    function initEnergyReminder() {
        var el = document.getElementById('user-energy');
        if (!el || !('Notification' in global)) return;
        var energy = parseInt(el.textContent || '0', 10);
        var maxAttr = document.body.getAttribute('data-max-energy');
        var max = parseInt(maxAttr || '100', 10);
        if (energy >= max && Notification.permission === 'granted') {
            try {
                var key = 'gop_energy_full_' + (document.body.getAttribute('data-user-id') || '0');
                var last = localStorage.getItem(key);
                var today = new Date().toISOString().slice(0, 10);
                if (last !== today) {
                    showLocalNotification(
                        document.body.getAttribute('data-energy-title') || 'Energy full',
                        document.body.getAttribute('data-energy-body') || '',
                        '/crimes'
                    );
                    localStorage.setItem(key, today);
                }
            } catch (e) { /* ignore */ }
        }
    }

    global.GopPwa = {
        requestNotificationPermission: requestNotificationPermission,
        showLocalNotification: showLocalNotification,
        init: function () {
            initPwaPrompt();
            initEnergyReminder();
        },
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { GopPwa.init(); });
    } else {
        GopPwa.init();
    }
})(window);
