from django.core import paginator
from django.shortcuts import render, redirect
from django.views.generic import View
from goods.models import GoodsCategory, Goods, GoodsSKU,GoodsImage,IndexGoodsBanner,IndexPromotionBanner,IndexCategoryGoodsBanner
from django.core.cache import cache
from django_redis import get_redis_connection
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, EmptyPage

class ListView(View):
    """列表页"""
    # 接收请求参数,category_id,page_num,sort
    def get(self,request,category_id,page_num):
        sort = request.GET.get('sort','default') # 如果用户不传,就是默认的default排序规则

        # 校验category_id,查询时校验
        try:
            category = GoodsCategory.objects.get(id=category_id)
        except category_id.DoesNotExist:
            return redirect(reverse('goods:index'))

        # 查询商品全部分类
        categorys = GoodsCategory.objects.all()

        # 查询新品推荐
        new_skus = GoodsSKU.objects.filter(category=category).order_by('-create_time')[:2]

        # 按照排序规则,查询category对应的所有sku
        if sort == 'price':
            # 按照价格由低到高排序
            skus = GoodsSKU.objects.filter(category=category).order_by('price')
            # 按照销量由高到低排序
            skus = GoodsSKU.objects.filter(category=category).order_by('-sales')
        else:
            skus = GoodsSKU.objects.filter(category=category)

        # 分页查询
        page_num = int(page_num)
        # 创建分页器对象
        paginator = Paginator(skus,2)
        # 使用分页器对象,创建分页对象
        try:
            # page_skus里包含了2个sku对象
            page_skus = paginator.page(page_num)
        except EmptyPage:
            page_skus = paginator.page(1)

        # 计算分页码列表
        page_list = paginator.page_range

        # 查询购物车数据
        cart_num = 0

        # 当用户登录时,操作购物车,查询购物车数据
        if request.user.is_authenticated():
            # 连接redis对象
            redis_conn = get_redis_connection('default')
            # 获取user_id
            user_id = request.user.id
            # 查询购物车数据
            cart_dict = redis_conn.hgetall('cart_%s'%user_id)

            # 便利cart_dict,取出val,累加
            for val in cart_dict.values():
                cart_num += int(val)

        # 构造上下文
        context = {
            'category':category,
            'sort':sort,
            'categorys':categorys,
            'new_skus':new_skus,
            'skus':skus,
            'page_skus':page_skus,
            'page_list':page_list,
            'cart_num':cart_num,
        }

        # 渲染模板
        return render(request,'list.html',context)


class DetailView(View):
    """详情页"""

    def get(self, request, sku_id):
        """提供详情页面"""

        # 查询缓存数据
        context = cache.get('detail_%s'%sku_id)

        # 如果没有缓存
        if context is None:

            try:
                # 获取商品信息
                sku = GoodsSKU.objects.get(id=sku_id)
            except GoodsSKU.DoesNotExist:
                # from django.http import Http404
                # raise Http404("商品不存在!")
                return redirect(reverse("goods:index"))

            # 获取类别
            categorys = GoodsCategory.objects.all()

            # 从订单中获取评论信息
            sku_orders = sku.ordergoods_set.all().order_by('-create_time')[:30]
            if sku_orders:
                for sku_order in sku_orders:
                    sku_order.ctime = sku_order.create_time.strftime('%Y-%m-%d %H:%M:%S')
                    sku_order.username = sku_order.order.user.username
            else:
                sku_orders = []

            # 获取最新推荐
            new_skus = GoodsSKU.objects.filter(category=sku.category).order_by("-create_time")[:2]

            # 获取其他规格的商品
            other_skus = sku.goods.goodssku_set.exclude(id=sku_id)

            context = {
                "categorys": categorys,
                "sku": sku,
                "orders": sku_orders,
                "new_skus": new_skus,
                "other_skus": other_skus,
            }

            # 缓存数据，key,context,过期时间
            cache.set('detail_%s' % sku_id, context, 3600)

        # 查询购物车数据redis
        cart_num = 0

        if request.user.is_authenticated():
            # 创建redis连接对象 hset cart_userid sku_id count
            redis_conn = get_redis_connection('default')
            user_id = request.user.id
            cart_dict = redis_conn.hgetall('cart_%s'%user_id)
            for val in cart_dict.values():
                cart_num += int(val)

            # 浏览记录保存：lpush history_userid skuid1, skuid2, ...
            # sku_id1 sku_id1
            # 去重
            redis_conn.lrem('history_%s'%user_id, 0, sku_id)
            # 添加
            redis_conn.lpush('history_%s'%user_id, sku_id)
            # 用户浏览顺序：sku_id1 sku_id2 sku_id3 sku_id4 sku_id5 sku_id6
            # 后端记录顺序：sku_id6 sku_id5 sku_id4 sku_id3 sku_id2 sku_id1
            redis_conn.ltrim('history_%s'%user_id, 0, 4)

        # 更新购物车数据到context
        context.update(cart_num=cart_num)

        # 渲染模板
        return render(request, 'detail.html', context)


class IndexView(View):
    """主页"""

    def get(self, request):
        """提供主页页面"""

        # 先查询是否有缓存，如果有，就直接读取缓存数据，反之，查询数据后再缓存
        context = cache.get('index_page_data')
        if context is None:
            print('没有缓存，查询数据库')

            # 查询用户信息user：不需要专门查询，已经在request中
            # 查询商品分类信息
            categorys = GoodsCategory.objects.all()

            # 查询图片轮播信息
            index_banners = IndexGoodsBanner.objects.all().order_by('index')

            # 查询商品活动信息
            promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

            # 查询主页商品列表信息
            for category in categorys:
                # 查询文字形式展示的商品
                title_banners = IndexCategoryGoodsBanner.objects.filter(category=category,display_type=0).order_by('index')
                category.title_banners = title_banners

                # 查询文字图片展示的商品
                image_banners = IndexCategoryGoodsBanner.objects.filter(category=category, display_type=1).order_by('index')
                category.image_banners = image_banners

            # 构造上下文
            context = {
                'categorys':categorys,
                'index_banners':index_banners,
                'promotion_banners':promotion_banners
            }

            # 缓存主页数据:key 要缓存的数据 有效期
            cache.set('index_page_data', context, 3600)

        # 查询购物车数据
        cart_num = 0

        # 当用户登陆时，操作购物车，查询购物车数据
        if request.user.is_authenticated():
            # 创建redi连接对象
            redis_conn = get_redis_connection('default')
            # 获取user_id
            user_id = request.user.id
            # 查询redis中存储的购物车数据 {'sku_id1':2, 'sku_id2':3}
            cart_dict = redis_conn.hgetall('cart_%s'%user_id)

            # 遍历cart_dict,取出val,累加：注意点：py3下，redis读取出的字典value是bytes
            for val in cart_dict.values():
                cart_num += int(val)

        # 更新购物车数据到上下文
        context.update(cart_num=cart_num)

        # 渲染模板
        return render(request, 'index.html', context)