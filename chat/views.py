from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse
import json
from .models import ChatMessage, MessageReaction
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
            video=uploaded_video
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
        
        # ⭕ 'review3' を判定条件に追加しました
        if react_type in ['confirm', 'agree', 'review', 'review2', 'review3']:
            try:
                msg = ChatMessage.objects.get(id=msg_id)
                existing_react = MessageReaction.objects.filter(message=msg, username=username, react_type=react_type)
                if existing_react.exists():
                    existing_react.delete()
                else:
                    MessageReaction.objects.create(message=msg, username=username, react_type=react_type)

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

                return JsonResponse({'status': 'success'})
            except ChatMessage.DoesNotExist:
                pass
    return JsonResponse({'status': 'failed'}, status=400)


from django.contrib.auth.models import User
from accounts.models import Profile  # フォルダ名が account の場合は account.models

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
        
        image_url = m.image.url if m.image else None
        video_url = m.video.url if m.video else None
        
        # 発言ユーザーのプロフィールアイコンの取得処理
        icon_url = ""
        try:
            # 投稿データのユーザー名からUserモデルを経由してProfileモデルを特定
            target_user = User.objects.get(username=m.username)
            profile, _ = Profile.objects.get_or_create(user=target_user)
            if profile and profile.icon and hasattr(profile.icon, 'url'):
                icon_url = profile.icon.url
        except Exception:
            icon_url = ""  # ユーザーが存在しないなどの例外時は空を返す
        
        logs.append({
            'id': m.id,
            'username': m.username,
            'text': m.text,
            'time': m.time,
            'parent_id': m.parent.id if m.parent else None,
            'reactions': reactions_count,
            'image_url': image_url,
            'video_url': video_url,
            'icon_url': icon_url,
             'user_id': target_user.id if 'target_user' in locals() else None,
        })
    
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(receiver=request.user, is_read=False).count()
    else:
        unread_count = 0

    return JsonResponse({'messages': logs, 'unread_count': unread_count})

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
        # 検索キーワードを含むメッセージを取得（親メッセージのみ）
        messages = ChatMessage.objects.filter(
            text__icontains=query,
            parent__isnull=True
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
            })
    
    return JsonResponse({'results': results, 'query': query})

@login_required
def notification_list(request):
    # 自分宛ての通知を新しい順にすべて取得
    notifications = Notification.objects.filter(receiver=request.user)
    
    # この画面を開いた瞬間に、これまでの通知をすべて「既読（is_read=True）」にする
    notifications.update(is_read=True)
    
    return render(request, 'chat/notifications.html', {'notifications': notifications})
