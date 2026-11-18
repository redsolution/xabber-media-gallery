from django.urls import path
from .views import QuotaView, AccountView, WhiteListView, FilesView, FilesPercentView, UploadFileView, SlotView, StatsView, XmppCodeView,\
    XmppAuthView, TokensView, DefaultQuotaView, AccountListView, BlackListView, OpenGraphView, DiskSpaceView


urlpatterns = [
    path('files/', FilesView.as_view({'get': 'list', 'delete': 'delete'}), name='files'),
    path('files/percent/<int:percent>/', FilesPercentView.as_view({'get': 'list', 'delete': 'delete'}), name='files'),
    path('files/upload/', UploadFileView.as_view(), name='files_upload'),
    path('files/slot/', SlotView.as_view(), name='slot'),
    path(r'files/stats/', StatsView.as_view(), name='stats'),
    path('account/xmpp_code_request/', XmppCodeView.as_view(), name='xmpp_code_request'),
    path('account/xmpp_auth/', XmppAuthView.as_view(), name='xmpp_auth'),
    path('account/tokens/', TokensView.as_view({'get': 'list', 'delete': 'delete'}), name='tokens'),
    path('account/quota/', QuotaView.as_view(), name='quota'),
    path('account/default_quota/', DefaultQuotaView.as_view(), name='default_quota'),
    path('account/', AccountView.as_view({'delete': 'delete'}), name='account'),
    path('account/list/', AccountListView.as_view(), name='account_list'),
    path('blacklist/', BlackListView.as_view({'get': 'list', 'post': 'create'}), name='blacklist'),
    path('whitelist/', WhiteListView.as_view({'get': 'list', 'post': 'create'}), name='whitelist'),
    path(r'opengraph/', OpenGraphView.as_view(), name='opengraph'),
    path('disk/space/', DiskSpaceView.as_view(), name='disk_space'),
]
