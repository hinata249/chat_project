from django import forms
from django.contrib.auth.models import User
from .models import Profile

class ProfileForm(forms.ModelForm):
    # 💡 ログインネーム（User.username）を直接編集するフィールド
    username = forms.CharField(label='ユーザー名', max_length=150)

    class Meta:
        model = Profile
        fields = ['icon'] # 画像はProfileモデルから持ってくる

    def __init__(self, *args, **kwargs):
        # 💡 画面を開いたとき、現在のログインID（adminなど）を自動で入力欄に埋め込む処理
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['username'].initial = user.username
