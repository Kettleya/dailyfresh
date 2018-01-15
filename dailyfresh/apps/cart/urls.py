from django.conf.urls import url
from cart import views

urlpatterns = [
    # 添加购物车
    url(r'^add$',views.AddCartView.as_view(),name='add'),
    # 购物车信息
    url(r'^$',views.CartInfoView.as_view(),name='info'),
    # 更新购物车视图
    url(r'^update$',views.UpdateCartView.as_view(),name='update'),
    # 删除购物车视图
    url(r'^delete$',views.DeleteCartView.as_view(),name='delete'),
]