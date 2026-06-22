(function (global) {
    'use strict';

    function connectSocket() {
        if (typeof io === 'undefined') return null;
        try {
            return io({ transports: ['websocket', 'polling'], reconnection: true });
        } catch (e) {
            return null;
        }
    }

    function initChatRealtime(room, onMessage, onDelete) {
        if (!room || typeof onMessage !== 'function') return { stop: function () {} };
        var socket = connectSocket();
        if (!socket) return { stop: function () {}, mode: 'poll' };

        var stopped = false;
        socket.on('connect', function () {
            if (stopped) return;
            socket.emit('chat_subscribe', { room: room }, function (res) {
                if (res && res.error) console.warn('chat_subscribe:', res.error);
            });
        });

        socket.on('chat_message', function (msg) {
            if (!stopped && msg && msg.id) onMessage(msg);
        });

        socket.on('chat_delete', function (payload) {
            if (stopped || !payload || !payload.id) return;
            if (typeof onDelete === 'function') onDelete(payload.id);
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

    function initMessengerRealtime(onMessage) {
        if (typeof onMessage !== 'function') return { stop: function () {}, mode: 'poll' };
        var socket = connectSocket();
        if (!socket) return { stop: function () {}, mode: 'poll' };

        var stopped = false;
        socket.on('connect', function () {
            if (stopped) return;
            socket.emit('messenger_subscribe', {}, function (res) {
                if (res && res.error) console.warn('messenger_subscribe:', res.error);
            });
        });

        socket.on('messenger_message', function (msg) {
            if (!stopped && msg && msg.id) onMessage(msg);
        });

        return {
            mode: 'socket',
            stop: function () {
                stopped = true;
                try {
                    socket.emit('messenger_unsubscribe', {});
                    socket.disconnect();
                } catch (e) { /* ignore */ }
            },
        };
    }

    function initGangChatRealtime(gangId, onMessage, onDelete) {
        if (!gangId || typeof onMessage !== 'function') return { stop: function () {}, mode: 'poll' };
        var socket = connectSocket();
        if (!socket) return { stop: function () {}, mode: 'poll' };

        var stopped = false;
        socket.on('connect', function () {
            if (stopped) return;
            socket.emit('gang_chat_subscribe', { gang_id: gangId }, function (res) {
                if (res && res.error) console.warn('gang_chat_subscribe:', res.error);
            });
        });

        socket.on('gang_chat_message', function (msg) {
            if (!stopped && msg && msg.id) onMessage(msg);
        });

        socket.on('gang_chat_delete', function (payload) {
            if (stopped || !payload || !payload.id) return;
            if (typeof onDelete === 'function') onDelete(payload.id);
        });

        return {
            mode: 'socket',
            stop: function () {
                stopped = true;
                try {
                    socket.emit('gang_chat_unsubscribe', { gang_id: gangId });
                    socket.disconnect();
                } catch (e) { /* ignore */ }
            },
        };
    }

    global.GopChatRealtime = {
        init: initChatRealtime,
        initMessenger: initMessengerRealtime,
        initGang: initGangChatRealtime,
    };
})(window);
