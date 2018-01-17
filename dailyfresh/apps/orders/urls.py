from django.conf.urls import url
from orders import views

urlpatterns = [
    # 订单确认页面
    url(r'^place$',views.PlaceOrderView.as_view(),name='place'),
    # 订单提交页面
    url(r'^commit$',views.CommitOrderView.as_view(),name='commit'),
]