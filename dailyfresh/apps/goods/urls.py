from django.conf.urls import url
from goods import views


urlpatterns = [
    # 主页
    url(r'^index$', views.IndexView.as_view(), name='index')
]