from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy
from django.views import generic
from django.http import JsonResponse
from .forms import ProfileForm
from .models import Profile, Message
from .models import Notification

# 1. アカウント新規登録処理
class SignUpView(generic.CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy('login') 
    template_name = 'accounts/signup.html'

# 2. メインチャット画面の表示（常に最新のユーザーデータを取得）
@login_required
def main_chat(request):
    user = User.objects.get(id=request.user.id)
    return render(request, 'accounts/mainchat.html', {'user': user})

# 3. プロフィール画面（閲覧・編集）★ログインIDと表示名を完全同期
@login_required
def edit_profile(request, user_id=None):
    if user_id is None:
        target_user = request.user
    else:
        target_user = get_object_or_404(User, id=user_id)

    my_profile, _ = Profile.objects.get_or_create(user=request.user)
    target_profile, _ = Profile.objects.get_or_create(user=target_user)

    is_me = (target_user == request.user)
    is_following = my_profile.following.filter(id=target_profile.id).exists()

    if request.method == 'POST' and is_me:
        form = ProfileForm(request.POST, request.FILES, instance=target_profile, user=target_user)
        if form.is_valid():
            new_username = form.cleaned_data.get('username')
            if new_username:
                # 💡 ログイン用IDとプロフィール用名前を「同時に同じ値」で上書き保存します
                target_user.username = new_username
                target_user.save()
                target_profile.nickname = new_username
                target_profile.save()
            form.save()
            return redirect('chat_room')
    else:
        form = ProfileForm(instance=target_profile, user=target_user)

    context = {
        'form': form,
        'profile': target_profile,
        'target_user': target_user,
        'is_me': is_me,
        'is_following': is_following,
        'following_count': target_profile.following.count(),
        'followers_count': target_profile.followers.count(),
    }
    return render(request, 'accounts/profile_edit.html', context)

# 4. フォローする / フォロー中（解除）を切り替える処理
@login_required
def toggle_follow(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    my_profile, _ = Profile.objects.get_or_create(user=request.user)
    target_profile, _ = Profile.objects.get_or_create(user=target_user)

    if my_profile.following.filter(id=target_profile.id).exists():
        my_profile.following.remove(target_profile)
    else:
        my_profile.following.add(target_profile)

        if target_user != request.user:
            Notification.objects.create(
                receiver=target_user,
                sender=request.user,
                notification_type='follow'
            )
    return redirect('view_profile', user_id=user_id)

# 5. チャットメッセージ一覧の取得（💡 読み出し名をログインIDに一本化）
@login_required
def get_messages(request):
    messages = Message.objects.all()
    data = []
    for m in messages:
        profile, _ = Profile.objects.get_or_create(user=m.user)
        # 💡 チグハグを防止するため、表示名をログインID（username）に完全固定します
        nickname = m.user.username
        icon_url = profile.icon.url if profile.icon else ""

        data.append({
            'id': m.id,
            'username': nickname,
            'user_id': m.user.id,
            'text': m.text,
            'icon_url': icon_url,
            'media_url': m.media.url if m.media else "",
            'time': m.created_at.strftime('%m/%d %H:%M'),
        })
    return JsonResponse({'messages': data})

# 6. チャットメッセージをDBに保存する処理
@login_required
def send_message(request):
    if request.method == 'POST':
        text = request.POST.get('text', '')
        media = request.FILES.get('media', None)
        if text or media:
            Message.objects.create(user=request.user, text=text, media=media)
            return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)
