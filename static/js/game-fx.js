/**
 * Gangs of Palestine — Phase 1 Game FX
 * Sounds, confetti, micro-interactions, animated bars, flash/URL effects.
 */
(function (global) {
    'use strict';

    var STORAGE_KEY = 'gop_sound_muted';
    var audioCtx = null;

    function prefersReducedMotion() {
        return global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    function isMuted() {
        try {
            return localStorage.getItem(STORAGE_KEY) === '1';
        } catch (e) {
            return false;
        }
    }

    function setMuted(muted) {
        try {
            localStorage.setItem(STORAGE_KEY, muted ? '1' : '0');
        } catch (e) { /* ignore */ }
        document.querySelectorAll('.gop-sound-toggle').forEach(function (el) {
            el.classList.toggle('muted', muted);
            var on = el.querySelector('.gop-sound-on');
            var off = el.querySelector('.gop-sound-off');
            if (on) on.style.display = muted ? 'none' : '';
            if (off) off.style.display = muted ? '' : 'none';
        });
    }

    function getAudioCtx() {
        if (!audioCtx) {
            var AC = global.AudioContext || global.webkitAudioContext;
            if (!AC) return null;
            audioCtx = new AC();
        }
        if (audioCtx.state === 'suspended') {
            audioCtx.resume().catch(function () {});
        }
        return audioCtx;
    }

    function playTone(freq, duration, type, gainVal, ramp) {
        if (isMuted() || prefersReducedMotion()) return;
        var ctx = getAudioCtx();
        if (!ctx) return;
        var osc = ctx.createOscillator();
        var gain = ctx.createGain();
        osc.type = type || 'sine';
        osc.frequency.setValueAtTime(freq, ctx.currentTime);
        if (ramp) {
            osc.frequency.exponentialRampToValueAtTime(ramp, ctx.currentTime + duration);
        }
        gain.gain.setValueAtTime(gainVal || 0.08, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + duration + 0.02);
    }

    function playNoise(duration, gainVal) {
        if (isMuted() || prefersReducedMotion()) return;
        var ctx = getAudioCtx();
        if (!ctx) return;
        var bufferSize = ctx.sampleRate * duration;
        var buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        var data = buffer.getChannelData(0);
        for (var i = 0; i < bufferSize; i++) {
            data[i] = (Math.random() * 2 - 1) * (1 - i / bufferSize);
        }
        var src = ctx.createBufferSource();
        src.buffer = buffer;
        var gain = ctx.createGain();
        gain.gain.setValueAtTime(gainVal || 0.06, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
        src.connect(gain);
        gain.connect(ctx.destination);
        src.start();
    }

    var sounds = {
        click: function () { playTone(520, 0.06, 'sine', 0.05); },
        cash: function () {
            playTone(880, 0.08, 'sine', 0.07);
            setTimeout(function () { playTone(1175, 0.12, 'sine', 0.06); }, 70);
            setTimeout(function () { playTone(1568, 0.14, 'sine', 0.05); }, 140);
        },
        success: function () {
            playTone(523, 0.1, 'sine', 0.06);
            setTimeout(function () { playTone(659, 0.1, 'sine', 0.06); }, 90);
            setTimeout(function () { playTone(784, 0.15, 'sine', 0.05); }, 180);
        },
        fail: function () {
            playTone(220, 0.2, 'sawtooth', 0.05, 160);
            playNoise(0.15, 0.04);
        },
        jail: function () {
            playTone(110, 0.35, 'square', 0.04);
            setTimeout(function () { playNoise(0.2, 0.05); }, 100);
        },
        combat: function () {
            playNoise(0.08, 0.12);
            playTone(180, 0.1, 'sawtooth', 0.06, 90);
        }
    };

    function ensureConfettiCanvas() {
        var c = document.getElementById('gop-confetti-canvas');
        if (c) return c;
        c = document.createElement('canvas');
        c.id = 'gop-confetti-canvas';
        document.body.appendChild(c);
        return c;
    }

    function confetti(opts) {
        if (prefersReducedMotion()) return;
        opts = opts || {};
        var count = opts.count || 60;
        var canvas = ensureConfettiCanvas();
        var ctx = canvas.getContext('2d');
        canvas.width = global.innerWidth;
        canvas.height = global.innerHeight;
        var colors = opts.colors || ['#ffd700', '#d4af37', '#28a745', '#fff8e1', '#ffc107'];
        var particles = [];
        var cx = opts.x != null ? opts.x : canvas.width / 2;
        var cy = opts.y != null ? opts.y : canvas.height * 0.35;
        for (var i = 0; i < count; i++) {
            particles.push({
                x: cx,
                y: cy,
                vx: (Math.random() - 0.5) * 14,
                vy: Math.random() * -12 - 4,
                w: Math.random() * 8 + 4,
                h: Math.random() * 6 + 3,
                color: colors[Math.floor(Math.random() * colors.length)],
                rot: Math.random() * 360,
                vr: (Math.random() - 0.5) * 12,
                life: 1
            });
        }
        var start = performance.now();
        var duration = opts.duration || 1800;
        function frame(now) {
            var elapsed = now - start;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            var alive = false;
            particles.forEach(function (p) {
                if (p.life <= 0) return;
                alive = true;
                p.x += p.vx;
                p.y += p.vy;
                p.vy += 0.35;
                p.rot += p.vr;
                p.life = 1 - elapsed / duration;
                if (p.life <= 0) return;
                ctx.save();
                ctx.translate(p.x, p.y);
                ctx.rotate(p.rot * Math.PI / 180);
                ctx.globalAlpha = Math.max(0, p.life);
                ctx.fillStyle = p.color;
                ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
                ctx.restore();
            });
            if (alive && elapsed < duration) {
                requestAnimationFrame(frame);
            } else {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
            }
        }
        requestAnimationFrame(frame);
    }

    function shake(target) {
        if (prefersReducedMotion()) return;
        var el = target || document.querySelector('.content-wrapper') || document.body;
        el.classList.remove('gop-shake');
        void el.offsetWidth;
        el.classList.add('gop-shake');
        setTimeout(function () { el.classList.remove('gop-shake'); }, 600);
    }

    function floatReward(text, opts) {
        if (prefersReducedMotion()) return;
        opts = opts || {};
        var el = document.createElement('div');
        el.className = 'gop-float-money' + (opts.negative ? ' negative' : '') + (opts.xp ? ' xp' : '');
        el.textContent = text;
        el.style.left = (opts.x != null ? opts.x : global.innerWidth / 2 - 40) + 'px';
        el.style.top = (opts.y != null ? opts.y : global.innerHeight * 0.4) + 'px';
        document.body.appendChild(el);
        setTimeout(function () { el.remove(); }, 1500);
    }

    function animateCounters(root) {
        root = root || document;
        root.querySelectorAll('[data-count-to]').forEach(function (el) {
            var target = parseFloat(el.getAttribute('data-count-to') || '0');
            var prefix = el.getAttribute('data-count-prefix') || '';
            var suffix = el.getAttribute('data-count-suffix') || '';
            var duration = parseInt(el.getAttribute('data-count-duration') || '900', 10);
            if (prefersReducedMotion()) {
                el.textContent = prefix + Math.round(target).toLocaleString() + suffix;
                return;
            }
            var start = 0;
            var startTime = null;
            function step(ts) {
                if (!startTime) startTime = ts;
                var p = Math.min(1, (ts - startTime) / duration);
                var eased = 1 - Math.pow(1 - p, 3);
                var val = Math.round(start + (target - start) * eased);
                el.textContent = prefix + val.toLocaleString() + suffix;
                if (p < 1) requestAnimationFrame(step);
            }
            requestAnimationFrame(step);
        });
    }

    function initAnimatedBars(root) {
        root = root || document;
        root.querySelectorAll('.gop-anim-bar[data-pct]').forEach(function (bar) {
            var fill = bar.querySelector('.gop-anim-bar-fill');
            if (!fill) return;
            var pct = bar.getAttribute('data-pct') || '0';
            fill.style.width = '0%';
            requestAnimationFrame(function () {
                requestAnimationFrame(function () {
                    fill.style.width = pct + '%';
                });
            });
        });
    }

    function initMicroInteractions() {
        document.querySelectorAll('.crime-card:not(.locked)').forEach(function (card) {
            card.classList.add('card-lift');
        });
        document.querySelectorAll('.balance-box').forEach(function (box) {
            box.classList.add('card-lift');
        });
        document.addEventListener('click', function (e) {
            var btn = e.target.closest('button, .btn, [type="submit"]');
            if (!btn || btn.disabled) return;
            sounds.click();
        }, true);
    }

    function initPageEnter() {
        document.body.classList.add('gop-page-enter');
        setTimeout(function () { document.body.classList.remove('gop-page-enter'); }, 400);
    }

    function parseUrlFx() {
        var params = new URLSearchParams(global.location.search);
        var fx = params.get('fx');
        var amt = parseInt(params.get('amt') || '0', 10);
        if (!fx) return;
        setTimeout(function () {
            if (fx === 'deposit' || fx === 'withdraw' || fx === 'transfer') {
                sounds.cash();
                confetti();
                if (amt > 0) floatReward('+$' + amt.toLocaleString());
                document.querySelectorAll('.bank-balance-pulse').forEach(function (el) {
                    el.classList.add('gop-reward-pop');
                });
            } else if (fx === 'escape_success') {
                sounds.success();
                confetti({ count: 80 });
            } else if (fx === 'escape_fail') {
                sounds.jail();
                shake();
            }
        }, 300);
        if (global.history && global.history.replaceState) {
            params.delete('fx');
            params.delete('amt');
            var qs = params.toString();
            var url = global.location.pathname + (qs ? '?' + qs : '') + global.location.hash;
            global.history.replaceState({}, '', url);
        }
    }

    function handleFlashMeta() {
        var el = document.getElementById('game-flash-meta');
        if (!el) return;
        var messages;
        try {
            messages = JSON.parse(el.textContent || '[]');
        } catch (e) {
            return;
        }
        if (!messages.length) return;
        setTimeout(function () {
            messages.forEach(function (pair) {
                var cat = pair[0];
                var msg = pair[1] || '';
                if (cat === 'hostess_reaction') return;
                if (cat === 'message') cat = 'info';
                if (cat === 'danger') cat = 'error';
                if (cat === 'success') {
                    sounds.success();
                    if (/إيداع|سحب|تحويل|deposit|withdraw|transfer|سرقت|انتصرت|نجحت|مبروك/i.test(msg)) {
                        confetti({ count: 45 });
                    }
                    var moneyMatch = msg.match(/[\$]?\s*([\d,]+)/);
                    if (moneyMatch) {
                        floatReward('+' + moneyMatch[1].replace(/,/g, '') + '$');
                    }
                } else if (cat === 'error') {
                    sounds.fail();
                    shake();
                } else if (cat === 'warning') {
                    sounds.jail();
                }
            });
        }, 450);
    }

    function initSoundToggle() {
        setMuted(isMuted());
        document.querySelectorAll('.gop-sound-toggle').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                setMuted(!isMuted());
            });
        });
    }

    function init() {
        initPageEnter();
        initSoundToggle();
        initMicroInteractions();
        initAnimatedBars();
        animateCounters();
        parseUrlFx();
        handleFlashMeta();
        if (document.body.getAttribute('data-game-context') === 'crime-story') {
            sounds.success();
            confetti({ count: 50 });
            animateCounters(document.querySelector('.story-wrap'));
        }
        if (document.body.getAttribute('data-game-context') === 'combat-result') {
            var win = document.body.getAttribute('data-combat-result') === 'win';
            if (win) {
                sounds.combat();
                confetti({ count: 55 });
            } else {
                sounds.fail();
                shake();
            }
        }
    }

    var GameFX = {
        sounds: sounds,
        confetti: confetti,
        shake: shake,
        floatReward: floatReward,
        animateCounters: animateCounters,
        initAnimatedBars: initAnimatedBars,
        setMuted: setMuted,
        isMuted: isMuted,
        init: init
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    global.GameFX = GameFX;
})(window);
