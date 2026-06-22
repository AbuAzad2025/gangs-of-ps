(function (global) {
    'use strict';

    function escapeHtml(text) {
        var map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return String(text || '').replace(/[&<>"']/g, function (m) { return map[m]; });
    }

    function getCsrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.getAttribute('content') || '';
        var input = document.querySelector('input[name="csrf_token"]');
        return input ? input.value : '';
    }

    function scrollAssistantToBottom() {
        var body = document.getElementById('gop-assistant-messages');
        if (body) body.scrollTop = body.scrollHeight;
    }

    function toggleHostessChat(forceOpen) {
        var widget = document.getElementById('gop-assistant-widget');
        if (!widget) return;
        var display = widget.style.display || (window.getComputedStyle ? window.getComputedStyle(widget).display : '');
        var open = forceOpen === true || display === 'none';
        if (open) {
            widget.style.display = 'flex';
            widget.style.opacity = '0';
            widget.style.transform = 'scale(0.9) translateY(20px)';
            setTimeout(function () {
                widget.style.opacity = '1';
                widget.style.transform = 'scale(1) translateY(0)';
            }, 10);
            setTimeout(function () {
                var input = document.getElementById('gop-assistant-input');
                if (input) input.focus();
            }, 300);
        } else {
            widget.style.opacity = '0';
            widget.style.transform = 'scale(0.9) translateY(20px)';
            setTimeout(function () { widget.style.display = 'none'; }, 300);
        }
    }

    function getAvatarHtml() {
        var tpl = document.getElementById('gop-assistant-avatar-tpl');
        return tpl ? tpl.innerHTML : '';
    }

    function appendMessage(role, text, typingId) {
        var chatBody = document.getElementById('gop-assistant-messages');
        if (!chatBody) return null;
        var avatarHtml = getAvatarHtml();
        var row = document.createElement('div');
        if (typingId) row.id = typingId;
        if (role === 'user') {
            row.className = 'message sent mb-3 fade-in text-right';
            row.innerHTML = '<div class="p-3 text-white shadow-sm d-inline-block text-left hostess-msg-bubble-sent">' +
                escapeHtml(text) + '</div>';
        } else {
            row.className = 'message received mb-3 fade-in';
            var body = String(text || '');
            if (body.indexOf('typing-dots') < 0) {
                body = escapeHtml(body).replace(/\n/g, '<br>');
            }
            row.innerHTML = '<div class="d-flex align-items-end">' + avatarHtml +
                '<div class="bg-dark border border-secondary p-3 text-white shadow-sm hostess-msg-bubble-received">' +
                body + '</div></div>';
        }
        chatBody.appendChild(row);
        scrollAssistantToBottom();
        return row;
    }

    async function sendAssistantMessage() {
        var input = document.getElementById('gop-assistant-input');
        if (!input) return;
        var message = input.value.trim();
        if (!message) return;

        var root = document.getElementById('gop-assistant-root');
        var apiUrl = (root && root.getAttribute('data-api-url')) || '/api/assistant/chat';
        var hostessId = (root && root.getAttribute('data-hostess-id')) || '';

        appendMessage('user', message);
        input.value = '';

        var typingId = 'gop-typing-' + Date.now();
        appendMessage('assistant', '<div class="typing-dots"><span></span><span></span><span></span></div>', typingId);

        try {
            var response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                body: JSON.stringify({
                    message: message,
                    hostess_id: hostessId ? parseInt(hostessId, 10) : undefined,
                }),
            });
            var data = null;
            try { data = await response.json(); } catch (e) { data = null; }
            var typingEl = document.getElementById(typingId);
            if (typingEl) typingEl.remove();

            if (response.ok && data && data.response) {
                appendMessage('assistant', data.response);
            } else {
                appendMessage('assistant', (data && data.error) ? data.error : ('Error ' + response.status));
            }
        } catch (err) {
            var el = document.getElementById(typingId);
            if (el) el.remove();
            appendMessage('assistant', 'Network Error');
        }
    }

    function bindAssistantWidget() {
        var root = document.getElementById('gop-assistant-root');
        if (!root || root.getAttribute('data-bound') === '1') return;
        root.setAttribute('data-bound', '1');

        var input = document.getElementById('gop-assistant-input');
        if (input) {
            input.addEventListener('keypress', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    sendAssistantMessage();
                }
            });
        }
        var sendBtn = document.getElementById('gop-assistant-send');
        if (sendBtn) sendBtn.addEventListener('click', function (e) {
            e.preventDefault();
            sendAssistantMessage();
        });
        document.querySelectorAll('[data-gop-assistant-toggle]').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                toggleHostessChat();
            });
        });
        document.querySelectorAll('[data-gop-assistant-prompt]').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                var input = document.getElementById('gop-assistant-input');
                var prompt = btn.getAttribute('data-gop-assistant-prompt') || '';
                if (input && prompt) {
                    toggleHostessChat(true);
                    input.value = prompt;
                    sendAssistantMessage();
                }
            });
        });
    }

    global.GopAssistant = {
        open: function () { toggleHostessChat(true); },
        close: function () { toggleHostessChat(false); },
        toggle: toggleHostessChat,
        send: sendAssistantMessage,
    };
    global.toggleHostessChat = toggleHostessChat;
    global.sendPublicMessage = sendAssistantMessage;
    global.handleEnter = function (e) {
        if (e.key === 'Enter') sendAssistantMessage();
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindAssistantWidget);
    } else {
        bindAssistantWidget();
    }
})(window);
