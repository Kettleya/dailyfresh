from django.conf.urls import url
from users import views
from django.contrib.auth.decorators import login_required


urlpatterns = [
    # 函数视图：注册
    # url(r'^register/$', views.register),
    # 类视图：注册
    url(r'^register$', views.RegisterView.as_view(), name='register'),
    # 激活
    url(r'^active/(?P<token>.+)$', views.ActiveView.as_view(), name='active'),
    # 登陆
    url(r'^login$', views.LoginView.as_view(), name='login'),
    # 退出登录
    url(r'^logout$', views.LogoutView.as_view(), name='logout'),
    # 用户中心：用户地址
    # url(r'^address$', login_required(views.AddressView.as_view()), name='address'),
    url(r'^address$', views.AddressView.as_view(), name='address'),
    # 个人信息
    url(r'^info$', views.UserInfoView.as_view(), name='info')

]
