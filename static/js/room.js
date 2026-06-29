/* ==========================================================================
   1. 変数定義と初期設定
   ========================================================================== */
const currentUser = document.getElementById('current-user').textContent.trim();
let selectedParentId = null;

// ログイン状態の判定
const isLoggedIn = (currentUser !== "" && currentUser !== "ゲスト");

// ユーザーが開いているスレッドの親メッセージIDを記録しておく部屋
const openThreadIds = new Set();

// すでに画面に表示したメッセージのIDを記録しておく部屋
const renderedMessageIds = new Set();


/* ==========================================================================
   2. ファイル添付・コントロール処理
   ========================================================================== */
// クリップボタンを押した時に画像か動画か選ばせる処理
function triggerFileInput() {
    const choice = prompt("添付するファイルの種類を選んでください:\n1: 画像（写真・イラスト）\n2: 動画", "1");
    if (choice === "1") {
        document.getElementById('image-input').click();
    } else if (choice === "2") {
        document.getElementById('video-input').click();
    }
}

// クリップボタンを緑チェックに変える処理を追加
function fileChanged() {
    const imgInput = document.getElementById('image-input');
    const vidInput = document.getElementById('video-input');
    const clipBtn = document.getElementById('clip-btn'); // 追加

    if (imgInput.files.length > 0 || vidInput.files.length > 0) {
        document.getElementById('message-input').required = false;
        
        // クリップマークを緑のチェックマークに変更
        if (clipBtn) {
            clipBtn.innerHTML = "✅"; 
            clipBtn.style.color = "#22c55e"; // 綺麗な黄緑色
        }
    } else {
        resetFiles();
    }
}

function resetFiles() {
    document.getElementById('image-input').value = "";
    document.getElementById('video-input').value = "";
    document.getElementById('message-input').required = true;
    
    // クリップマークを元に戻す
    const clipBtn = document.getElementById('clip-btn');
    if (clipBtn) {
        clipBtn.innerHTML = "📎";
        clipBtn.style.color = ""; // スタイル消去
    }
}

/* ==========================================================================
   3. メッセージデータの取得とスレッド生成
   ========================================================================== */
function fetchMessages() {
    fetch('/get_messages')
        .then(res => res.json())
        .then(data => {
            // サーバーから返される辞書データから、メッセージ配列と未読通知数を分解して取得
            // 辞書型（オブジェクト形式）への移行に伴うエラーを完全に防ぎます
            const messages = data.messages || [];
            const unreadCount = data.unread_count || 0;

            // 画面上のベルマークの通知バッジ（数字）をリアルタイムに書き換える処理
            const badge = document.getElementById('noti-badge');
            if (badge) {
                badge.textContent = unreadCount;
            }

            const chatBox = document.getElementById('chat-box');
            const isAtBottom = chatBox.scrollHeight - chatBox.clientHeight <= chatBox.scrollTop + 60;
            
            const rootMessages = [];
            const replyMap = {};
            
            messages.forEach(m => {
                if (!m.parent_id) {
                    rootMessages.push(m);
                } else {
                    if (!replyMap[m.parent_id]) replyMap[m.parent_id] = [];
                    replyMap[m.parent_id].push(m);
                }
            });
            
            function buildTree(targetElement, messageList, isReply) {
                messageList.forEach(m => {
                    if (!renderedMessageIds.has(m.id)) {
                        renderMessage(targetElement, m, isReply);
                        renderedMessageIds.add(m.id);
                    } else {
                        updateReactionsAndText(m);
                    }

                    if (replyMap[m.id] && replyMap[m.id].length > 0) {
                        const myWrapper = document.getElementById('msg-wrapper-' + m.id);
                        if (myWrapper) {
                            let toggleBtn = myWrapper.querySelector('.thread-toggle-btn');
                            if (!toggleBtn) {
                                toggleBtn = document.createElement('button');
                                toggleBtn.className = 'thread-toggle-btn';
                                toggleBtn.onclick = () => toggleThread(m.id);
                                const mainContainer = document.getElementById('msg-id-' + m.id);
                                mainContainer.after(toggleBtn);
                            }
                            
                            const replyCount = replyMap[m.id].length;
                            let rArea = myWrapper.querySelector('.reply-box');
                            
                            if (openThreadIds.has(m.id)) {
                                toggleBtn.innerHTML = `▲ 返信を折りたたむ (${replyCount}件)`;
                                if (!rArea) {
                                    rArea = document.createElement('div');
                                    rArea.className = 'reply-box';
                                    myWrapper.appendChild(rArea);
                                }
                                rArea.style.display = 'flex';
                                buildTree(rArea, replyMap[m.id], true);
                            } else {
                                toggleBtn.innerHTML = `▶ 返信を表示する (${replyCount}件)`;
                                if (rArea) {
                                    rArea.style.display = 'none';
                                }
                            }
                        }
                    }
                });
            }
            
            buildTree(chatBox, rootMessages, false);
            if (isAtBottom) { chatBox.scrollTop = chatBox.scrollHeight; }

            // URLの末尾に特定のメッセージID（#msg-id-xx）が指定されている場合、その場所へ自動スクロールする処理
            const hash = window.location.hash;
            if (hash && hash.startsWith('#msg-id-')) {
                // 画面上に該当のメッセージ要素が出現するまでわずかに待ってから実行
                setTimeout(() => {
                    const targetMessage = document.querySelector(hash);
                    if (targetMessage) {
                        // 対象のメッセージ枠までスムーズにスクロールさせる
                        targetMessage.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        
                        // ジャンプしたメッセージを目立たせるために、一瞬だけ背景を黄色く光らせる演出（お好みで）
                        targetMessage.style.backgroundColor = '#fef08a';
                        setTimeout(() => {
                            targetMessage.style.backgroundColor = ''; // 元に戻す
                        }, 2000);
                    }
                }, 300);
            }
        });
}

