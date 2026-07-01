from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from chat import views

#chatアプリとaccountアプリの両方のviewsをインポートします
from chat import views as chat_views
from accounts import views as account_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 【最重要】サイトのトップ（/）にアクセスした時、最初にログイン画面を表示する
    path('', auth_views.LoginView.as_view(), name='login'),
    
    # ログイン・ログアウト機能
    path('accounts/login/', auth_views.LoginView.as_view(), name='login_old'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # 【重要】チャット画面のURLを「/room/」へ引っ越しさせました
    path('room/', chat_views.chat_room, name='chat_room'), # chat_views に修正
    
    # チャット用画面と各通信窓口（既存のまま変更なし）
    path('signup/', chat_views.signup, name='signup'),     # chat_views に修正
    path('send_message', chat_views.send_message, name='send_message'),
    path('get_messages', chat_views.get_messages, name='get_messages'),
    path('edit_message', chat_views.edit_message, name='edit_message'),
    path('react_message', chat_views.react_message, name='react_message'),
    path('search_posts', chat_views.search_posts, name='search_posts'), 
    path('get_reaction_users/', views.get_reaction_users, name='get_reaction_users'),

    # 新しいプロフィール画面用のURL（accountアプリのviewsに繋ぎます）
    path('profile/', account_views.edit_profile, name='my_profile'),
    path('profile/<int:user_id>/', account_views.edit_profile, name='view_profile'),
    path('profile/<int:user_id>/toggle-follow/', account_views.toggle_follow, name='toggle_follow'),

    # 通知一覧画面へのアクセス窓口
    path('notifications/', chat_views.notification_list, name='notifications'),

    path('delete_message', chat_views.delete_message, name='delete_message'),
     
    # 【新規追加】ユーザー検索の通信窓口URL（room.jsと連携）
    path('search_users/', chat_views.search_users, name='search_users'),
    # 【新規追加】ミニゲームへのアクセス窓口URL
    # 学習モードのURL
    path('minigames/mahjong/learning/', views.learning_page, name='learning'),

    # 麻雀の裏側で動く通信用URL群
    path('minigames/mahjong/', views.game_mahjong, name='game_mahjong'),
    path('tsumo/', views.tsumo, name='tsumo'),
    path('declare_riichi/', views.declare_riichi, name='declare_riichi'),
    path('declare_naki/', views.declare_naki, name='declare_naki'),
    path('check_agari/', views.check_agari, name='check_agari'),
    path('player_discard/', views.player_discard, name='player_discard'),
    path('cpu_turn/', views.cpu_turn, name='cpu_turn'),
    path('sync_next_kyoku/', views.sync_next_kyoku, name='sync_next_kyoku'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
