from django.contrib import admin
from django.urls import path
from chat import views
from django.contrib.auth import views as auth_views

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 💡 【最重要】サイトのトップ（/）にアクセスした時、最初にログイン画面を表示する
    path('', auth_views.LoginView.as_view(), name='login'),
    
    # ログイン・ログアウト機能（既存のURLもそのまま残しておきます）
    path('accounts/login/', auth_views.LoginView.as_view(), name='login_old'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # 💡 【重要】チャット画面のURLを「/room/」へ引っ越しさせました
    path('room/', views.chat_room, name='chat_room'),
    
    # チャット用画面と各通信窓口（既存のまま変更なし）
    path('signup/', views.signup, name='signup'),
    path('send_message', views.send_message, name='send_message'),
    path('get_messages', views.get_messages, name='get_messages'),
    path('edit_message', views.edit_message, name='edit_message'),
    path('react_message', views.react_message, name='react_message'), 
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)