// ボタンクリックで開閉状態を切り替える関数
function toggleThread(parentId) {
    const chatBox = document.getElementById('chat-box');
    const isAtBottom = chatBox.scrollHeight - chatBox.clientHeight <= chatBox.scrollTop + 60;

    if (openThreadIds.has(parentId)) {
        openThreadIds.delete(parentId); // 閉じる
        // 閉じられたスレッドの中にある子・孫メッセージのIDは、再描画のために記録から一旦消去する
        const myWrapper = document.getElementById('msg-wrapper-' + parentId);
        if (myWrapper) {
            const rArea = myWrapper.querySelector('.reply-box');
            if (rArea) {
                // 返信箱の中にあるすべてのIDを renderedMessageIds から削除
                const innerContainers = rArea.querySelectorAll('[id^="msg-id-"]');
                innerContainers.forEach(el => {
                    const cid = el.id.replace('msg-id-', '');
                    renderedMessageIds.delete(parseInt(cid));
                    renderedMessageIds.delete(cid);
                    const wId = 'msg-wrapper-' + cid;
                    const innerWrapper = document.getElementById(wId);
                    if (innerWrapper) innerWrapper.remove();
                });
                rArea.remove(); // 返信エリア自体を一旦消去
            }
        }
    } else {
        openThreadIds.add(parentId); // 開く
    }
    fetchMessages(); // 画面を再同期
    if (isAtBottom) { chatBox.scrollTop = chatBox.scrollHeight; }
}
/* ==========================================================================
   4. DOM描画・メッセージ更新処理
   ========================================================================== */
// メッセージをリロードさせず、リアクションと編集文字だけを反映する関数
function updateReactionsAndText(m) {
    const container = document.getElementById('msg-id-' + m.id);
    if (!container) return;
    
    const txtDiv = container.querySelector('.msg-text');
    if (txtDiv && txtDiv.firstChild && txtDiv.firstChild.nodeType === Node.TEXT_NODE && txtDiv.firstChild.textContent !== m.text) {
        txtDiv.firstChild.textContent = m.text;
    }

    const rBar = container.querySelector('.reaction-bar');
    if (rBar) {
        const r = m.reactions || {};
        let newHTML = '';
        
        if (r.confirm > 0) newHTML += `<button class="react-btn" onclick="sendReaction(${m.id}, 'confirm')">👍 ${r.confirm}</button>`;
        if (r.agree > 0) newHTML += `<button class="react-btn" onclick="sendReaction(${m.id}, 'agree')">❤️ ${r.agree}</button>`;
        if (r.review > 0) newHTML += `<button class="react-btn" onclick="sendReaction(${m.id}, 'review')">😂 ${r.review}</button>`;
        if (r.review2 > 0) newHTML += `<button class="react-btn" onclick="sendReaction(${m.id}, 'review2')">😮 ${r.review2}</button>`;
        if (r.review3 > 0) newHTML += `<button class="react-btn" onclick="sendReaction(${m.id}, 'review3')">💪 ${r.review3}</button>`;
        
        if (rBar.innerHTML !== newHTML) {
            rBar.innerHTML = newHTML;
        }
    }
}

