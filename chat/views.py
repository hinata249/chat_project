from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse
import random
import math
import json
from .models import ChatMessage, MessageReaction, Report
from accounts.models import Notification



def chat_room(request):
    unread_count = Notification.objects.filter(receiver=request.user, is_read=False).count()
    
    context = {
        'user': request.user,
        'unread_count': unread_count  # カウントした数値をHTMLへ引き渡す
    }
    return render(request, 'chat/room.html', context)

@login_required
def send_message(request):
    if request.method == 'POST':
        
        text = request.POST.get('text', '')
        time_str = request.POST.get('time', '')
        parent_id = request.POST.get('parent_id')
        
        # ファイルの取得
        uploaded_image = request.FILES.get('image')
        uploaded_video = request.FILES.get('video')
        
        parent_msg = None
        if parent_id and parent_id != 'null' and parent_id != '':
            parent_msg = ChatMessage.objects.get(id=int(parent_id))
            
        # データベースに保存
        ChatMessage.objects.create(
            username=request.user.username,
            text=text,
            time=time_str,
            parent=parent_msg,
            image=uploaded_image,
            video=uploaded_video,
            user_id=request.user.id
        )

        if parent_msg:
            try:
                # 返信元のメッセージに記録されているユーザー名からUserモデルを特定
                parent_user = User.objects.get(username=parent_msg.username)
                
                # 自分自身への返信ではない場合のみ、Notificationテーブルに通知を保存
                if parent_user != request.user:
                    Notification.objects.create(
                        receiver=parent_user,
                        sender=request.user,
                        notification_type='reply',
                        message_id=parent_msg.id
                    )
            except Exception:
                pass

        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'failed'}, status=400)
