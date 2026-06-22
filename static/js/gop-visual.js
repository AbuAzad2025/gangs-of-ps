/**
 * Image fallbacks & light visual helpers for text-first UI.
 */
(function (global) {
    'use strict';

    var DEFAULT_FALLBACK = (document.body && document.body.dataset.gopImgFallback) || '/static/images/placeholders/scene.svg';
    var SCENE_FALLBACK = (document.body && document.body.dataset.gopSceneFallback) || DEFAULT_FALLBACK;

    function resolveFallback(el) {
        return el.getAttribute('data-gop-fallback')
            || el.getAttribute('data-fallback')
            || DEFAULT_FALLBACK;
    }

    function bindImgFallback(img) {
        if (img.dataset.gopFallbackBound) return;
        img.dataset.gopFallbackBound = '1';
        var fallback = resolveFallback(img);
        img.addEventListener('error', function onErr() {
            if (img.src.indexOf(fallback) !== -1) return;
            img.removeEventListener('error', onErr);
            img.src = fallback;
            img.classList.add('gop-img-fallback-active');
        });
    }

    function testBackground(el) {
        if (el.dataset.gopBgTested) return;
        el.dataset.gopBgTested = '1';
        var style = el.style.backgroundImage || '';
        var match = style.match(/url\(["']?([^"')]+)["']?\)/);
        if (!match || !match[1]) return;

        var probe = new Image();
        probe.onload = function () { /* ok */ };
        probe.onerror = function () {
            var fb = el.getAttribute('data-gop-bg-fallback') || SCENE_FALLBACK;
            if (fb) {
                el.style.backgroundImage = 'url("' + fb + '")';
                el.dataset.gopBgTested = '';
                testBackground(el);
                return;
            }
            el.classList.add('location-bg--fallback');
            el.style.backgroundImage = 'none';
        };
        probe.src = match[1];
    }

    function init() {
        document.querySelectorAll('img.gop-visual, img[data-gop-fallback], img.crime-image').forEach(bindImgFallback);
        document.querySelectorAll('.location-bg').forEach(testBackground);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    global.GopVisual = { init: init, bindImgFallback: bindImgFallback };
})(window);