// 【修正】 room.js の renderMessage 関数
function renderMessage(targetEl, data, isReply) {
    const currentUserEl = document.getElementById('current-user');
    const currentHeaderName = currentUserEl ? currentUserEl.innerText.trim() : "";
    
    // ⭕ 【重要】HTMLからログインユーザーのIDを取得
    const currentUserId = currentUserEl ? parseInt(currentUserEl.getAttribute('data-user-id')) : null;
    
    // ⭕ 【重要】ID同士を比較して「あなた」か「他人」かを完璧に判定する
    const isMe = (currentUserId && data.user_id && currentUserId === parseInt(data.user_id));
    
    // 画面の表示名をニックネーム等に合わせる処理
    if (isMe) {
        data.username = currentHeaderName;
    }
    
    const wrapper = document.createElement('div');
    wrapper.id = 'msg-wrapper-' + data.id;
    wrapper.className = 'msg-wrapper'; 
    
    const container = document.createElement('div');
    container.id = 'msg-id-' + data.id;
    container.className = 'msg-container'; 

    const header = document.createElement('div');
    header.className = 'msg-header-info';
    
    const meBadge = isMe ? ' <span style="color:#2563eb; font-size:10px;">(あなた)</span>' : '';

    const avatarHtml = (data.icon_url && data.icon_url.trim() !== "") 
        ? `<img src="${data.icon_url}" class="msg-avatar" alt="アイコン">` 
        : `<div class="msg-avatar-default">👤</div>`;

    header.innerHTML = `
        <div class="msg-avatar-container">${avatarHtml}</div>
        <span class="msg-username" onclick="location.href='/profile/${data.user_id}/'" style="cursor: pointer; color: #1e3a8a;" onmouseover="this.style.textDecoration='underline'" onmouseout="this.style.textDecoration='none'">
            ${data.username}${meBadge}
        </span>
        <span class="msg-time">${data.time}</span>
    `;
    
    // 削除フラグが True だった場合の表示
    if (data.is_deleted) {
        container.appendChild(header);
        const contentBlock = document.createElement('div');
        const txt = document.createElement('div');
        txt.className = 'msg-text';
        txt.style.color = '#94a3b8';
        txt.style.fontStyle = 'italic';
        txt.textContent = data.text;
        
        contentBlock.appendChild(txt);
        container.appendChild(contentBlock);
        wrapper.appendChild(container);
        targetEl.appendChild(wrapper);
        return; 
    }
    
    // ボタンの出し分け処理
    if (isLoggedIn) {
        if (isMe) {
            // [編集] ボタン
            const edit = document.createElement('span');
            edit.className = 'action-link';
            edit.textContent = '[編集]';
            edit.onclick = () => triggerEdit(data.id, data.text);
            header.appendChild(edit);

            // [削除] ボタン
            const delLink = document.createElement('span');
            delLink.className = 'action-link';
            delLink.style.color = '#ef4444'; 
            delLink.textContent = '[削除]';
            delLink.onclick = () => triggerDelete(data.id); 
            header.appendChild(delLink);
        }
        
        const addReactLink = document.createElement('span');
        addReactLink.className = 'action-link';
        addReactLink.textContent = '[リアクション]';
        addReactLink.onclick = () => {
            const type = prompt("リアクションを選択:\n1:👍  2:❤️  3:😂  4:😮  5:💪", "1");
            if (type === "1") sendReaction(data.id, 'confirm');
            if (type === "2") sendReaction(data.id, 'agree');
            if (type === "3") sendReaction(data.id, 'review');
            if (type === "4") sendReaction(data.id, 'review2');
            if (type === "5") sendReaction(data.id, 'review3');
        };
        header.appendChild(addReactLink);

        const rep = document.createElement('span');
        rep.className = 'action-link';
        rep.textContent = '[スレッドへ返信]';
        rep.onclick = () => { 
            selectedParentId = data.id; 
            document.getElementById('reply-user').textContent = data.username; 
            document.getElementById('reply-target-banner').style.display = 'flex'; 
            document.getElementById('message-input').focus(); 
        };
        header.appendChild(rep);
    }
    
    const contentBlock = document.createElement('div');
    contentBlock.style.display = 'flex';
    contentBlock.style.flexDirection = 'column';
    contentBlock.style.gap = '6px';

    const txt = document.createElement('div');
    txt.className = 'msg-text';
    txt.textContent = data.text;
    
    if (isReply && isMe) {
        txt.style.backgroundColor = '#e0f2fe';
    }
    
    if (data.text && data.text.trim() !== "") {
        contentBlock.appendChild(txt);
    }
    
    // 【ファイルアップロードの画像表示】
    if (data.image_url) {
        const imgTag = document.createElement('img');
        imgTag.src = data.image_url;
        imgTag.className = 'msg-media';
        imgTag.onclick = () => window.open(data.image_url, '_blank');
        contentBlock.appendChild(imgTag);
    }

    // 【ファイルアップロードの動画表示】
    if (data.video_url) {
        const videoTag = document.createElement('video');
        videoTag.src = data.video_url;
        videoTag.className = 'msg-media';
        videoTag.controls = true;
        contentBlock.appendChild(videoTag);
    }

        // ==========================================================================
    // 【最終解決版】YouTubeリンクの自動検知・埋め込みプレイヤー処理
    // ==========================================================================
    if (data.text) {
        const words = data.text.split(/\s+/);
        
        words.forEach(function(word) {
            if (word.includes('youtu')) {
                let videoId = null;

                // 1. 通常のPC用URL (watch?v=...) の場合
                if (word.includes('v=')) {
                    const match = word.match(/v=([a-zA-Z0-9_-]{11})/);
                    if (match && match[1]) {
                        videoId = match[1];
                    }
                } 
                // 2. スマホ用短縮URL (youtu.be/...) の場合
                else if (word.includes('youtu.be/')) {
                    const match = word.match(/youtu\.be\/([a-zA-Z0-9_-]{11})/);
                    if (match && match[1]) {
                        videoId = match[1];
                    }
                }

                // 動画IDが正しく11文字で取得できていればプレイヤーを生成
                if (videoId && videoId.length === 11) { 
                    const correctEmbedUrl = "https://www.youtube.com/embed/" + videoId; 
                    
                    const iframeTag = document.createElement('iframe');
                    iframeTag.setAttribute('src', correctEmbedUrl); 
                    iframeTag.src = correctEmbedUrl; 
                    iframeTag.className = 'msg-embed-video';
                    
                    // ⭕【最重要】エラー153を回避するためのリファラーポリシーを追加
                    iframeTag.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
                    
                    // デザインとサイズ調整
                    iframeTag.style.width = "100%";
                    iframeTag.style.maxWidth = "480px";
                    iframeTag.style.height = "270px";
                    iframeTag.style.border = "none";
                    iframeTag.style.borderRadius = "8px";
                    
                    iframeTag.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
                    iframeTag.allowFullscreen = true;
                    
                    contentBlock.appendChild(iframeTag);
                }
            }
        });
    }




    const rBar = document.createElement('div');
    rBar.className = 'reaction-bar';
    const r = data.reactions || {};
    
    if (r.confirm > 0) rBar.innerHTML += `<button class="react-btn" onclick="sendReaction(${data.id}, 'confirm')">👍 ${r.confirm}</button>`;
    if (r.agree > 0) rBar.innerHTML += `<button class="react-btn" onclick="sendReaction(${data.id}, 'agree')">❤️ ${r.agree}</button>`;
    if (r.review > 0) rBar.innerHTML += `<button class="react-btn" onclick="sendReaction(${data.id}, 'review')">😂 ${r.review}</button>`;
    if (r.review2 > 0) rBar.innerHTML += `<button class="react-btn" onclick="sendReaction(${data.id}, 'review2')">😮 ${r.review2}</button>`;
    if (r.review3 > 0) rBar.innerHTML += `<button class="react-btn" onclick="sendReaction(${data.id}, 'review3')">💪 ${r.review3}</button>`;
    
    container.appendChild(header);
    container.appendChild(contentBlock);
    container.appendChild(rBar);
    
    wrapper.appendChild(container);
    targetEl.appendChild(wrapper);
}

