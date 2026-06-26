from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    # Django標準のユーザー（User）と1対1で紐付け
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    # ユーザー名（編集可能）
    nickname = models.CharField('ユーザー名', max_length=50, blank=True)
    
    # アイコン画像（更新可能 / media/icons/ フォルダに保存される）
    icon = models.ImageField('アイコン画像', upload_to='icons/', blank=True, null=True)
    
    # フォロー関係の定義（自分自身 Profile への多対多の紐付け）
    following = models.ManyToManyField('self', symmetrical=False, related_name='followers', blank=True)

    def __str__(self):
        return f"{self.user.username}のプロフィール"

class Message(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField(blank=True, null=True)
    # 添付ファイル（画像・動画）用
    media = models.FileField(upload_to='chat_media/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at'] # 古い順に並べる

# account/models.py の最末尾に追加
from django.db import models
from django.contrib.auth.models import User

class Notification(models.Model):
    # 通知を受け取る人、送った人
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications_received')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications_sent')
    
    # 通知の種類（'reply': スレッドへの返信, 'follow': フォローされた）
    notification_type = models.CharField(max_length=20)

    # どのメッセージに対する通知かを記録する項目（フォロー通知時は空になるため blank=True を指定）
    message_id = models.IntegerField(null=True, blank=True)
    
    # すでに読んだかどうかの判定項目
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
