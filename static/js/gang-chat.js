(function ($, global) {
    'use strict';

    function initGangChat(cfg) {
        if (!cfg || !cfg.gangId) return;

        var chatBox = $(cfg.boxSelector || '#gang-chat-box');
        var chatForm = $(cfg.formSelector || '#gang-chat-form');
        var chatInput = $(cfg.inputSelector || '#gang-chat-input');
        var avatarBase = cfg.avatarBase || '/static/images/avatars/';
        var lastChatId = 0;
        var isChatTabActive = false;
        var pollId = null;
        var socketMode = false;
        var escapeHtml = (global.GopChatUtils && global.GopChatUtils.escapeHtml) || function (t) { return t; };

        function scrollToBottom() {
            if (chatBox.length) chatBox.scrollTop(chatBox[0].scrollHeight);
        }

        function appendMessage(msg) {
            if (!msg || !msg.id) return;
            if (chatBox.find('[data-msg-id="' + msg.id + '"]').length) return;

            var isMe = parseInt(msg.user_id, 10) === parseInt(cfg.userId, 10);
            var deleteBtn = '';
            if (cfg.canModerate || isMe) {
                deleteBtn = '<button type="button" class="gop-chat-delete delete-gang-msg" data-id="' + msg.id + '" title="' + escapeHtml(cfg.labels.delete || '') + '"><i class="fas fa-times"></i></button>';
            }

            var html = ''
                + '<div class="gop-chat-row' + (isMe ? ' gop-chat-row--me' : '') + '" data-msg-id="' + msg.id + '">'
                + '  <img class="gop-chat-avatar" src="' + avatarBase + escapeHtml(msg.avatar || 'default.png') + '" alt="" onerror="this.src=\'https://ui-avatars.com/api/?name=' + encodeURIComponent(msg.username || '') + '&background=random\';">'
                + '  <div class="gop-chat-bubble-wrap">'
                + '    <div class="gop-chat-meta"><span class="gop-chat-name">' + escapeHtml(msg.username || '') + '</span><span class="gop-chat-time">' + escapeHtml(msg.created_at || '') + '</span></div>'
                + '    <div class="gop-chat-bubble ' + (isMe ? 'gop-chat-bubble--sent' : 'gop-chat-bubble--received') + '">'
                + escapeHtml(msg.message || '') + deleteBtn
                + '    </div>'
                + '  </div>'
                + '</div>';
            chatBox.append(html);
            lastChatId = Math.max(lastChatId, parseInt(msg.id, 10) || 0);
        }

        function loadGangMessages() {
            if (!isChatTabActive && lastChatId > 0) return;
            $.ajax({
                url: cfg.messagesUrl,
                data: { since_id: lastChatId },
                success: function (messages) {
                    if (!messages || !messages.length) {
                        if (lastChatId === 0) {
                            chatBox.html('<div class="text-center text-muted mt-5">' + escapeHtml(cfg.labels.empty || '') + '</div>');
                        }
                        return;
                    }
                    if (lastChatId === 0) chatBox.empty();
                    messages.forEach(appendMessage);
                    scrollToBottom();
                }
            });
        }

        function startPoll() {
            stopPoll();
            if (!isChatTabActive || document.hidden) return;
            pollId = setInterval(loadGangMessages, socketMode ? 15000 : 4000);
        }

        function stopPoll() {
            if (pollId) { clearInterval(pollId); pollId = null; }
        }

        var realtime = null;
        if (global.GopChatRealtime && global.GopChatRealtime.initGang) {
            realtime = global.GopChatRealtime.initGang(cfg.gangId, function (msg) {
                if (lastChatId === 0) chatBox.empty();
                appendMessage(msg);
                scrollToBottom();
            }, function (msgId) {
                chatBox.find('[data-msg-id="' + msgId + '"]').fadeOut(200, function () { $(this).remove(); });
            });
            socketMode = realtime && realtime.mode === 'socket';
        }

        $('a[data-toggle="tab"]').on('shown.bs.tab', function (e) {
            if ($(e.target).attr('href') === '#chat') {
                isChatTabActive = true;
                scrollToBottom();
                loadGangMessages();
                startPoll();
            } else {
                isChatTabActive = false;
                stopPoll();
            }
        });

        document.addEventListener('visibilitychange', function () {
            if (document.hidden) stopPoll();
            else if (isChatTabActive) startPoll();
        });

        chatForm.on('submit', function (e) {
            e.preventDefault();
            var msg = chatInput.val().trim();
            if (!msg) return;
            $.ajax({
                url: cfg.sendUrl,
                method: 'POST',
                data: { content: msg, csrf_token: cfg.csrfToken },
                success: function (response) {
                    chatInput.val('');
                    if (lastChatId === 0) chatBox.empty();
                    appendMessage(response);
                    scrollToBottom();
                },
                error: function (xhr) {
                    var err = (xhr.responseJSON && xhr.responseJSON.error) ? xhr.responseJSON.error : 'Error';
                    if (global.toastr) toastr.error(err);
                }
            });
        });

        $(document).on('click', '.delete-gang-msg', function (e) {
            e.preventDefault();
            if (!confirm(cfg.labels.confirmDelete || 'Delete?')) return;
            var msgId = $(this).data('id');
            $.ajax({
                url: cfg.deleteUrlBase + msgId,
                method: 'POST',
                data: { csrf_token: cfg.csrfToken },
                success: function () {
                    chatBox.find('[data-msg-id="' + msgId + '"]').fadeOut(200, function () { $(this).remove(); });
                },
                error: function () {
                    if (global.toastr) toastr.error(cfg.labels.deleteFailed || 'Failed');
                }
            });
        });

        if ($('.nav-link.active[href="#chat"]').length) {
            isChatTabActive = true;
            loadGangMessages();
            startPoll();
        }
    }

    global.GopGangChat = { init: initGangChat };
})(jQuery, window);