/* ==========================================================================
   5. 通信処理 (POST送信・編集・リアクション)
   ========================================================================== */
function cancelReply() { 
    selectedParentId = null; 
    document.getElementById('reply-target-banner').style.display = 'none'; 
}

function triggerEdit(msgId, oldText) {
    const newText = prompt("メッセージを編集してください:", oldText);
    if (newText !== null && newText.trim() !== "") {
        fetch('/edit_message', { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value }, 
            body: JSON.stringify({ id: msgId, text: newText.trim() }) 
        }).then(() => {
            renderedMessageIds.delete(msgId);
            fetchMessages();
        });
    }
}

// 【新規追加】メッセージの論理削除をサーバーに要請する関数
function triggerDelete(msgId) {
    if (confirm("このメッセージを消去してもよろしいですか？\n※データベース上には履歴が残りますが、画面上は非表示になります。")) {
        fetch('/delete_message', { 
            method: 'POST', 
            headers: { 
                'Content-Type': 'application/json', 
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value 
            }, 
            body: JSON.stringify({ id: msgId }) 
        })
        .then(res => {
            if (res.ok) {
                // 画面上の再描画キャッシュから一度IDを抹消
                renderedMessageIds.delete(msgId);
                // メッセージを再読み込みして「削除されました」状態に変形させる
                fetchMessages();
            } else {
                alert("削除に失敗しました。権限がないか、すでに削除されている可能性があります。");
            }
        });
    }
}


