import json
from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic import View
from django_redis import get_redis_connection
from goods.models import GoodsSKU

class CartInfoView(View):
    """购物车信息页面"""
    def get(self,request):
        """提供购物车信息页面"""

        # 如果用户已登陆,查询redis
        if request.user.is_authenticated():
            # 创建redis连接对象
            redis_conn = get_redis_connection('default')
            # 获取user_id
            user_id = request.user.id
            # 查询redis中所有购物车数据
            cart_dict = redis_conn.hgetall('cart_%s'%user_id)
        else:
            # 如果用户未登录过,查询cookie
            cart_json = request.COOKIES.get('cart')
            if cart_json is not None:
                cart_dict = json.loads(cart_json)
            else:
                cart_dict = {}

        # 定义临时变量
        skus = []
        total_amout = 0
        total_count = 0

        # 遍历购物车字典
        for count,sku_id in cart_dict.items():
            # 使用sku_id查询sku对象
            try:
                sku = GoodsSKU.objects.get(id=sku_id)
            except GoodsSKU.DoesNotExist:
                continue
            # 统一redis中和cookie中的count类型
            count = int(count)

            # 计算商品小计信息
            amount = sku.price * count

            # 动态给sku对象绑定商品数量和小计信息
            sku.count = count
            sku.amount = amount
            # 记录sku
            skus.append(sku)

            # 计算价格合计总数
            total_amout += amount
            total_count += count

        # 构造上下文
        context = {
            'skus':skus,
            'total_count':total_count,
            'total_amount':total_amout
        }

        # 渲染模板
        return render(request,'cart.html',context)


class AddCartView(View):
    """添加购物车"""

    def post(self, request):
        """处理添加购物车逻辑：接收数据，校验数据，存储数据"""

        # 判断是否登陆如果为登陆
        # if not request.user.is_authenticated():
        #     return JsonResponse({'code':1, 'message':'用户未登录'})

        # 获取请求参数：user_id,sku_id,count
        # user_id = request.user.id
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 校验参数：all()
        if not all([sku_id, count]):
            return JsonResponse({'code':2, 'message':'缺少参数'})

        # 判断sku_id是否正确
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'code': 3, 'message': '商品不存在'})

        # 判断数量是否是整数
        try:
            count = int(count)
        except Exception:
            return JsonResponse({'code': 4, 'message': '商品数量格式错误'})

        # 判断库存
        if count > sku.stock:
            return JsonResponse({'code': 5, 'message': '库存不足'})

        # 如果用户登陆，存储购物车数据到redis中
        if request.user.is_authenticated():
            # 只有登录才获取use_id
            user_id = request.user.id

            # 将数据保存到redis中
            redis_conn = get_redis_connection('default')
            # 判断要加入购物车的商品，是否已经存在
            origin_count = redis_conn.hget('cart_%s' % user_id, sku_id)
            if origin_count is not None:
                # 如果已存在，需要累加新旧数据。反之，直接添加新数据.origin_count是字节类型
                count += int(origin_count)

            redis_conn.hset('cart_%s' % user_id, sku_id, count)

            # 为了前端展示效果的需求，我们需要查询购物车总数量，交给前端
            cart_num = 0
            cart_dict = redis_conn.hgetall('cart_%s' % user_id)
            for val in cart_dict.values():
                cart_num += int(val)

            # 响应结果
            return JsonResponse({'code': 0, 'message': '添加购物车成功', 'cart_num': cart_num})

        else:
            # 如果用户登陆，存储购物车数据到cookie中 '{'sku_1':1, 'sku_2':2}'
            cart_json = request.COOKIES.get('cart')

            # 判断用户是否在cookie中存储过购物车数据
            if cart_json is not None:
                cart_dict = json.loads(cart_json)
            else:
                cart_dict = {}

            # 判断要添加到购物车的商品已存在的,做累加。反之，直接赋值新值count
            if sku_id in cart_dict:
                origin_count = cart_dict[sku_id]
                count += origin_count

            cart_dict[sku_id] = count

            # 为了前端展示购物车数据的效果，后端需要先查询出购物车总数
            cart_num = 0
            for val in cart_dict.values():
                cart_num += val

            # 将新的购物车字典数据转成json字符串
            new_cart_json = json.dumps(cart_dict)
            # 创建响应对象
            response = JsonResponse({'code': 0, 'message': '添加购物车成功', 'cart_num': cart_num})
            # 购物车数据写入cookie
            response.set_cookie('cart', new_cart_json)

            # 响应结果
            return response
