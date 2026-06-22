(function (global) {
    'use strict';

    function initChatRealtime(room, onMessage, onDelete) {
        if (!room || typeof onMessage !== 'function') return { stop: function () {} };
        if (typeof io === 'undefined') {
            return { stop: function () {}, mode: 'poll' };
        }

        var socket = null;
        var stopped = false;
        try {
            socket = io({ transports: ['websocket', 'polling'], reconnection: true });
        } catch (e) {
            return { stop: function () {}, mode: 'poll' };
        }

        socket.on('connect', function () {
            if (stopped) return;
            socket.emit('chat_subscribe', { room: room }, function (res) {
                if (res && res.error) {
                    console.warn('chat_subscribe:', res.error);
                }
            });
        });

        socket.on('chat_message', function (msg) {
            if (!stopped && msg && msg.id) {
                onMessage(msg);
            }
        });

        socket.on('chat_delete', function (payload) {
            if (stopped || !payload || !payload.id) return;
            if (typeof onDelete === 'function') {
                onDelete(payload.id);
            }
        });

        return {
            mode: 'socket',
            stop: function () {
                stopped = true;
                try {
                    socket.emit('chat_unsubscribe', { room: room });
                    socket.disconnect();
                } catch (e) { /* ignore */ }
            },
        };
    }

    global.GopChatRealtime = { init: initChatRealtime };
})(window);
