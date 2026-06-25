from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse
import json
from .models import ChatMessage, MessageReaction

def chat_room(request):
    return render(request, 'chat/room.html')

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
                return JsonResponse({'status': 'success'})
            except ChatMessage.DoesNotExist:
                pass
    return JsonResponse({'status': 'failed'}, status=400)


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
        
        # 💡 画像と動画のURLを取得する処理（登録されている場合のみURLを生成する）
        image_url = m.image.url if m.image else None
        video_url = m.video.url if m.video else None
        
        logs.append({
            'id': m.id,
            'username': m.username,
            'text': m.text,
            'time': m.time,
            'parent_id': m.parent.id if m.parent else None,
            'reactions': reactions_count,
            'image_url': image_url,  # 🛠️ フロントエンドに画像URLを伝える
            'video_url': video_url   # 🛠️ フロントエンドに動画URLを伝える
        })
    return JsonResponse(logs, safe=False)

def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})