@login_required
def edit_message(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        msg_id = int(data.get('id'))
        new_text = data.get('text')
        try:
            msg = ChatMessage.objects.get(id=msg_id, username=request.user.username)
            msg.text = new_text
            msg.save()
            return JsonResponse({'status': 'success'})
        except ChatMessage.DoesNotExist:
            pass
    return JsonResponse({'status': 'failed'}, status=400)

@login_required
def react_message(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        msg_id = int(data.get('id'))
        react_type = data.get('type')
        username = request.user.username
        
        #  'review3' を判定条件に追加しました
        if react_type in ['confirm', 'agree', 'review', 'review2', 'review3']:
            try:
                msg = ChatMessage.objects.get(id=msg_id)
                existing_react = MessageReaction.objects.filter(message=msg, user_id=request.user.id, react_type=react_type)
                if existing_react.exists():
                    existing_react.delete()
                else:
                    MessageReaction.objects.create(message=msg,username=username, user_id=request.user.id, react_type=react_type)

                    try:
                        target_user = User.objects.get(username=msg.username)
                        # 自分の投稿に対するリアクションでなければ通知を保存
                        if target_user != request.user:
                            Notification.objects.create(
                                receiver=target_user,
                                sender=request.user,
                                notification_type='reaction',
                                message_id=msg.id
                            )
                    except Exception:
                        pass  # 投稿ユーザーが見つからない等の例外時は処理をスキップ

                all_reactions = MessageReaction.objects.filter(message=msg)
                
                # JavaScript側が期待する初期構造を定義
                react_data = {
                    'confirm': {'count': 0, 'users': []},
                    'agree': {'count': 0, 'users': []},
                    'review': {'count': 0, 'users': []},
                    'review2': {'count': 0, 'users': []},
                    'review3': {'count': 0, 'users': []},
                }
                
                # ユーザーのニックネームを効率よく引くためのキャッシュ用辞書
                user_display_names = {}

                for r in all_reactions:
                    if r.react_type in react_data:
                        # 表示名（ニックネームがあれば優先、なければusername）を特定する処理
                        if r.user_id not in user_display_names:
                            try:
                                u = User.objects.get(id=r.user_id)
                                # 最初のHTMLコードにあった「user.profile.nickname」の規則に合わせます
                                display_name = getattr(u.profile, 'nickname', '')
                            except Exception:
                                display_name = r.username
                            user_display_names[r.username] = display_name
                        
                        # データを格納
                        react_data[r.react_type]['count'] += 1
                        react_data[r.react_type]['users'].append(user_display_names[r.username])

                # 成功ステータスと一緒に、メッセージIDと成形したリアクションデータを返す
                return JsonResponse({
                    'status': 'success',
                    'id': msg.id,
                    'reactions': react_data
                })
            

            except ChatMessage.DoesNotExist:
                pass
    return JsonResponse({'status': 'failed'}, status=400)             


from django.contrib.auth.models import User
from accounts.models import Profile  # フォルダ名が account の場合は account.models

# ==========================================
# 既存の get_messages を以下のように修正
# ==========================================
def get_messages(request):
    messages = ChatMessage.objects.all().order_by('id')
    logs = []
    
    for m in messages:
        reactions_count = {
            'confirm': MessageReaction.objects.filter(message=m, react_type='confirm').count(),
            'agree': MessageReaction.objects.filter(message=m, react_type='agree').count(),
            'review': MessageReaction.objects.filter(message=m, react_type='review').count(),
            'review2': MessageReaction.objects.filter(message=m, react_type='review2').count(),
            'review3': MessageReaction.objects.filter(message=m, react_type='review3').count(),
        }
        
        #  論理削除フラグの状態によってデータを制御
        if m.is_deleted:
            text_content = "このメッセージは削除されました"
            image_url = None
            video_url = None
        else:
            text_content = m.text
            image_url = m.image.url if m.image else None
            video_url = m.video.url if m.video else None
        
        # 発言ユーザーのプロフィールアイコンの取得処理
        icon_url = ""
        try:
            target_user = User.objects.get(id = m.user_id)
            # target_user = User.objects.get(username=m.username)
            profile, _ = Profile.objects.get_or_create(user=target_user)
            if profile and profile.icon and hasattr(profile.icon, 'url'):
                icon_url = profile.icon.url
        except Exception:
            icon_url = ""
        
        logs.append({
            'id': m.id,
            'username': m.username,
            'text': text_content,          #  置き換えたテキストを格納
            'time': m.time,
            'date': m.created_at.strftime('%Y/%m/%d') if hasattr(m, 'created_at') else "2026/06/XX", 
            'parent_id': m.parent.id if m.parent else None,
            'reactions': reactions_count,
            'image_url': image_url,        #  削除時は None になる
            'video_url': video_url,        #  削除時は None になる
            'icon_url': icon_url,
            'user_id': target_user.id if 'target_user' in locals() else None,
            'is_deleted': m.is_deleted,    #  フロントエンド判定用にフラグも追加
        })
    
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(receiver=request.user, is_read=False).count()
    else:
        unread_count = 0

    return JsonResponse({'messages': logs, 'unread_count': unread_count})

@login_required
def search_posts(request):
    query = request.GET.get('q', '').strip()
    results = []
    
    if query:
        # 検索キーワードを含むメッセージを取得（親メッセージのみ）
        messages = ChatMessage.objects.filter(
            text__icontains=query,
            is_deleted=False
        ).order_by('-id')
        
        for m in messages:
            reactions_count = {
                'confirm': MessageReaction.objects.filter(message=m, react_type='confirm').count(),
                'agree': MessageReaction.objects.filter(message=m, react_type='agree').count(),
                'review': MessageReaction.objects.filter(message=m, react_type='review').count(),
                'review2': MessageReaction.objects.filter(message=m, react_type='review2').count(),
                'review3': MessageReaction.objects.filter(message=m, react_type='review3').count(),
            }
            
            image_url = m.image.url if m.image else None
            video_url = m.video.url if m.video else None
            
            # 発言ユーザーのプロフィールアイコンの取得処理
            icon_url = ""
            user_id = None
            try:
                target_user = User.objects.get(username=m.username)
                profile, _ = Profile.objects.get_or_create(user=target_user)
                if profile and profile.icon and hasattr(profile.icon, 'url'):
                    icon_url = profile.icon.url
                user_id = target_user.id
            except Exception:
                icon_url = ""
            
            parent_id = None
            is_reply = False
            if m.parent:
                is_reply = True
                parent_id = m.parent.id

            results.append({
                'id': m.id,
                'username': m.username,
                'text': m.text,
                'time': m.time,
                'reactions': reactions_count,
                'image_url': image_url,
                'video_url': video_url,
                'icon_url': icon_url,
                'user_id': user_id,
                'reply_count': m.replies.count(),
                'parent_id' : parent_id,
                'is_reply' : is_reply
            })
    
    return JsonResponse({'results': results, 'query': query})


# ==========================================
# 【新規追加】メッセージを論理削除するビュー
# ==========================================
@login_required
def delete_message(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            msg_id = int(data.get('id'))
            
            # 安全のため、メッセージIDと「ログインしている本人のユーザー名」が一致するものだけを対象にする
            msg = ChatMessage.objects.get(id=msg_id, username=request.user.username)
            
            msg.is_deleted = True  #  物理削除はせず、フラグをTrueにするだけ
            msg.save()
            return JsonResponse({'status': 'success'})
        except (ChatMessage.DoesNotExist, ValueError, TypeError):
            return JsonResponse({'status': 'failed', 'error': '対象のメッセージが見つからないか、権限がありません'}, status=400)
            
    return JsonResponse({'status': 'failed'}, status=400)

def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})

@login_required
def search_posts(request):
    query = request.GET.get('q', '').strip()
    results = []
    
    if query:
        # 検索キーワードを含むすべてのメッセージを取得（親メッセージも返信も両方）
        messages = ChatMessage.objects.filter(
            text__icontains=query
        ).order_by('-id')
        
        for m in messages:
            reactions_count = {
                'confirm': MessageReaction.objects.filter(message=m, react_type='confirm').count(),
                'agree': MessageReaction.objects.filter(message=m, react_type='agree').count(),
                'review': MessageReaction.objects.filter(message=m, react_type='review').count(),
                'review2': MessageReaction.objects.filter(message=m, react_type='review2').count(),
                'review3': MessageReaction.objects.filter(message=m, react_type='review3').count(),
            }
            
            image_url = m.image.url if m.image else None
            video_url = m.video.url if m.video else None
            
            # 発言ユーザーのプロフィールアイコンの取得処理
            icon_url = ""
            user_id = None
            try:
                target_user = User.objects.get(username=m.username)
                profile, _ = Profile.objects.get_or_create(user=target_user)
                if profile and profile.icon and hasattr(profile.icon, 'url'):
                    icon_url = profile.icon.url
                user_id = target_user.id
            except Exception:
                icon_url = ""
            
            # 返信の場合は親メッセージの情報を追加
            parent_id = None
            is_reply = False
            if m.parent:
                is_reply = True
                parent_id = m.parent.id
            
            results.append({
                'id': m.id,
                'username': m.username,
                'text': m.text,
                'time': m.time,
                'reactions': reactions_count,
                'image_url': image_url,
                'video_url': video_url,
                'icon_url': icon_url,
                'user_id': user_id,
                'reply_count': m.replies.count(),
                'parent_id': parent_id,
                'is_reply': is_reply,
            })
    
    return JsonResponse({'results': results, 'query': query})

@login_required
def notification_list(request):
    # 自分宛ての通知を新しい順にすべて取得
    notifications = Notification.objects.filter(receiver=request.user)
    
    # この画面を開いた瞬間に、これまでの通知をすべて「既読（is_read=True）」にする
    notifications.update(is_read=True)
    
    return render(request, 'chat/notifications.html', {'notifications': notifications})

#【新規追加】ユーザー検索(部分一致)
from django.contrib.auth.models import User

@login_required
def search_users(request):
    """
    ユーザー名を部分一致で検索し、プロフィール画像付きのJSON形式で返すビュー
    """
    keyword = request.GET.get('keyword', '').strip()
    if not keyword:
        return JsonResponse({'users': []})
    
    # usernameカラムからキーワードを部分一致で最大20件検索
    matching_users = User.objects.filter(username__icontains=keyword)[:20]
    
    # フロントエンドに渡すデータを構築
    user_list = []
    for u in matching_users:
        icon_url = ""
        # ⭕ 投稿検索のロジックを参考：プロフィールアイコンのURLを取得する
        try:
            if u.profile and u.profile.icon:
                icon_url = u.profile.icon.url
        except Exception:
            pass # プロフィールが存在しない等のエラーを安全に回避
            
        user_list.append({
            'id': u.id,
            'username': u.username,
            'icon_url': icon_url # 💡 アイコンのURLを新しく追加
        })
        
    return JsonResponse({'users': user_list})

# === views.py の末尾に新しく追加します ===
from django.http import JsonResponse
from .models import MessageReaction # models.pyから読み込み
from django.contrib.auth.models import User

def get_reaction_users(request):
    msg_id = request.GET.get('msg_id')
    react_type = request.GET.get('type')
    
    reactions = MessageReaction.objects.filter(message_id=msg_id, react_type=react_type)
    
    users_list = []
    for r in reactions:
        display_name = r.username
        icon_url = ""  # 一旦空文字にしておきます
        
        try:
            u = User.objects.get(id=r.user_id)
            display_name = getattr(u.profile, 'nickname', '') or u.username
            
            # 以前送っていただいた get_messages 関数のアイコン取得ロジックと完全に同じ記述に統一します
            if hasattr(u, 'profile') and u.profile and hasattr(u.profile, 'icon') and u.profile.icon and hasattr(u.profile.icon, 'url'):
                icon_url = u.profile.icon.url
        except Exception:
            pass
            
        users_list.append({
            'name': display_name,
            'icon_url': icon_url
        })
        
    return JsonResponse({'users': users_list})

# 通報機能
@login_required
def report_message(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message_id = data.get('id')
            reason = data.get('reason', '通報理由なし')
            
            target_message = get_object_or_404(ChatMessage, id=message_id)
            Report.objects.create(reporter=request.user, message=target_message, reason=reason)
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=400)



# 麻雀

MANZU = [f"{i}萬" for i in range(1, 10)]
PINZU = [f"{i}筒" for i in range(1, 10)]
SOUZU = [f"{i}索" for i in range(1, 10)]
JIHAI = ["東", "南", "西", "北", "白", "發", "中"]
BASE_TILES = MANZU + PINZU + SOUZU + JIHAI
YAOCHU = ["1萬", "9萬", "1筒", "9筒", "1索", "9索"] + JIHAI

TILE_ORDER = {tile: i for i, tile in enumerate(BASE_TILES)}
TILE_ORDER["赤5萬"] = TILE_ORDER["5萬"] - 0.1
TILE_ORDER["赤5筒"] = TILE_ORDER["5筒"] - 0.1
TILE_ORDER["赤5索"] = TILE_ORDER["5索"] - 0.1

def normalize_tile(t):
    return t.replace('赤', '')

def normalize_hand(hand):
    return [normalize_tile(t) for t in hand]

def is_yaochu(tile):
    return normalize_tile(tile) in YAOCHU

def get_bakaze(kyoku):
    if kyoku <= 4: return "東"
    elif kyoku <= 8: return "南"
    else: return "西"

def get_jikaze(kyoku, player):
    positions = ['jibun', 'shimochi', 'toimen', 'kamicha']
    winds = ["東", "南", "西", "北"]
    oya_idx = (kyoku - 1) % 4
    player_idx = positions.index(player)
    wind_idx = (player_idx - oya_idx) % 4
    return winds[wind_idx]

def get_flat_furo_tiles(furo_list):
    full_hand = []
    for f in furo_list:
        if isinstance(f, dict):
            full_hand.extend(f['tiles'])
        else:
            full_hand.extend(f)
    return full_hand

def check_chiitoitsu(norm_hand):
    if len(norm_hand) != 14: return False
    counts = {t: norm_hand.count(t) for t in set(norm_hand)}
    return len(counts) == 7 and all(c == 2 for c in counts.values())

def get_agari_patterns(norm_closed_hand):
    if len(norm_closed_hand) % 3 != 2: return []
    sorted_hand = sorted(norm_closed_hand, key=lambda t: TILE_ORDER[t])
    unique_tiles = sorted(list(set(sorted_hand)), key=lambda t: TILE_ORDER[t])
    patterns = []

    for janto in unique_tiles:
        if sorted_hand.count(janto) >= 2:
            temp_hand = sorted_hand.copy()
            temp_hand.remove(janto)
            temp_hand.remove(janto)
            
            mentsu_list = find_mentsu(temp_hand)
            if mentsu_list is not None:
                for ml in mentsu_list:
                    patterns.append(ml + [(janto, janto)])
    return patterns

def find_mentsu(norm_hand):
    if not norm_hand: return [[]]
    first = norm_hand[0]
    result = []
    
    if norm_hand.count(first) >= 3:
        next_hand = norm_hand.copy()
        for _ in range(3): next_hand.remove(first)
        sub_patterns = find_mentsu(next_hand)
        if sub_patterns is not None:
            for sp in sub_patterns:
                result.append([(first, first, first)] + sp)
                
    if first not in JIHAI:
        num = int(first[0])
        suit = first[1]
        t2, t3 = f"{num+1}{suit}", f"{num+2}{suit}"
        if t2 in norm_hand and t3 in norm_hand:
            next_hand = norm_hand.copy()
            next_hand.remove(first)
            next_hand.remove(t2)
            next_hand.remove(t3)
            sub_patterns = find_mentsu(next_hand)
            if sub_patterns is not None:
                for sp in sub_patterns:
                    result.append([(first, t2, t3)] + sp)
                    
    return result if result else None

def is_win(hand, furo_list=[]):
    full_hand = hand.copy() + get_flat_furo_tiles(furo_list)
    norm_closed_hand = normalize_hand(hand)
    norm_full_hand = normalize_hand(full_hand)
    
    if len(furo_list) == 0:
        if check_chiitoitsu(norm_full_hand): return True
        if len(norm_full_hand) == 14 and len(set(norm_full_hand)) == 13 and all(t in YAOCHU for t in norm_full_hand): return True
        
    return len(get_agari_patterns(norm_closed_hand)) > 0

def make_score_movement_text(session_scores, points_diff):
    name_map = {'jibun': '自分', 'shimochi': '下家', 'toimen': '対面', 'kamicha': '上家'}
    movement_parts = []
    for p in ['jibun', 'shimochi', 'toimen', 'kamicha']:
        before = session_scores.get(p, 25000)
        diff = points_diff.get(p, 0)
        after = before + diff
        name = name_map[p]
        if diff > 0:
            movement_parts.append(f"{name}: {before} + {diff} = {after}")
        elif diff < 0:
            movement_parts.append(f"{name}: {before} - {abs(diff)} = {after}")
        else:
            movement_parts.append(f"{name}: {before} = {after}")
    return "\n\n【点数移動】\n" + "\n".join(movement_parts)

def calculate_fu(closed_mentsu, furo_list, janto, agari_tile, is_tsumo, is_menzen, bakaze="東", jikaze="東"):
    base_fu = 20
    norm_agari = normalize_tile(agari_tile)

    janto_fu = 0
    if janto in [bakaze, jikaze, "白", "發", "中"]:
        janto_fu += 2
        if bakaze == jikaze and janto == bakaze: janto_fu += 2

    furo_fu = 0
    for f in furo_list:
        action = f.get('action')
        tiles = f.get('tiles', [])
        if not tiles: continue
        called = normalize_tile(f.get('called_tile', tiles[0]))

        if action == 'pon':
            furo_fu += 4 if is_yaochu(called) else 2
        elif action in ['kan', 'kakan']:
            furo_fu += 16 if is_yaochu(called) else 8
        elif action == 'ankan':
            furo_fu += 32 if is_yaochu(called) else 16

    possible_fus = []

    if janto == norm_agari:
        temp_fu = base_fu + janto_fu + furo_fu + 2
        for m in closed_mentsu:
            if m[0] == m[1]: temp_fu += 8 if is_yaochu(m[0]) else 4
        if is_tsumo: temp_fu += 2
        elif is_menzen: temp_fu += 10
        possible_fus.append(math.ceil(temp_fu / 10) * 10)

    for i, target_m in enumerate(closed_mentsu):
        if norm_agari in target_m:
            temp_fu = base_fu + janto_fu + furo_fu
            wait_fu = 0

            if target_m[0] == target_m[1]:
                if not is_tsumo:
                    temp_fu += 4 if is_yaochu(target_m[0]) else 2
                else:
                    temp_fu += 8 if is_yaochu(target_m[0]) else 4
            else:
                idx = target_m.index(norm_agari)
                if idx == 1:
                    wait_fu = 2
                elif idx == 0 and target_m[2][0] == '9':
                    wait_fu = 2
                elif idx == 2 and target_m[0][0] == '1':
                    wait_fu = 2

            temp_fu += wait_fu

            for j, other_m in enumerate(closed_mentsu):
                if i == j: continue
                if other_m[0] == other_m[1]:
                    temp_fu += 8 if is_yaochu(other_m[0]) else 4

            if is_tsumo: temp_fu += 2
            elif is_menzen: temp_fu += 10
            possible_fus.append(math.ceil(temp_fu / 10) * 10)

    if not possible_fus:
        return 25

    return max(possible_fus)

def judge_yaku(hand, furo_list, agari_tile, is_tsumo, is_riichi, dora_tiles, is_ippatsu=False, bakaze="東", jikaze="東", wall_len=50, discards_len=5, is_rinshan=False, is_chankan=False, ura_indicators=[], is_daburi=False):
    is_menzen = len([f for f in furo_list if f.get('action') != 'ankan']) == 0
    norm_closed_hand = normalize_hand(hand)
    full_hand = hand.copy() + get_flat_furo_tiles(furo_list)
    norm_full_hand = normalize_hand(full_hand)
    
    dora_count = sum(norm_full_hand.count(dt) for dt in dora_tiles)
    aka_count = sum(1 for t in full_hand if '赤' in t)
    dora_yaku = []
    if dora_count > 0: dora_yaku.append((f"ドラ{dora_count}", dora_count))
    if aka_count > 0: dora_yaku.append((f"赤ドラ{aka_count}", aka_count))
    
    if is_riichi and ura_indicators:
        ura_tiles = [get_dora_tile(ind) for ind in ura_indicators]
        ura_count = sum(norm_full_hand.count(ut) for ut in ura_tiles)
        if ura_count > 0:
            dora_yaku.append((f"裏ドラ{ura_count}", ura_count))

    yakuman_list = []
    if is_menzen and len(norm_full_hand) == 14 and len(set(norm_full_hand)) == 13 and all(t in YAOCHU for t in norm_full_hand):
        yakuman_list.append(("国士無双", 13))
    if all(t in JIHAI for t in norm_full_hand):
        yakuman_list.append(("字一色", 13))
    if all(t in ["2索","3索","4索","6索","8索","發"] for t in norm_full_hand):
        yakuman_list.append(("緑一色", 13))
    if all(t in ["1萬","9萬","1筒","9筒","1索","9索"] for t in norm_full_hand):
        yakuman_list.append(("清老頭", 13))
        
    kantsu_count = sum(1 for f in furo_list if f.get('action') in ['kan', 'ankan', 'kakan'])
    if kantsu_count == 4:
        yakuman_list.append(("四槓子", 13))
        
    if is_menzen and not any(t in JIHAI for t in norm_full_hand):
        suits = set(t[1] for t in norm_full_hand)
        if len(suits) == 1:
            suit = list(suits)[0]
            base_chuuren = [f"1{suit}"]*3 + [f"{i}{suit}" for i in range(2,9)] + [f"9{suit}"]*3
            temp_hand = norm_full_hand.copy()
            match = True
            for bt in base_chuuren:
                if bt in temp_hand: temp_hand.remove(bt)
                else: match = False; break
            if match: yakuman_list.append(("九蓮宝燈", 13))

    if discards_len == 0 and is_menzen:
        if is_tsumo and bakaze == jikaze: yakuman_list.append(("天和", 13))
        elif is_tsumo and bakaze != jikaze: yakuman_list.append(("地和", 13))

    patterns = get_agari_patterns(norm_closed_hand)
    
    open_mentsu = []
    for f in furo_list:
        norm_tiles = normalize_hand(f['tiles'])
        if f['action'] in ['kan', 'ankan', 'kakan', 'pon']: open_mentsu.append((norm_tiles[0], norm_tiles[0], norm_tiles[0]))
        else: open_mentsu.append(tuple(sorted(norm_tiles, key=lambda t: TILE_ORDER[t])))

    if not patterns:
        if yakuman_list:
            return yakuman_list, sum(y[1] for y in yakuman_list), 25
            
        if check_chiitoitsu(norm_full_hand):
            yaku_temp = [("七対子", 2)]
            if is_tsumo: yaku_temp.append(("門前清自摸和", 1))
            if is_daburi: yaku_temp.append(("ダブル立直", 2))
            elif is_riichi: yaku_temp.append(("立直", 1))
            if is_ippatsu: yaku_temp.append(("一発", 1))
            if wall_len == 0 and is_tsumo: yaku_temp.append(("海底撈月", 1))
            if wall_len == 0 and not is_tsumo: yaku_temp.append(("河底撈魚", 1))
            if all(not is_yaochu(t) for t in norm_full_hand): yaku_temp.append(("断么九", 1))
            if all(is_yaochu(t) for t in norm_full_hand): yaku_temp.append(("混老頭", 2))
            
            suits = set(t[1] for t in norm_full_hand if t not in JIHAI)
            has_jihai = any(t in JIHAI for t in norm_full_hand)
            if len(suits) == 1:
                if has_jihai: yaku_temp.append(("混一色", 3))
                else: yaku_temp.append(("清一色", 6))
                
            if not yaku_temp: return [], 0, 0
            yaku_temp.extend(dora_yaku)
            return yaku_temp, sum(y[1] for y in yaku_temp), 25
            
        return [], 0, 0

    best_yaku = []
    max_han = 0
    best_fu = 0
    
    for pattern in patterns:
        yaku_temp = []
        closed_mentsu = pattern[:-1]
        janto = pattern[-1][0]
        all_mentsu = closed_mentsu + open_mentsu
        
        ankou_count = sum(1 for m in closed_mentsu if m[0] == m[1] and (is_tsumo or normalize_tile(agari_tile) != m[0]))
        ankou_count += sum(1 for f in furo_list if f.get('action') == 'ankan') 
        
        sangen_koutsu = sum(1 for m in all_mentsu if m[0] == m[1] and m[0] in ["白", "發", "中"])
        sangen_janto = 1 if janto in ["白", "發", "中"] else 0
        wind_koutsu = sum(1 for m in all_mentsu if m[0] == m[1] and m[0] in ["東", "南", "西", "北"])
        wind_janto = 1 if janto in ["東", "南", "西", "北"] else 0
        
        current_yakuman = yakuman_list.copy()
        if ankou_count == 4: current_yakuman.append(("四暗刻", 13))
        if sangen_koutsu == 3: current_yakuman.append(("大三元", 13))
        if wind_koutsu == 4: current_yakuman.append(("大四喜", 13))
        if wind_koutsu == 3 and wind_janto == 1: current_yakuman.append(("小四喜", 13))
        
        if current_yakuman:
            return current_yakuman, sum(y[1] for y in current_yakuman), 25
            
        if is_menzen:
            if is_daburi: yaku_temp.append(("ダブル立直", 2))
            elif is_riichi: yaku_temp.append(("立直", 1))
            if is_ippatsu and is_riichi: yaku_temp.append(("一発", 1))
            if is_tsumo: yaku_temp.append(("門前清自摸和", 1))
            
        if wall_len == 0 and is_tsumo: yaku_temp.append(("海底撈月", 1))
        if wall_len == 0 and not is_tsumo: yaku_temp.append(("河底撈魚", 1))
        if is_rinshan: yaku_temp.append(("嶺上開花", 1))
        if is_chankan: yaku_temp.append(("槍槓", 1))

        if all(not is_yaochu(t) for t in norm_full_hand): yaku_temp.append(("断么九", 1))
            
        for m in all_mentsu:
            if m[0] == m[1]:
                if m[0] == bakaze: yaku_temp.append(("役牌(場風)", 1))
                if m[0] == jikaze: yaku_temp.append(("役牌(自風)", 1))
                if m[0] in ["白", "發", "中"]: yaku_temp.append((f"役牌({m[0]})", 1))
                
        is_pinfu = False
        if is_menzen and all(m[0] != m[1] for m in closed_mentsu) and janto not in [bakaze, jikaze, "白", "發", "中"]:
            for m in closed_mentsu:
                if normalize_tile(agari_tile) in m:
                    idx = m.index(normalize_tile(agari_tile))
                    if (idx == 0 and m[2][0] != '9') or (idx == 2 and m[0][0] != '1'):
                        is_pinfu = True
                        break
        
        if is_pinfu: yaku_temp.append(("平和", 1))
        
        if len([m for m in all_mentsu if m[0] == m[1]]) == 4: yaku_temp.append(("対々和", 2))
        if ankou_count == 3: yaku_temp.append(("三暗刻", 2))
        if kantsu_count == 3: yaku_temp.append(("三槓子", 2))
        if sangen_koutsu == 2 and sangen_janto == 1: yaku_temp.append(("小三元", 2))

        shuntsu_nums = {'萬':[], '筒':[], '索':[]}
        koutsu_nums = {'萬':[], '筒':[], '索':[]}
        for m in all_mentsu:
            if m[0] != m[1]: shuntsu_nums[m[0][1]].append(int(m[0][0]))
            else:
                if m[0] not in JIHAI: koutsu_nums[m[0][1]].append(int(m[0][0]))
                    
        if any(n in shuntsu_nums['萬'] and n in shuntsu_nums['筒'] and n in shuntsu_nums['索'] for n in range(1,8)):
            yaku_temp.append(("三色同順", 2 if is_menzen else 1))
        if any(n in koutsu_nums['萬'] and n in koutsu_nums['筒'] and n in koutsu_nums['索'] for n in range(1,10)):
            yaku_temp.append(("三色同刻", 2))
        for suit in ['萬', '筒', '索']:
            if 1 in shuntsu_nums[suit] and 4 in shuntsu_nums[suit] and 7 in shuntsu_nums[suit]:
                yaku_temp.append(("一気通貫", 2 if is_menzen else 1))
                
        if is_menzen:
            shuntsu_str = [str(m) for m in closed_mentsu if m[0] != m[1]]
            duplicates = len(shuntsu_str) - len(set(shuntsu_str))
            if duplicates == 1: yaku_temp.append(("一盃口", 1))
            elif duplicates == 2: yaku_temp.append(("二盃口", 3))

        has_terminals = all(any(is_yaochu(t) for t in m) for m in all_mentsu + [[janto, janto]])
        is_all_yaochu = all(is_yaochu(t) for t in norm_full_hand)
        has_shuntsu = any(m[0] != m[1] for m in all_mentsu)
        has_jihai = any(t in JIHAI for t in norm_full_hand)
        
        if is_all_yaochu and has_jihai and not has_shuntsu: yaku_temp.append(("混老頭", 2))
        elif has_terminals and not has_jihai and has_shuntsu: yaku_temp.append(("純全帯么九", 3 if is_menzen else 2))
        elif has_terminals and has_jihai and has_shuntsu: yaku_temp.append(("混全帯么九", 2 if is_menzen else 1))

        suits = set(t[1] for t in norm_full_hand if t not in JIHAI)
        if len(suits) == 1:
            if has_jihai: yaku_temp.append(("混一色", 3 if is_menzen else 2))
            else: yaku_temp.append(("清一色", 6 if is_menzen else 5))
            
        if not yaku_temp: continue
        
        yaku_temp.extend(dora_yaku)
        
        han = sum(y[1] for y in yaku_temp)
        fu = calculate_fu(closed_mentsu, furo_list, janto, agari_tile, is_tsumo, is_menzen, bakaze, jikaze)
        
        if is_pinfu and is_tsumo: fu = 20
        elif is_pinfu and not is_tsumo: fu = 30
        elif fu < 30: fu = 30
        
        if han > max_han or (han == max_han and fu > best_fu):
            max_han = han
            best_fu = fu
            best_yaku = yaku_temp

    return best_yaku, max_han, best_fu

def calc_points(han, fu, is_oya, is_tsumo, honba=0, kyotaku=0):
    if han == 0: return "役なし", 0
    if han >= 13: mangan_type, basic_points = "役満", 8000
    elif han >= 11: mangan_type, basic_points = "三倍満", 6000
    elif han >= 8: mangan_type, basic_points = "倍満", 4000
    elif han >= 6: mangan_type, basic_points = "跳満", 3000
    else:
        basic_points = fu * (2 ** (han + 2))
        mangan_type = ""
        if basic_points >= 1920:
            mangan_type, basic_points = "満貫", 2000
            
    honba_pts = honba * 300
    kyotaku_pts = kyotaku * 1000

    if is_oya:
        if is_tsumo:
            all_pay = math.ceil(basic_points * 2 / 100) * 100
            base_total = all_pay * 3
            total = base_total + honba_pts + kyotaku_pts
            parts = [str(base_total)]
            if honba_pts > 0: parts.append(str(honba_pts))
            if kyotaku_pts > 0: parts.append(str(kyotaku_pts))
            formula = "+".join(parts)
            if len(parts) > 1: formula += f"={total}"
            return f"{mangan_type} {formula}点 ({all_pay}点オール)", total
        else:
            base_total = math.ceil(basic_points * 6 / 100) * 100
            total = base_total + honba_pts + kyotaku_pts
            parts = [str(base_total)]
            if honba_pts > 0: parts.append(str(honba_pts))
            if kyotaku_pts > 0: parts.append(str(kyotaku_pts))
            formula = "+".join(parts)
            if len(parts) > 1: formula += f"={total}"
            return f"{mangan_type} {formula}点", total
    else:
        if is_tsumo:
            oya_pay = math.ceil(basic_points * 2 / 100) * 100
            ko_pay = math.ceil(basic_points / 100) * 100
            base_total = oya_pay + ko_pay * 2
            total = base_total + honba_pts + kyotaku_pts
            parts = [str(base_total)]
            if honba_pts > 0: parts.append(str(honba_pts))
            if kyotaku_pts > 0: parts.append(str(kyotaku_pts))
            formula = "+".join(parts)
            if len(parts) > 1: formula += f"={total}"
            return f"{mangan_type} {formula}点 ({ko_pay}・{oya_pay}点)", total
        else:
            base_total = math.ceil(basic_points * 4 / 100) * 100
            total = base_total + honba_pts + kyotaku_pts
            parts = [str(base_total)]
            if honba_pts > 0: parts.append(str(honba_pts))
            if kyotaku_pts > 0: parts.append(str(kyotaku_pts))
            formula = "+".join(parts)
            if len(parts) > 1: formula += f"={total}"
            return f"{mangan_type} {formula}点", total

def get_dora_tile(dora_indicator):
    norm_ind = normalize_tile(dora_indicator)
    if norm_ind in JIHAI:
        jihai_order = ["東", "南", "西", "北", "白", "發", "中"]
        idx = jihai_order.index(norm_ind)
        if idx < 4: return jihai_order[(idx + 1) % 4]
        else: return jihai_order[4 + ((idx - 4 + 1) % 3)]
    else:
        num = int(norm_ind[0])
        suit = norm_ind[1]
        next_num = (num % 9) + 1
        return f"{next_num}{suit}"

def get_machi_tiles(hand13, furo_list=[]):
    machi = []
    norm_hand = normalize_hand(hand13)
    norm_furo = normalize_hand(get_flat_furo_tiles(furo_list))
    for tile in BASE_TILES:
        if norm_hand.count(tile) + norm_furo.count(tile) >= 4: continue
        if is_win(hand13 + [tile], furo_list): machi.append(tile)
    return machi

def get_jibun_furiten_status(request, hand, furo_list, discards):
    machi_tiles = get_machi_tiles(hand, furo_list)
    if not machi_tiles: return False
    is_discard = any(normalize_tile(m) in [normalize_tile(t) for t in discards] for m in machi_tiles)
    is_doujun = request.session.get('jibun_doujun_furiten', False)
    is_riichi = request.session.get('jibun_riichi_furiten', False)
    return is_discard or is_doujun or is_riichi

def get_ron_players(request, discard_tile, discarder):
    players_order = ['jibun', 'shimochi', 'toimen', 'kamicha']
    idx = players_order.index(discarder)
    check_order = [players_order[(idx + i) % 4] for i in range(1, 4)]
    
    kyoku = request.session.get('kyoku', 1)
    dora_indicators = request.session.get('dora_indicators', [])
    dora_tiles = [get_dora_tile(ind) for ind in dora_indicators]
    ura_indicators = request.session.get('ura_indicators', [])
    wall = request.session.get('wall', [])
    bakaze = get_bakaze(kyoku)
    
    ron_players = []
    for p in check_order:
        hand = request.session.get(f'{p}_hand', [])
        discards = request.session.get(f'{p}_discards', [])
        is_riichi = request.session.get('is_jibun_riichi' if p == 'jibun' else f'{p}_is_riichi', False)
        is_daburi = request.session.get('is_jibun_daburi' if p == 'jibun' else f'{p}_is_daburi', False)
        furo = request.session.get('jibun_furo', []) if p == 'jibun' else request.session.get(f'{p}_furo', [])
        ippatsu_chance = request.session.get('ippatsu_chance' if p == 'jibun' else f'{p}_ippatsu_chance', False)
        
        machi = get_machi_tiles(hand, furo)
        if normalize_tile(discard_tile) in machi:
            if p == 'jibun':
                request.session['missed_ron_candidate'] = True
                is_furiten = get_jibun_furiten_status(request, hand, furo, discards)
            else:
                is_doujun = request.session.get(f'{p}_doujun_furiten', False)
                is_riichi_f = request.session.get(f'{p}_riichi_furiten', False)
                is_discard_f = any(normalize_tile(m) in [normalize_tile(t) for t in discards] for m in machi)
                is_furiten = is_discard_f or is_doujun or is_riichi_f
                
            if not is_furiten:
                temp_hand = hand + [discard_tile]
                jikaze = get_jikaze(kyoku, p)
                yaku_list, han, fu = judge_yaku(temp_hand, furo, discard_tile, False, is_riichi, dora_tiles, ippatsu_chance, bakaze, jikaze, len(wall), len(discards), ura_indicators=ura_indicators, is_daburi=is_daburi)
                if han > 0:
                    ron_players.append({
                        'player': p, 'yaku_list': yaku_list, 'han': han, 'fu': fu, 'machi': machi
                    })
    return ron_players

def process_multi_ron_data(request, ron_players, discarder):
    kyoku = request.session.get('kyoku', 1)
    honba = request.session.get('honba', 0)
    kyotaku = request.session.get('kyotaku', 0)
    current_scores = request.session.get('scores', {'jibun': 25000, 'shimochi': 25000, 'toimen': 25000, 'kamicha': 25000})
    ura_indicators = request.session.get('ura_indicators', [])
    
    oya_order = ['jibun', 'shimochi', 'toimen', 'kamicha']
    oya = oya_order[(kyoku - 1) % 4]
    cpu_map_jp = {'jibun': '自分', 'shimochi': '下家', 'toimen': '対面', 'kamicha': '上家'}
    
    discarder_just_riichi = request.session.get(f'{discarder}_just_riichi', False)
    if discarder_just_riichi:
        kyotaku = max(0, kyotaku - 1)

    if len(ron_players) == 3:
        tenpai_status = {}
        points_diff = {'jibun': 0, 'shimochi': 0, 'toimen': 0, 'kamicha': 0}
        
        if discarder_just_riichi:
            points_diff[discarder] += 1000

        for p in oya_order:
            hand = request.session.get(f'{p}_hand', [])
            furo = request.session.get('jibun_furo', []) if p == 'jibun' else request.session.get(f'{p}_furo', [])
            if get_machi_tiles(hand, furo): tenpai_status[p] = True
            else: tenpai_status[p] = False
            
        if tenpai_status[oya]:
            next_kyoku = kyoku
            next_honba = honba + 1
            result_msg = "トリプルロンが発生したため、三家和により流局となります。（親テンパイにより連荘）"
        else:
            next_kyoku = kyoku + 1
            next_honba = honba + 1
            result_msg = "トリプルロンが発生したため、三家和により流局となります。（親ノーテンにより親移動）"
            
        cpu_hands = { 'shimochi': request.session.get('shimochi_hand', []), 'toimen': request.session.get('toimen_hand', []), 'kamicha': request.session.get('kamicha_hand', []) }
        return {
            'is_ryukyoku': True, 'result_msg': result_msg, 'points_diff': points_diff,
            'next_kyoku': next_kyoku, 'next_honba': next_honba, 'next_kyotaku': kyotaku,
            'current_kyotaku': kyotaku, 'cpu_hands': cpu_hands
        }

    points_diff = {'jibun': 0, 'shimochi': 0, 'toimen': 0, 'kamicha': 0}
    
    if discarder_just_riichi:
        points_diff[discarder] += 1000

    result_texts = []
    
    first_p = ron_players[0]['player']
    if first_p == oya:
        next_kyoku = kyoku
        next_honba = honba + 1
    else:
        next_kyoku = kyoku + 1
        next_honba = 0
        
    for i, rp in enumerate(ron_players):
        p = rp['player']
        han = rp['han']
        fu = rp['fu']
        yaku_list = rp['yaku_list']
        machi_list = rp['machi']
        
        is_p_oya = (p == oya)
        h_val = honba if i == 0 else 0
        k_val = kyotaku if i == 0 else 0
        
        score_result, total_points = calc_points(han, fu, is_p_oya, False, h_val, k_val)
        yaku_str = "、".join([y[0] for y in yaku_list])
        machi_str = "、".join(machi_list)
        
        p_name = cpu_map_jp[p]
        res_text = f"{p_name}のロンアガリ！\n{score_result}\n{han}翻 {fu}符\n[{yaku_str}]\n【待ち牌】: {machi_str}"
        
        is_riichi = request.session.get('is_jibun_riichi' if p == 'jibun' else f'{p}_is_riichi', False)
        is_daburi = request.session.get('is_jibun_daburi' if p == 'jibun' else f'{p}_is_daburi', False)
        if is_riichi or is_daburi:
            ura_inds_str = " ".join([normalize_tile(ind) for ind in ura_indicators])
            res_text += f"\n(裏ドラ表示牌: {ura_inds_str})"
            
        result_texts.append(res_text)
        
        if han >= 13: basic_points = 8000
        elif han >= 11: basic_points = 6000
        elif han >= 8: basic_points = 4000
        elif han >= 6: basic_points = 3000
        else:
            basic_points = fu * (2 ** (han + 2))
            if basic_points >= 1920: basic_points = 2000
            
        if is_p_oya:
            ron_pay = math.ceil(basic_points * 6 / 100) * 100 + 300 * h_val
        else:
            ron_pay = math.ceil(basic_points * 4 / 100) * 100 + 300 * h_val
            
        points_diff[p] += ron_pay + k_val * 1000
        points_diff[discarder] -= ron_pay

    movement_text = make_score_movement_text(current_scores, points_diff)
    title = "ダブルロン発生！" if len(ron_players) == 2 else ""
    full_result_text = (f"【{title}】\n\n" if title else "") + "\n---------------------\n".join(result_texts) + movement_text
    cpu_hands = { 'shimochi': request.session.get('shimochi_hand', []), 'toimen': request.session.get('toimen_hand', []), 'kamicha': request.session.get('kamicha_hand', []) }
    
    return {
        'cpu_just_ron': True, 'score_result': full_result_text, 'points_diff': points_diff,
        'next_kyoku': next_kyoku, 'next_honba': next_honba, 'next_kyotaku': 0, 'cpu_hands': cpu_hands
    }

def simulate_naki_tenpai(request, p, hand, furo, discard_tile, action, consume_tiles):
    kyoku = request.session.get('kyoku', 1)
    dora_indicators = request.session.get('dora_indicators', [])
    dora_tiles = [get_dora_tile(ind) for ind in dora_indicators]
    wall = request.session.get('wall', [])
    bakaze = get_bakaze(kyoku)
    jikaze = get_jikaze(kyoku, p)
    discards = request.session.get(f'{p}_discards', [])
    ura_indicators = request.session.get('ura_indicators', [])

    temp_hand = hand.copy()
    for t in consume_tiles:
        if t in temp_hand: temp_hand.remove(t)
    
    temp_furo = furo.copy()
    temp_furo.append({'action': action, 'tiles': consume_tiles + [discard_tile], 'source': 'someone', 'called_tile': discard_tile})
    
    for drop_cand in set(temp_hand):
        test_hand = temp_hand.copy()
        test_hand.remove(drop_cand)
        machi = get_machi_tiles(test_hand, temp_furo)
        if machi:
            for m in machi:
                agari_hand = test_hand + [m]
                yaku_list, han, fu = judge_yaku(agari_hand, temp_furo, m, False, False, dora_tiles, False, bakaze, jikaze, len(wall), len(discards), ura_indicators=ura_indicators, is_daburi=False)
                if han > 0:
                    return drop_cand
    return None

def cpu_try_naki(request, p, discard_tile, discarder, is_chi):
    discards = request.session.get(f'{p}_discards', [])
    if len(discards) < 8: return None
    if request.session.get(f'{p}_is_riichi', False): return None
    
    hand = request.session.get(f'{p}_hand', [])
    furo = request.session.get(f'{p}_furo', [])
    
    is_kamicha = (discarder == ['jibun', 'shimochi', 'toimen', 'kamicha'][(['jibun', 'shimochi', 'toimen', 'kamicha'].index(p) - 1) % 4])
    
    norm_discard = normalize_tile(discard_tile)
    norm_hand = normalize_hand(hand)
    
    if not is_chi:
        if norm_hand.count(norm_discard) >= 2:
            cands = [t for t in hand if normalize_tile(t) == norm_discard]
            from itertools import combinations
            for pat in set(combinations(cands, 2)):
                consume = list(pat)
                drop_tile = simulate_naki_tenpai(request, p, hand, furo, discard_tile, 'pon', consume)
                if drop_tile:
                    return {'action': 'pon', 'consume': consume, 'drop_tile': drop_tile}
    else:
        if is_kamicha and norm_discard not in JIHAI:
            num = int(norm_discard[0])
            suit = norm_discard[1]
            t_m2, t_m1, t_p1, t_p2 = f"{num-2}{suit}", f"{num-1}{suit}", f"{num+1}{suit}", f"{num+2}{suit}"
            
            chi_patterns = []
            def add_chi(tn1, tn2):
                c1s = [t for t in hand if normalize_tile(t) == tn1]
                c2s = [t for t in hand if normalize_tile(t) == tn2]
                for c1 in set(c1s):
                    for c2 in set(c2s):
                        chi_patterns.append([c1, c2])
            if t_m2 in norm_hand and t_m1 in norm_hand: add_chi(t_m2, t_m1)
            if t_m1 in norm_hand and t_p1 in norm_hand: add_chi(t_m1, t_p1)
            if t_p1 in norm_hand and t_p2 in norm_hand: add_chi(t_p1, t_p2)
            
            for consume in chi_patterns:
                drop_tile = simulate_naki_tenpai(request, p, hand, furo, discard_tile, 'chi', consume)
                if drop_tile:
                    return {'action': 'chi', 'consume': consume, 'drop_tile': drop_tile}
    return None

def execute_cpu_naki_and_discard(request, p, discard_tile, discarder, naki_data):
    action = naki_data['action']
    consume = naki_data['consume']
    drop_tile = naki_data['drop_tile']
    
    hand = request.session.get(f'{p}_hand', [])
    furo = request.session.get(f'{p}_furo', [])
    discards = request.session.get(f'{p}_discards', [])
    
    for t in consume:
        hand.remove(t)
    
    furo.append({'action': action, 'tiles': consume + [discard_tile], 'source': discarder, 'called_tile': discard_tile})
    
    hand.remove(drop_tile)
    discards.append(drop_tile)
    
    request.session[f'{p}_hand'] = hand
    request.session[f'{p}_furo'] = furo
    request.session[f'{p}_discards'] = discards
    request.session['ippatsu_chance'] = False
    request.session['shimochi_ippatsu_chance'] = False
    request.session['toimen_ippatsu_chance'] = False
    request.session['kamicha_ippatsu_chance'] = False
    request.session[f'{p}_doujun_furiten'] = False

    cpu_flags = request.session.get(f'{p}_tsumogiri_flags', [])
    cpu_flags.append(False)
    request.session[f'{p}_tsumogiri_flags'] = cpu_flags
    
    return {
        'cpu_naki': True,
        'naki_player': p,
        'naki_action': action,
        'naki_consume': consume,
        'discard_tile': drop_tile,
        'discarder': p,
        f'{p}_discards': discards,
        f'{p}_tsumogiri_flags': cpu_flags
    }

def check_naki_available(request, hand, discard_tile, is_kamicha, is_riichi):
    kan_count = request.session.get('kan_count', 0)
    wall = request.session.get('wall', [])
    if is_riichi:
        return {'pon': False, 'kan': False, 'chi': False, 'chi_patterns': [], 'pon_patterns': [], 'kan_patterns': []}
        
    norm_discard = normalize_tile(discard_tile)
    norm_hand = normalize_hand(hand)
    pon_patterns = []
    kan_patterns = []
    chi_patterns = []
    
    if norm_hand.count(norm_discard) >= 2:
        cands = [t for t in hand if normalize_tile(t) == norm_discard]
        from itertools import combinations
        for p in set(combinations(cands, 2)):
            pon_patterns.append(list(p) + [discard_tile])

    if norm_hand.count(norm_discard) >= 3 and kan_count < 4 and len(wall) > 0:
        cands = [t for t in hand if normalize_tile(t) == norm_discard]
        from itertools import combinations
        for p in set(combinations(cands, 3)):
            kan_patterns.append(list(p) + [discard_tile])
            
    if is_kamicha and norm_discard not in JIHAI:
        num = int(norm_discard[0])
        suit = norm_discard[1]
        t_m2, t_m1, t_p1, t_p2 = f"{num-2}{suit}", f"{num-1}{suit}", f"{num+1}{suit}", f"{num+2}{suit}"
        
        def add_chi_combs(tn1, tn2):
            c1s = [t for t in hand if normalize_tile(t) == tn1]
            c2s = [t for t in hand if normalize_tile(t) == tn2]
            for c1 in set(c1s):
                for c2 in set(c2s):
                    chi_patterns.append([c1, c2, discard_tile])

        if t_m2 in norm_hand and t_m1 in norm_hand: add_chi_combs(t_m2, t_m1)
        if t_m1 in norm_hand and t_p1 in norm_hand: add_chi_combs(t_m1, t_p1)
        if t_p1 in norm_hand and t_p2 in norm_hand: add_chi_combs(t_p1, t_p2)
            
    return {
        'pon': len(pon_patterns) > 0, 'kan': len(kan_patterns) > 0, 'chi': len(chi_patterns) > 0,
        'chi_patterns': chi_patterns, 'pon_patterns': pon_patterns, 'kan_patterns': kan_patterns
    }

def count_visible_tiles(request):
    jibun_hand = request.session.get('jibun_hand', [])
    furos = request.session.get('jibun_furo', []) + request.session.get('shimochi_furo', []) + request.session.get('toimen_furo', []) + request.session.get('kamicha_furo', [])
    discards = request.session.get('jibun_discards', []) + request.session.get('shimochi_discards', []) + request.session.get('toimen_discards', []) + request.session.get('kamicha_discards', [])
    dora_indicators = request.session.get('dora_indicators', [])
    
    visible = {}
    for t in jibun_hand + discards + dora_indicators + get_flat_furo_tiles(furos):
        if t: visible[normalize_tile(t)] = visible.get(normalize_tile(t), 0) + 1
    return visible

def count_visible_tiles_for_cpu(request, cpu_name):
    cpu_hand = request.session.get(f'{cpu_name}_hand', [])
    furos = request.session.get('jibun_furo', []) + request.session.get('shimochi_furo', []) + request.session.get('toimen_furo', []) + request.session.get('kamicha_furo', [])
    discards = request.session.get('jibun_discards', []) + request.session.get('shimochi_discards', []) + request.session.get('toimen_discards', []) + request.session.get('kamicha_discards', [])
    dora_indicators = request.session.get('dora_indicators', [])
    
    visible = {}
    for t in cpu_hand + discards + dora_indicators + get_flat_furo_tiles(furos):
        if t: visible[normalize_tile(t)] = visible.get(normalize_tile(t), 0) + 1
    return visible

def get_current_machi_info(request, hand, furo_list=[]):
    machi_tiles = []
    current_count = len(hand)
    if current_count in [1, 4, 7, 10, 13]:
        machi_tiles = get_machi_tiles(hand, furo_list)
    elif current_count in [2, 5, 8, 11, 14]:
        for tile in set(hand):
            temp = hand.copy()
            temp.remove(tile)
            machi_tiles.extend(get_machi_tiles(temp, furo_list))
        machi_tiles = list(set(machi_tiles))
        
    if not machi_tiles: return []
    visible = count_visible_tiles(request)
    machi_info = []
    for tile in machi_tiles:
        rem = 4 - visible.get(tile, 0)
        if rem < 0: rem = 0
        machi_info.append({'tile': tile, 'count': rem})
    return machi_info

def handle_ryukyoku(request):
    kyoku = request.session.get('kyoku', 1)
    honba = request.session.get('honba', 0)
    kyotaku = request.session.get('kyotaku', 0)
    scores = request.session.get('scores', {})
    jibun_furo = request.session.get('jibun_furo', [])
    oya_order = ['jibun', 'shimochi', 'toimen', 'kamicha']
    oya = oya_order[(kyoku - 1) % 4]
    
    tenpai_status = {}
    points_diff = {'jibun': 0, 'shimochi': 0, 'toimen': 0, 'kamicha': 0}
    for p in oya_order:
        hand = request.session.get(f'{p}_hand', [])
        furo = jibun_furo if p == 'jibun' else request.session.get(f'{p}_furo', [])
        if get_machi_tiles(hand, furo): tenpai_status[p] = True
        else: tenpai_status[p] = False
            
    tenpai_players = [p for p, t in tenpai_status.items() if t]
    noten_players = [p for p, t in tenpai_status.items() if not t]
    num_tenpai = len(tenpai_players)
    
    name_map = {'jibun': '自分', 'shimochi': '下家', 'toimen': '対面', 'kamicha': '上家'}
    tenpai_names = [name_map[p] for p in tenpai_players]
    noten_names = [name_map[p] for p in noten_players]
    
    log_msg = "全員ノーテンまたは全員テンパイにより、点数移動はありません。"
    if num_tenpai == 1:
        for p in noten_players: points_diff[p] -= 1000
        for p in tenpai_players: points_diff[p] += 3000
        log_msg = f"【テンパイ】{tenpai_names[0]} (+3000点)\n【ノーテン】他の3名 (-1000点)"
    elif num_tenpai == 2:
        for p in noten_players: points_diff[p] -= 1500
        for p in tenpai_players: points_diff[p] += 1500
        log_msg = f"【テンパイ】{', '.join(tenpai_names)} (+1500点)\n【ノーテン】{', '.join(noten_names)} (-1500点)"
    elif num_tenpai == 3:
        for p in noten_players: points_diff[p] -= 3000
        for p in tenpai_players: points_diff[p] += 1000
        log_msg = f"【テンパイ】3名 (+1000点)\n【ノーテン】{noten_names[0]} (-3000点)"
        
    if tenpai_status[oya]:
        next_kyoku = kyoku
        next_honba = honba + 1
        result_msg = f"流局（親テンパイにより連荘）\n{log_msg}"
    else:
        next_kyoku = kyoku + 1
        next_honba = honba + 1
        result_msg = f"流局（親ノーテンにより親移動）\n{log_msg}"
        
    cpu_hands = { 'shimochi': request.session.get('shimochi_hand', []), 'toimen': request.session.get('toimen_hand', []), 'kamicha': request.session.get('kamicha_hand', []) }
        
    return JsonResponse({ 'is_ryukyoku': True, 'result_msg': result_msg, 'points_diff': points_diff, 'next_kyoku': next_kyoku, 'next_honba': next_honba, 'next_kyotaku': kyotaku, 'current_kyotaku': kyotaku, 'cpu_hands': cpu_hands })

def handle_post_discard(request, discard_tile, discarder, base_response_data):
    for p in ['jibun', 'shimochi', 'toimen', 'kamicha']:
        base_response_data[f'{p}_furo'] = request.session.get(f'{p}_furo', [])
        base_response_data[f'{p}_discards'] = request.session.get(f'{p}_discards', [])
        base_response_data[f'{p}_tsumogiri_flags'] = request.session.get(f'{p}_tsumogiri_flags', [])
        if p != 'jibun':
            base_response_data[f'{p}_hand_len'] = len(request.session.get(f'{p}_hand', []))

    ron_players = get_ron_players(request, discard_tile, discarder)
    if ron_players:
        jibun_in_ron = any(r['player'] == 'jibun' for r in ron_players)
        if jibun_in_ron:
            res = process_multi_ron_data(request, ron_players, discarder)
            base_response_data.update(res)
            base_response_data['cpu_just_ron'] = False
            base_response_data['ron_available'] = True
            cpu_only_players = [r for r in ron_players if r['player'] != 'jibun']
            if cpu_only_players:
                base_response_data['cpu_pass_ron_data'] = process_multi_ron_data(request, cpu_only_players, discarder)
        else:
            res = process_multi_ron_data(request, ron_players, discarder)
            base_response_data.update(res)
            base_response_data['cpu_just_ron'] = True
        
        base_response_data['next_turn_player'] = ['jibun', 'shimochi', 'toimen', 'kamicha'][(['jibun', 'shimochi', 'toimen', 'kamicha'].index(discarder) + 1) % 4]
        return base_response_data

    players = ['jibun', 'shimochi', 'toimen', 'kamicha']
    idx = players.index(discarder)
    pon_players_order = [players[(idx+1)%4], players[(idx+2)%4], players[(idx+3)%4]]
    
    for p in pon_players_order:
        if p == 'jibun': continue
        naki_data = cpu_try_naki(request, p, discard_tile, discarder, False)
        if naki_data:
            naki_res = execute_cpu_naki_and_discard(request, p, discard_tile, discarder, naki_data)
            base_response_data.update(naki_res)
            return handle_post_discard(request, naki_res['discard_tile'], p, base_response_data)

    if 'jibun' in pon_players_order:
        jibun_hand = request.session.get('jibun_hand', [])
        jibun_is_riichi = request.session.get('is_jibun_riichi', False)
        is_kamicha = (discarder == 'kamicha')
        naki_info = check_naki_available(request, jibun_hand, discard_tile, is_kamicha, jibun_is_riichi)
        if naki_info['pon'] or naki_info['kan']:
            base_response_data['naki_info'] = naki_info
            base_response_data['next_turn_player'] = players[(idx + 1) % 4]
            return base_response_data

    chi_player = players[(idx+1)%4]
    if chi_player != 'jibun':
        naki_data = cpu_try_naki(request, chi_player, discard_tile, discarder, True)
        if naki_data:
            naki_res = execute_cpu_naki_and_discard(request, chi_player, discard_tile, discarder, naki_data)
            base_response_data.update(naki_res)
            return handle_post_discard(request, naki_res['discard_tile'], chi_player, base_response_data)
    else:
        jibun_hand = request.session.get('jibun_hand', [])
        jibun_is_riichi = request.session.get('is_jibun_riichi', False)
        naki_info = check_naki_available(request, jibun_hand, discard_tile, True, jibun_is_riichi)
        if naki_info['chi']:
            base_response_data['naki_info'] = naki_info
            base_response_data['next_turn_player'] = chi_player
            return base_response_data

    base_response_data['next_turn_player'] = players[(players.index(discarder) + 1) % 4]
    return base_response_data

def game_mahjong(request):
    kyoku = request.session.get('kyoku', 1)
    honba = request.session.get('honba', 0)
    kyotaku = request.session.get('kyotaku', 0)
    scores = request.session.get('scores', {'jibun': 25000, 'shimochi': 25000, 'toimen': 25000, 'kamicha': 25000})
    
    if kyoku > 8 or request.GET.get('reset') == 'true':
        kyoku = 1
        honba = 0
        kyotaku = 0
        scores = {'jibun': 25000, 'shimochi': 25000, 'toimen': 25000, 'kamicha': 25000}
        request.session['game_log'] = []
        
    oya_order = ['jibun', 'shimochi', 'toimen', 'kamicha']
    oya = oya_order[(kyoku - 1) % 4]
    
    wall = BASE_TILES * 4
    wall.remove("5萬"); wall.append("赤5萬")
    wall.remove("5筒"); wall.append("赤5筒")
    wall.remove("5索"); wall.append("赤5索")
    random.shuffle(wall)
    
    jibun_hand    = sorted(wall[0:13], key=lambda tile: TILE_ORDER[tile])
    shimochi_hand = sorted(wall[13:26], key=lambda tile: TILE_ORDER[tile])
    toimen_hand   = sorted(wall[26:39], key=lambda tile: TILE_ORDER[tile])
    kamicha_hand  = sorted(wall[39:52], key=lambda tile: TILE_ORDER[tile])
    
    wanpai = wall[52:66]
    request.session['rinshan_tiles'] = wanpai[0:4]
    dora_indicators = [wanpai[4]]
    ura_indicators = [wanpai[5]]
    request.session['reserve_dora'] = [wanpai[6], wanpai[8], wanpai[10]]
    request.session['reserve_ura'] = [wanpai[7], wanpai[9], wanpai[11]]
    
    dora_tile = get_dora_tile(dora_indicators[0])
    
    request.session['wall'] = wall[66:]
    request.session['jibun_hand'] = jibun_hand
    request.session['jibun_furo'] = []
    request.session['shimochi_hand'] = shimochi_hand
    request.session['shimochi_furo'] = []
    request.session['toimen_hand'] = toimen_hand
    request.session['toimen_furo'] = []
    request.session['kamicha_hand'] = kamicha_hand
    request.session['kamicha_furo'] = []
    
    request.session['jibun_discards'] = []
    request.session['shimochi_discards'] = []
    request.session['toimen_discards'] = []
    request.session['kamicha_discards'] = []
    
    request.session['jibun_tsumogiri_flags'] = []
    request.session['shimochi_tsumogiri_flags'] = []
    request.session['toimen_tsumogiri_flags'] = []
    request.session['kamicha_tsumogiri_flags'] = []
    
    request.session['is_jibun_riichi'] = False
    request.session['shimochi_is_riichi'] = False
    request.session['toimen_is_riichi'] = False
    request.session['kamicha_is_riichi'] = False
    
    request.session['is_jibun_daburi'] = False
    request.session['shimochi_is_daburi'] = False
    request.session['toimen_is_daburi'] = False
    request.session['kamicha_is_daburi'] = False

    request.session['jibun_just_riichi'] = False
    request.session['shimochi_just_riichi'] = False
    request.session['toimen_just_riichi'] = False
    request.session['kamicha_just_riichi'] = False
    
    request.session['ippatsu_chance'] = False
    request.session['shimochi_ippatsu_chance'] = False
    request.session['toimen_ippatsu_chance'] = False
    request.session['kamicha_ippatsu_chance'] = False
    
    request.session['kan_count'] = 0
    
    request.session['jibun_doujun_furiten'] = False
    request.session['jibun_riichi_furiten'] = False
    request.session['missed_ron_candidate'] = False
    request.session['shimochi_doujun_furiten'] = False
    request.session['shimochi_riichi_furiten'] = False
    request.session['toimen_doujun_furiten'] = False
    request.session['toimen_riichi_furiten'] = False
    request.session['kamicha_doujun_furiten'] = False
    request.session['kamicha_riichi_furiten'] = False
    
    request.session['dora_indicators'] = dora_indicators
    request.session['ura_indicators'] = ura_indicators
    request.session['kyoku'] = kyoku
    request.session['honba'] = honba
    request.session['kyotaku'] = kyotaku
    request.session['scores'] = scores
    
    kyoku_name = f"{'東' if kyoku <= 4 else '南'}{(kyoku - 1) % 4 + 1}局"
    jibun_hand_data = [{'raw': t, 'text': normalize_tile(t), 'is_aka': '赤' in t, 'is_dora': normalize_tile(t) == dora_tile} for t in jibun_hand]
    
    return render(request, 'chat/game_mahjong.html', {
        'hand': jibun_hand_data,
        'dora_indicators': json.dumps(dora_indicators),
        'dora_tiles': json.dumps([get_dora_tile(ind) for ind in dora_indicators]),
        'scores': scores,
        'kyoku_name': kyoku_name,
        'honba': honba,
        'kyotaku': kyotaku,
        'oya': oya,
        'game_log': request.session.get('game_log', [])
    })

def tsumo(request):
    for p in ['jibun', 'shimochi', 'toimen', 'kamicha']:
        request.session[f'{p}_just_riichi'] = False
        if request.session.get(f'{p}_missed_ron_candidate'):
            request.session[f'{p}_doujun_furiten'] = True
            is_r = request.session.get('is_jibun_riichi' if p == 'jibun' else f'{p}_is_riichi', False)
            if is_r:
                request.session[f'{p}_riichi_furiten'] = True
            request.session[f'{p}_missed_ron_candidate'] = False

    request.session['jibun_doujun_furiten'] = False

    wall = request.session.get('wall', [])
    jibun_hand = request.session.get('jibun_hand', [])
    jibun_furo = request.session.get('jibun_furo', [])
    jibun_discards = request.session.get('jibun_discards', [])
    is_riichi = request.session.get('is_jibun_riichi', False)
    is_daburi = request.session.get('is_jibun_daburi', False)
    ippatsu_chance = request.session.get('ippatsu_chance', False)
    request.session['ippatsu_chance'] = False
    
    is_rinshan = request.session.get('is_rinshan', False)
    kyoku = request.session.get('kyoku', 1)
    honba = request.session.get('honba', 0)
    kyotaku = request.session.get('kyotaku', 0)
    dora_indicators = request.session.get('dora_indicators', [])
    dora_tiles = [get_dora_tile(ind) for ind in dora_indicators]
    ura_indicators = request.session.get('ura_indicators', [])
    
    if len(wall) == 0: return handle_ryukyoku(request)
    
    tsumo_tile = wall.pop(0)
    jibun_hand.append(tsumo_tile)
    request.session['wall'] = wall
    request.session['jibun_hand'] = jibun_hand
    request.session['is_rinshan'] = False
    
    can_riichi = False
    riichi_declarable_tiles = []
    scores = request.session.get('scores', {})
    jibun_score = scores.get('jibun', 25000)
    
    is_jibun_menzen = len([f for f in jibun_furo if f.get('action') != 'ankan']) == 0
    if not is_riichi and is_jibun_menzen and jibun_score >= 1100:
        for tile in set(jibun_hand):
            temp_hand = jibun_hand.copy()
            temp_hand.remove(tile)
            if get_machi_tiles(temp_hand, jibun_furo):
                can_riichi = True
                riichi_declarable_tiles.append(tile)
                
    can_win = is_win(jibun_hand, jibun_furo)
    score_result = ""
    points_diff = {}
    next_kyoku = kyoku
    next_honba = honba
    next_kyotaku = kyotaku
    cpu_hands = {}
    
    ankan_patterns = []
    kakan_patterns = []
    kan_count = request.session.get('kan_count', 0)
    
    if not is_riichi and kan_count < 4 and len(wall) > 0:
        norm_full_hand = normalize_hand(jibun_hand)
        checked_tiles = set()
        for tile in jibun_hand:
            norm_t = normalize_tile(tile)
            if norm_t not in checked_tiles:
                if norm_full_hand.count(norm_t) == 4:
                    ankan_patterns.append([t for t in jibun_hand if normalize_tile(t) == norm_t])
                checked_tiles.add(norm_t)
        
        for f in jibun_furo:
            if f.get('action') == 'pon':
                pon_norm = normalize_tile(f['tiles'][0])
                if pon_norm in normalize_hand(jibun_hand):
                    added_t = [t for t in jibun_hand if normalize_tile(t) == pon_norm][0]
                    kakan_patterns.append(added_t)
    
    if can_win:
        bakaze = get_bakaze(kyoku)
        jikaze = get_jikaze(kyoku, 'jibun')
        yaku_list, han, fu = judge_yaku(jibun_hand, jibun_furo, tsumo_tile, True, is_riichi, dora_tiles, ippatsu_chance, bakaze, jikaze, len(wall), len(jibun_discards), is_rinshan=is_rinshan, ura_indicators=ura_indicators, is_daburi=is_daburi)
        
        if han > 0:
            oya_order = ['jibun', 'shimochi', 'toimen', 'kamicha']
            oya = oya_order[(kyoku - 1) % 4]
            is_oya = (oya == 'jibun')
            
            score_result, total_points = calc_points(han, fu, is_oya, True, honba, kyotaku)
            yaku_str = "、".join([y[0] for y in yaku_list])
            
            if han >= 13: basic_points = 8000
            elif han >= 11: basic_points = 6000
            elif han >= 8: basic_points = 4000
            elif han >= 6: basic_points = 3000
            else:
                basic_points = fu * (2 ** (han + 2))
                if basic_points >= 1920: basic_points = 2000
                
            points_diff = {'jibun': 0, 'shimochi': 0, 'toimen': 0, 'kamicha': 0}
            if is_oya:
                all_pay = math.ceil(basic_points * 2 / 100) * 100 + 100 * honba
                points_diff['jibun'] = all_pay * 3 + kyotaku * 1000
                points_diff['shimochi'] = -all_pay
                points_diff['toimen'] = -all_pay
                points_diff['kamicha'] = -all_pay
                next_honba = honba + 1
            else:
                oya_pay = math.ceil(basic_points * 2 / 100) * 100 + 100 * honba
                ko_pay = math.ceil(basic_points / 100) * 100 + 100 * honba
                points_diff['jibun'] = oya_pay + ko_pay * 2 + kyotaku * 1000
                for p in oya_order:
                    if p != 'jibun': points_diff[p] = -oya_pay if p == oya else -ko_pay
                next_kyoku = kyoku + 1
                next_honba = 0

            temp_hand = jibun_hand.copy()
            if tsumo_tile in temp_hand: temp_hand.remove(tsumo_tile)
            machi_list = get_machi_tiles(temp_hand, jibun_furo)
            machi_str = "、".join(machi_list)

            current_scores = request.session.get('scores', {'jibun': 25000, 'shimochi': 25000, 'toimen': 25000, 'kamicha': 25000})
            movement_text = make_score_movement_text(current_scores, points_diff)

            score_result = f"自分のツモアガリ！\n{score_result}\n{han}翻 {fu}符\n[{yaku_str}]\n【待ち牌】: {machi_str}{movement_text}"
            
            if is_riichi or is_daburi:
                ura_inds_str = " ".join([normalize_tile(ind) for ind in ura_indicators])
                score_result += f"\n(裏ドラ表示牌: {ura_inds_str})"
            next_kyotaku = 0
            cpu_hands = { 'shimochi': request.session.get('shimochi_hand', []), 'toimen': request.session.get('toimen_hand', []), 'kamicha': request.session.get('kamicha_hand', []) }
        else:
            can_win = False
            
    machi_info = get_current_machi_info(request, jibun_hand, jibun_furo)
    tile_class = 'manzu' if '萬' in tsumo_tile else 'pinzu' if '筒' in tsumo_tile else 'souzu' if '索' in tsumo_tile else 'jihai'
    is_furiten = get_jibun_furiten_status(request, jibun_hand, jibun_furo, jibun_discards)
    
    return JsonResponse({
        'tile': tsumo_tile, 'tile_class': tile_class, 'can_riichi': can_riichi,
        'riichi_declarable_tiles': riichi_declarable_tiles, 'is_already_riichi': is_riichi,
        'can_win': can_win, 'score_result': score_result, 'points_diff': points_diff,
        'next_kyoku': next_kyoku, 'next_honba': next_honba, 'next_kyotaku': next_kyotaku,
        'current_kyotaku': kyotaku, 'machi_info': machi_info, 'cpu_hands': cpu_hands,
        'dora_indicators': dora_indicators, 'dora_tiles': dora_tiles, 'is_furiten': is_furiten,
        'ankan_patterns': ankan_patterns, 'kakan_patterns': kakan_patterns
    })

def declare_riichi(request):
    request.session['is_jibun_riichi'] = True
    request.session['ippatsu_chance'] = True
    request.session['jibun_just_riichi'] = True
    
    jibun_discards = request.session.get('jibun_discards', [])
    furos = request.session.get('jibun_furo', []) + request.session.get('shimochi_furo', []) + request.session.get('toimen_furo', []) + request.session.get('kamicha_furo', [])
    if len(jibun_discards) == 0 and len(furos) == 0:
        request.session['is_jibun_daburi'] = True
    else:
        request.session['is_jibun_daburi'] = False
        
    scores = request.session.get('scores', {})
    if 'jibun' in scores: scores['jibun'] -= 1000
    request.session['scores'] = scores
    kyotaku = request.session.get('kyotaku', 0)
    request.session['kyotaku'] = kyotaku + 1
    return JsonResponse({'status': 'success', 'current_kyotaku': kyotaku + 1})

def declare_naki(request):
    for p in ['jibun', 'shimochi', 'toimen', 'kamicha']:
        request.session[f'{p}_just_riichi'] = False
        if request.session.get(f'{p}_missed_ron_candidate'):
            request.session[f'{p}_doujun_furiten'] = True
            is_r = request.session.get('is_jibun_riichi' if p == 'jibun' else f'{p}_is_riichi', False)
            if is_r:
                request.session[f'{p}_riichi_furiten'] = True
            request.session[f'{p}_missed_ron_candidate'] = False

    request.session['jibun_doujun_furiten'] = False

    action = request.GET.get('action')
    tile = request.GET.get('tile')
    source = request.GET.get('source')
    pattern_str = request.GET.get('pattern', '[]')
    
    jibun_hand = request.session.get('jibun_hand', [])
    jibun_furo = request.session.get('jibun_furo', [])
    consume_tiles = json.loads(pattern_str)
    
    source_discards = []
    if source:
        source_discards = request.session.get(f'{source}_discards', [])
        if source_discards and source_discards[-1] == tile:
            source_discards.pop()
            request.session[f'{source}_discards'] = source_discards
            source_flags = request.session.get(f'{source}_tsumogiri_flags', [])
            if source_flags:
                source_flags.pop()
                request.session[f'{source}_tsumogiri_flags'] = source_flags
    
    request.session['ippatsu_chance'] = False
    request.session['shimochi_ippatsu_chance'] = False
    request.session['toimen_ippatsu_chance'] = False
    request.session['kamicha_ippatsu_chance'] = False
    
    for t in consume_tiles:
        jibun_hand.remove(t)

    if action == 'kakan':
        jibun_hand.remove(tile)

    if action in ['kan', 'ankan', 'kakan']:
        kan_count = request.session.get('kan_count', 0)
        if kan_count < 4:
            rinshan_tiles = request.session.get('rinshan_tiles', [])
            reserve_dora = request.session.get('reserve_dora', [])
            reserve_ura = request.session.get('reserve_ura', [])
            dora_indicators = request.session.get('dora_indicators', [])
            ura_indicators = request.session.get('ura_indicators', [])
            wall = request.session.get('wall', [])
            
            if rinshan_tiles:
                rinshan_tile = rinshan_tiles.pop(0)
                jibun_hand.append(rinshan_tile)
                request.session['rinshan_tiles'] = rinshan_tiles
            
            if reserve_dora:
                dora_indicators.append(reserve_dora.pop(0))
                request.session['reserve_dora'] = reserve_dora
                request.session['dora_indicators'] = dora_indicators
            
            if reserve_ura:
                ura_indicators.append(reserve_ura.pop(0))
                request.session['reserve_ura'] = reserve_ura
                request.session['ura_indicators'] = ura_indicators
                
            if wall:
                wall.pop()
                request.session['wall'] = wall
                
            request.session['kan_count'] = kan_count + 1
            
        if action == 'ankan':
            jibun_furo.append({'action': 'ankan', 'tiles': consume_tiles, 'source': 'jibun', 'called_tile': consume_tiles[0]})
        elif action == 'kakan':
            for f in jibun_furo:
                if f.get('action') == 'pon' and normalize_tile(f['tiles'][0]) == normalize_tile(tile):
                    f['action'] = 'kakan'
                    f['tiles'].append(tile)
                    f['called_tile'] = tile
                    break
        elif action == 'kan':
            jibun_furo.append({'action': 'kan', 'tiles': consume_tiles + [tile], 'source': source, 'called_tile': tile})
            
        request.session['is_rinshan'] = True
    else:
        jibun_furo.append({'action': action, 'tiles': consume_tiles + [tile], 'source': source, 'called_tile': tile})
        
    request.session['jibun_hand'] = jibun_hand
    request.session['jibun_furo'] = jibun_furo
    machi_info = get_current_machi_info(request, jibun_hand, jibun_furo)
    current_dora_inds = request.session.get('dora_indicators', [])
    jibun_discards = request.session.get('jibun_discards', [])
    is_furiten = get_jibun_furiten_status(request, jibun_hand, jibun_furo, jibun_discards)
    
    return JsonResponse({
        'hand': jibun_hand, 'furo': jibun_furo, 'machi_info': machi_info, 
        'source': source, 'source_discards': source_discards,
        'source_tsumogiri_flags': request.session.get(f'{source}_tsumogiri_flags', []),
        'dora_indicators': current_dora_inds, 'dora_tiles': [get_dora_tile(ind) for ind in current_dora_inds],
        'is_furiten': is_furiten
    })

def check_agari(request):
    tiles = request.GET.getlist('tiles[]')
    is_tsumo = request.GET.get('is_tsumo') == 'true'
    dora_indicators = request.session.get('dora_indicators', [])
    dora_tiles = [get_dora_tile(ind) for ind in dora_indicators]
    ura_indicators = request.session.get('ura_indicators', [])
    is_riichi = request.session.get('is_jibun_riichi', False)
    is_daburi = request.session.get('is_jibun_daburi', False)
    ippatsu_chance = request.session.get('ippatsu_chance', False)
    jibun_furo = request.session.get('jibun_furo', [])
    jibun_discards = request.session.get('jibun_discards', [])
    wall = request.session.get('wall', [])
    kyoku = request.session.get('kyoku', 1)
    honba = request.session.get('honba', 0)
    kyotaku = request.session.get('kyotaku', 0)
    agari_tile = tiles[-1]
    
    can_win = is_win(tiles, jibun_furo)
    score_result = ""
    
    if can_win:
        bakaze = get_bakaze(kyoku)
        jikaze = get_jikaze(kyoku, 'jibun')
        yaku_list, han, fu = judge_yaku(tiles, jibun_furo, agari_tile, is_tsumo, is_riichi, dora_tiles, ippatsu_chance, bakaze, jikaze, len(wall), len(jibun_discards), ura_indicators=ura_indicators, is_daburi=is_daburi)
        
        if han > 0:
            oya_order = ['jibun', 'shimochi', 'toimen', 'kamicha']
            oya = oya_order[(kyoku - 1) % 4]
            is_oya = (oya == 'jibun')
            score_result, _ = calc_points(han, fu, is_oya, is_tsumo, honba, kyotaku)
            yaku_str = "、".join([y[0] for y in yaku_list])
            score_result = f"{score_result}\n{han}翻 {fu}符\n[{yaku_str}]"
            
            if is_riichi or is_daburi:
                ura_inds_str = " ".join([normalize_tile(ind) for ind in ura_indicators])
                score_result += f"\n(裏ドラ表示牌: {ura_inds_str})"
        else:
            can_win = False
            score_result = "役がありません"
            
    return JsonResponse({'can_win': can_win, 'score_result': score_result})

def get_approx_shanten(hand, furo_count=0):
    norm_hand = normalize_hand(hand)
    counts = {t: norm_hand.count(t) for t in set(norm_hand)}
    
    pairs = sum(1 for c in counts.values() if c >= 2)
    
    temp_hand = sorted(norm_hand, key=lambda x: TILE_ORDER[x])
    mentsu = 0
    taatsu = 0
    
    for t, c in counts.items():
        if c >= 3:
            mentsu += 1
            for _ in range(3): temp_hand.remove(t)
            
    i = 0
    while i < len(temp_hand):
        t1 = temp_hand[i]
        if t1 not in JIHAI:
            num = int(t1[0])
            suit = t1[1]
            t2 = f"{num+1}{suit}"
            t3 = f"{num+2}{suit}"
            if t2 in temp_hand and t3 in temp_hand:
                mentsu += 1
                temp_hand.remove(t1)
                temp_hand.remove(t2)
                temp_hand.remove(t3)
                continue
        i += 1
        
    i = 0
    while i < len(temp_hand):
        t1 = temp_hand[i]
        if temp_hand.count(t1) >= 2:
            taatsu += 1
            temp_hand.remove(t1)
            temp_hand.remove(t1)
            continue
        if t1 not in JIHAI:
            num = int(t1[0])
            suit = t1[1]
            t2 = f"{num+1}{suit}"
            t3 = f"{num+2}{suit}"
            if t2 in temp_hand:
                taatsu += 1
                temp_hand.remove(t1)
                temp_hand.remove(t2)
                continue
            if t3 in temp_hand:
                taatsu += 1
                temp_hand.remove(t1)
                temp_hand.remove(t3)
                continue
        i += 1
        
    mentsu += furo_count
    if mentsu + taatsu > 4:
        taatsu = 4 - mentsu
        
    shanten_standard = 8 - (mentsu * 2) - taatsu - (1 if pairs > 0 else 0)
    shanten_chiitoi = 6 - pairs
    
    return min(shanten_standard, shanten_chiitoi)

def get_safety_rank(tile, genbutsu_set, visible_counts):
    nt = normalize_tile(tile)
    if nt in genbutsu_set:
        return 0
        
    rem_count = 4 - visible_counts.get(nt, 0)
    if rem_count == 0:
        return 0 
        
    if nt in JIHAI:
        if rem_count == 1: return 1
        if rem_count == 2: return 2
        return 3
        
    num = int(nt[0])
    suit = nt[1]
    
    is_suji = False
    if num in [1, 4, 7]:
        if f"4{suit}" in genbutsu_set: is_suji = True
    elif num in [2, 5, 8]:
        if f"5{suit}" in genbutsu_set: is_suji = True
    elif num in [3, 6, 9]:
        if f"6{suit}" in genbutsu_set: is_suji = True
        
    if is_suji:
        if num in [1, 9]: return 4
        if num in [2, 8]: return 5
        return 6
        
    if num in [1, 9]: return 7
    if num in [2, 8]: return 8
    return 9

def select_best_discard(request, p, hand):
    kyoku = request.session.get('kyoku', 1)
    bakaze = get_bakaze(kyoku)
    jikaze = get_jikaze(kyoku, p)
    dora_indicators = request.session.get('dora_indicators', [])
    dora_tiles = [get_dora_tile(ind) for ind in dora_indicators]
    visible_counts = count_visible_tiles_for_cpu(request, p)
    furo = request.session.get('jibun_furo' if p == 'jibun' else f'{p}_furo', [])
    
    tile_scores = []
    norm_hand = normalize_hand(hand)
    counts = {t: norm_hand.count(t) for t in set(norm_hand)}
    pair_count = sum(1 for c in counts.values() if c >= 2)
    
    chiitoitsu_mode = (pair_count >= 5)

    for tile in hand:
        score = 0
        nt = normalize_tile(tile)
        count = norm_hand.count(nt)
        
        if chiitoitsu_mode:
            if count >= 2:
                score += 10000
            else:
                rem_count = 4 - visible_counts.get(nt, 0)
                
                if rem_count <= 0:
                    score -= 10000
                elif rem_count == 1:
                    score -= 2000
                else:
                    if rem_count == 2:
                        score += 300
                    elif rem_count == 3:
                        score += 100
                    
                    if nt in JIHAI:
                        score += 800
                    else:
                        num = int(nt[0])
                        if num in [1, 9]:
                            score += 600
                        elif num in [2, 8]:
                            score += 200
                        elif num in [3, 7]:
                            score += 100
                        else:
                            score += 0
                    
                    if nt in dora_tiles:
                        score += 500
                        
            if '赤' in tile:
                score += 100
        else:
            if '赤' in tile: score += 50 
            if nt in JIHAI:
                score += 10
                if nt == bakaze and nt == jikaze:
                    score += 40
                elif nt == bakaze and nt != jikaze:
                    score -= 10
                elif nt == jikaze:
                    score += 20
                elif nt in ["白", "發", "中"]:
                    score += 15
                    
                if count == 2: score += 80
                elif count >= 3: score += 200
            else:
                num = int(nt[0])
                suit = nt[1]
                
                if num in [1, 9]: score += 20
                elif num in [2, 8]: score += 30
                else: score += 40
                
                if count == 2: score += 80
                elif count >= 3: score += 200
                
                has_m2 = f"{num-2}{suit}" in norm_hand
                has_m1 = f"{num-1}{suit}" in norm_hand
                has_p1 = f"{num+1}{suit}" in norm_hand
                has_p2 = f"{num+2}{suit}" in norm_hand
                
                is_mentsu = (has_m1 and has_p1) or (has_p1 and has_p2) or (has_m1 and has_m2)
                if is_mentsu:
                    score += 200
                else:
                    if (2 <= num <= 7 and has_p1) or (3 <= num <= 8 and has_m1):
                        score += 100
                    
                    if (num == 1 and has_p1) or (num == 9 and has_m1):
                        score += 40
                    if (num == 2 and has_m1) or (num == 8 and has_p1):
                        score += 20

                    if has_p2:
                        if num + 2 <= 5:
                            score += 70
                        elif num >= 5:
                            score += 40
                        else:
                            score += 55
                    
                    if has_m2:
                        if num <= 5:
                            score += 40
                        elif num - 2 >= 5:
                            score += 70
                        else:
                            score += 55

                    if not any([has_m2, has_m1, has_p1, has_p2]) and count == 1:
                        score -= 10
        
        tile_scores.append((tile, score))

    riichi_players = []
    for other in ['jibun', 'shimochi', 'toimen', 'kamicha']:
        if other != p and request.session.get('is_jibun_riichi' if other == 'jibun' else f'{other}_is_riichi', False):
            riichi_players.append(other)
            
    if riichi_players:
        shanten = get_approx_shanten(hand, len(furo))
        if shanten >= 3:
            genbutsu_set = set()
            for rp in riichi_players:
                for t in request.session.get(f'{rp}_discards', []):
                    genbutsu_set.add(normalize_tile(t))
            
            defense_scores = []
            for tile, off_score in tile_scores:
                safety_rank = get_safety_rank(tile, genbutsu_set, visible_counts)
                defense_scores.append((tile, safety_rank, off_score))
            
            min_safety = min(s[1] for s in defense_scores)
            best_defense_cands = [s for s in defense_scores if s[1] == min_safety]
            min_off = min(s[2] for s in best_defense_cands)
            final_cands = [s[0] for s in best_defense_cands if s[2] == min_off]
            return random.choice(final_cands)

    min_score = min(score for tile, score in tile_scores)
    candidates = [tile for tile, score in tile_scores if score == min_score]
    return random.choice(candidates)

def player_discard(request):
    request.session['jibun_doujun_furiten'] = False

    my_discard = request.GET.get('tile')
    is_tsumogiri = request.GET.get('tsumogiri') == 'true'
    
    jibun_hand = request.session.get('jibun_hand', [])
    jibun_furo = request.session.get('jibun_furo', [])
    jibun_discards = request.session.get('jibun_discards', [])
    jibun_flags = request.session.get('jibun_tsumogiri_flags', [])
    
    if my_discard:
        if my_discard in jibun_hand: jibun_hand.remove(my_discard)
        jibun_discards.append(my_discard)
        jibun_flags.append(is_tsumogiri)
        
    request.session['jibun_hand'] = jibun_hand
    request.session['jibun_discards'] = jibun_discards
    request.session['jibun_tsumogiri_flags'] = jibun_flags
    
    machi_info = get_current_machi_info(request, jibun_hand, jibun_furo)
    current_dora_inds = request.session.get('dora_indicators', [])
    is_furiten = get_jibun_furiten_status(request, jibun_hand, jibun_furo, jibun_discards)
    
    response_data = {
        'jibun_discards': jibun_discards,
        'jibun_tsumogiri_flags': jibun_flags,
        'machi_info': machi_info,
        'dora_indicators': current_dora_inds, 
        'dora_tiles': [get_dora_tile(ind) for ind in current_dora_inds],
        'is_furiten': is_furiten
    }
    
    response_data = handle_post_discard(request, my_discard, 'jibun', response_data)
    if 'next_turn_player' not in response_data:
        response_data['next_turn_player'] = ['shimochi', 'toimen', 'kamicha', 'jibun'][(['jibun', 'shimochi', 'toimen', 'kamicha'].index(response_data.get('discarder', 'jibun')) + 1) % 4]
        
    return JsonResponse(response_data)

def cpu_turn(request):
    for p in ['jibun', 'shimochi', 'toimen', 'kamicha']:
        request.session[f'{p}_just_riichi'] = False
        if request.session.get(f'{p}_missed_ron_candidate'):
            request.session[f'{p}_doujun_furiten'] = True
            is_r = request.session.get('is_jibun_riichi' if p == 'jibun' else f'{p}_is_riichi', False)
            if is_r:
                request.session[f'{p}_riichi_furiten'] = True
            request.session[f'{p}_missed_ron_candidate'] = False

    cpu = request.GET.get('cpu')
    request.session[f'{cpu}_doujun_furiten'] = False

    wall = request.session.get('wall', [])
    jibun_hand = request.session.get('jibun_hand', [])
    jibun_furo = request.session.get('jibun_furo', [])
    jibun_discards = request.session.get('jibun_discards', [])
    kyoku = request.session.get('kyoku', 1)
    
    ippatsu_chance = request.session.get(f'{cpu}_ippatsu_chance', False)
    request.session[f'{cpu}_ippatsu_chance'] = False
    
    cpu_hand = request.session.get(f'{cpu}_hand', [])
    cpu_discards = request.session.get(f'{cpu}_discards', [])
    cpu_furo = request.session.get(f'{cpu}_furo', [])
    dora_indicators = request.session.get('dora_indicators', [])
    dora_tiles = [get_dora_tile(ind) for ind in dora_indicators]
    is_cpu_riichi = request.session.get(f'{cpu}_is_riichi', False)
    
    if len(wall) == 0: return handle_ryukyoku(request)
        
    drawn_tile = wall.pop(0)
    cpu_just_riichi = False
    scores = request.session.get('scores', {})
    cpu_score = scores.get(cpu, 25000)
    
    is_cpu_menzen = len([f for f in cpu_furo if f.get('action') != 'ankan']) == 0
    temp_full_hand = cpu_hand + [drawn_tile]
    
    bakaze = get_bakaze(kyoku)
    jikaze = get_jikaze(kyoku, cpu)
    ura_indicators = request.session.get('ura_indicators', [])
    honba = request.session.get('honba', 0)
    kyotaku = request.session.get('kyotaku', 0)
    
    if is_win(temp_full_hand, cpu_furo):
        is_cpu_daburi = request.session.get(f'{cpu}_is_daburi', False)
        yaku_list, han, fu = judge_yaku(cpu_hand, cpu_furo, drawn_tile, True, is_cpu_riichi, dora_tiles, ippatsu_chance, bakaze, jikaze, len(wall), len(cpu_discards), is_rinshan=False, ura_indicators=ura_indicators, is_daburi=is_cpu_daburi)
        if han > 0:
            oya_order = ['jibun', 'shimochi', 'toimen', 'kamicha']
            oya = oya_order[(kyoku - 1) % 4]
            is_oya = (oya == cpu)
            
            score_result, total_points = calc_points(han, fu, is_oya, True, honba, kyotaku)
            yaku_str = "、".join([y[0] for y in yaku_list])
            
            if han >= 13: basic_points = 8000
            elif han >= 11: basic_points = 6000
            elif han >= 8: basic_points = 4000
            elif han >= 6: basic_points = 3000
            else:
                basic_points = fu * (2 ** (han + 2))
                if basic_points >= 1920: basic_points = 2000
                
            points_diff = {'jibun': 0, 'shimochi': 0, 'toimen': 0, 'kamicha': 0}
            if is_oya:
                all_pay = math.ceil(basic_points * 2 / 100) * 100 + 100 * honba
                points_diff[cpu] = all_pay * 3 + kyotaku * 1000
                for p in oya_order:
                    if p != cpu: points_diff[p] = -all_pay
                next_honba = honba + 1
                next_kyoku = kyoku
            else:
                oya_pay = math.ceil(basic_points * 2 / 100) * 100 + 100 * honba
                ko_pay = math.ceil(basic_points / 100) * 100 + 100 * honba
                points_diff[cpu] = oya_pay + ko_pay * 2 + kyotaku * 1000
                for p in oya_order:
                    if p != cpu: points_diff[p] = -oya_pay if p == oya else -ko_pay
                next_kyoku = kyoku + 1
                next_honba = 0
                
            cpu_map_jp = {'jibun': '自分', 'shimochi': '下家', 'toimen': '対面', 'kamicha': '上家'}
            machi_list = get_machi_tiles(cpu_hand, cpu_furo)
            machi_str = "、".join(machi_list)
            
            movement_text = make_score_movement_text(scores, points_diff)
            full_score_result = f"{cpu_map_jp[cpu]}のツモアガリ！\n{score_result}\n{han}翻 {fu}符\n[{yaku_str}]\n【待ち牌】: {machi_str}{movement_text}"
            
            if is_cpu_riichi or is_cpu_daburi:
                ura_inds_str = " ".join([normalize_tile(ind) for ind in ura_indicators])
                full_score_result += f"\n(裏ドラ表示牌: {ura_inds_str})"
                
            cpu_hands = { 'shimochi': request.session.get('shimochi_hand', []), 'toimen': request.session.get('toimen_hand', []), 'kamicha': request.session.get('kamicha_hand', []) }
            cpu_hands[cpu] = temp_full_hand 
            
            return JsonResponse({
                'cpu_just_ron': True, 
                'score_result': full_score_result,
                'points_diff': points_diff,
                'next_kyoku': next_kyoku,
                'next_honba': next_honba,
                'next_kyotaku': 0,
                'cpu_hands': cpu_hands
            })
    
    if not is_cpu_riichi and cpu_score >= 1100 and is_cpu_menzen:
        tenpai_candidates = []
        visible_counts = count_visible_tiles_for_cpu(request, cpu)
        for tile in set(temp_full_hand):
            temp_hand = temp_full_hand.copy()
            temp_hand.remove(tile)
            machi = get_machi_tiles(temp_hand, cpu_furo)
            if machi:
                is_furiten = any(normalize_tile(m) in [normalize_tile(t) for t in cpu_discards] for m in machi)
                rem_count = sum(max(0, 4 - visible_counts.get(normalize_tile(m), 0)) for m in machi)
                if rem_count > 0:
                    tenpai_candidates.append({'discard': tile, 'is_furiten': is_furiten, 'rem_count': rem_count})
                    
        if tenpai_candidates:
            tenpai_candidates.sort(key=lambda x: (not x['is_furiten'], x['rem_count']), reverse=True)
            best_cand = tenpai_candidates[0]
            discard_tile = best_cand['discard']
            if not best_cand['is_furiten']:
                request.session[f'{cpu}_is_riichi'] = True
                request.session[f'{cpu}_ippatsu_chance'] = True
                cpu_just_riichi = True
                request.session[f'{cpu}_just_riichi'] = True
                
                all_furos = request.session.get('jibun_furo', []) + request.session.get('shimochi_furo', []) + request.session.get('toimen_furo', []) + request.session.get('kamicha_furo', [])
                if len(cpu_discards) == 0 and len(all_furos) == 0:
                    request.session[f'{cpu}_is_daburi'] = True
                else:
                    request.session[f'{cpu}_is_daburi'] = False
                
                if cpu in scores: scores[cpu] -= 1000
                request.session['scores'] = scores
                request.session['kyotaku'] = request.session.get('kyotaku', 0) + 1
        else:
            discard_tile = select_best_discard(request, cpu, temp_full_hand)
    else:
        if not is_cpu_riichi: discard_tile = select_best_discard(request, cpu, temp_full_hand)
        else: discard_tile = drawn_tile
        
    is_tsumogiri = (discard_tile == drawn_tile)
    temp_full_hand.remove(discard_tile)
    cpu_hand = temp_full_hand
    cpu_hand.sort(key=lambda tile: TILE_ORDER[tile])
    cpu_discards.append(discard_tile)
    kyotaku = request.session.get('kyotaku', 0)
    
    cpu_flags = request.session.get(f'{cpu}_tsumogiri_flags', [])
    cpu_flags.append(is_tsumogiri)
    
    request.session['wall'] = wall
    request.session[f'{cpu}_hand'] = cpu_hand
    request.session[f'{cpu}_discards'] = cpu_discards
    request.session[f'{cpu}_tsumogiri_flags'] = cpu_flags

    machi_info = get_current_machi_info(request, jibun_hand, jibun_furo)
    tile_class = 'manzu' if '萬' in discard_tile else 'pinzu' if '筒' in discard_tile else 'souzu' if '索' in discard_tile else 'jihai'
    is_furiten = get_jibun_furiten_status(request, jibun_hand, jibun_furo, jibun_discards)
    
    response_data = {
        f'{cpu}_discards': cpu_discards,
        f'{cpu}_tsumogiri_flags': cpu_flags,
        'discard_tile': discard_tile,
        'ron_available': False, 'is_ryukyoku': False, 'cpu_just_riichi': cpu_just_riichi,
        'current_kyotaku': kyotaku, 'jibun_discards': jibun_discards, 'machi_info': machi_info,
        'dora_indicators': dora_indicators, 'dora_tiles': dora_tiles, 'tile_class': tile_class,
        'is_furiten': is_furiten
    }
    
    response_data = handle_post_discard(request, discard_tile, cpu, response_data)
    if 'next_turn_player' not in response_data:
        response_data['next_turn_player'] = ['jibun', 'shimochi', 'toimen', 'kamicha'][(['jibun', 'shimochi', 'toimen', 'kamicha'].index(response_data.get('discarder', cpu)) + 1) % 4]
        
    return JsonResponse(response_data)

def sync_next_kyoku(request):
    kyoku = int(request.GET.get('kyoku', 1))
    honba = int(request.GET.get('honba', 0))
    kyotaku = int(request.GET.get('kyotaku', 0))
    scores = {
        'jibun': int(request.GET.get('jibun', 25000)), 'shimochi': int(request.GET.get('shimochi', 25000)),
        'toimen': int(request.GET.get('toimen', 25000)), 'kamicha': int(request.GET.get('kamicha', 25000)),
    }
    
    log_title = request.GET.get('log_title')
    log_text = request.GET.get('log_text')
    if log_title and log_text:
        game_log = request.session.get('game_log', [])
        game_log.append({'title': log_title, 'text': log_text})
        request.session['game_log'] = game_log

    request.session['kyoku'] = kyoku
    request.session['honba'] = honba
    request.session['kyotaku'] = kyotaku
    request.session['scores'] = scores
    return JsonResponse({'status': 'success'})

def learning_page(request):
    return render(request, 'chat/learning.html')
