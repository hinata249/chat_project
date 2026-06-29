from django.db import models
from django.contrib.auth.models import User

# ⭕ データベースにメッセージを保存するためのテーブル（設計図）
class ChatMessage(models.Model):
    username = models.CharField(max_length=150)
    text = models.TextField()
    time = models.CharField(max_length=10)
    # 自分への返信（親子関係）を管理。消されたら連動して消える設定
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    # 🛠️ 【新機能】画像と動画を保存する項目を追加（空っぽでもOKにする）
    image = models.ImageField(upload_to='chat_images/', null=True, blank=True)
    video = models.FileField(upload_to='chat_videos/', null=True, blank=True)

    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.username}: {self.text[:10]}"

# ⭕ 誰がどの絵文字を押したかを記録するテーブル
class MessageReaction(models.Model):
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='message_reactions')
    username = models.CharField(max_length=150)
    react_type = models.CharField(max_length=20) # 'confirm', 'agree', 'review', 'review2'

    class Meta:
        # 同じ人が同じメッセージに同じ絵文字を複数回押せないように制限
        unique_together = ('message', 'username', 'react_type')