function sendReaction(msgId, rType) {
    fetch('/react_message', { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value }, 
        body: JSON.stringify({ id: msgId, type: rType }) 
    }).then(() => fetchMessages());
}

// メッセージ送信（FormData形式）
document.getElementById('chat-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const input = document.getElementById('message-input');
    const imgInput = document.getElementById('image-input');
    const vidInput = document.getElementById('video-input');
    
    const now = new Date();
    const timeStr = String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0');
    
    if (input.value.trim() !== "" || imgInput.files.length > 0 || vidInput.files.length > 0) {
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);
        formData.append('text', input.value.trim());
        formData.append('time', timeStr);
        formData.append('parent_id', selectedParentId);
        
        if (imgInput.files.length > 0) {
            formData.append('image', imgInput.files[0]);
        }
        if (vidInput.files.length > 0) {
            formData.append('video', vidInput.files[0]);
        }

        // 返信を送信した親メッセージのスレッドを自動的に「開いた状態」にする
        if (selectedParentId) {
            openThreadIds.add(selectedParentId);
        }

        fetch('/send_message', { 
            method: 'POST', 
            headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value }, 
            body: formData 
        }).then(() => { 
            input.value = ""; 
            resetFiles(); 
            cancelReply(); 
            fetchMessages(); 
        });
    }
});

// Shift+Enter対応の改行キーボード処理（Enter突き抜け＆日本語変換誤爆防止版）
document.getElementById('message-input').addEventListener('keydown', function(e) { 
    // 日本語入力の変換確定時のEnter（isComposing）は無視する
    if (e.isComposing) {
        return;
    }

    if (e.key === 'Enter' && !e.shiftKey) { 
        e.preventDefault(); 
        
        // ダイアログを閉じた直後の「Enter突き抜け」による誤送信を完全に防止
        // 念のため、メッセージが空かつファイルも選択されていない場合は送信しない安全策
        const imgInput = document.getElementById('image-input');
        const vidInput = document.getElementById('video-input');
        const hasFiles = (imgInput && imgInput.files.length > 0) || (vidInput && vidInput.files.length > 0);
        
        if (this.value.trim() === "" && !hasFiles) {
            return; // 何もなければ送信しない
        }

        // フォームのHTML要素を取得して直接 submit() を呼ぶか、正しくイベントを発火させる
        const form = document.getElementById('chat-form');
        if (form) {
            // requestSubmit() を使うことで、ブラウザの標準的な submit イベント（e.preventDefault等）が綺麗に連動します
            form.requestSubmit(); 
        }
    } 
});



/* ==========================================================================
   6. 定期自動実行の設定（Ajaxタイマー）
========================================================================== */
fetchMessages();setInterval(fetchMessages, 2000);

// 入力欄の文字数に合わせて高さを自動調整する処理
const tx = document.getElementById('message-input');
if (tx) {
    tx.addEventListener('input', function() {
        this.style.height = 'auto'; // 一度高さをリセット
        this.style.height = this.scrollHeight + 'px'; // 文字の高さに合わせて広げる
    });
}

// 投稿ボタンを押した後に高さを元（44px）に戻す処理を送信イベントに追加
document.getElementById('chat-form').addEventListener('submit', function() {
    setTimeout(() => {
        if (tx) tx.style.height = '44px';
    }, 10);
});
