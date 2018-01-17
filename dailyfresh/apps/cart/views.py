from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse
from goods.models import GoodsSKU
from django_redis import get_redis_connection
import json


# Create your views here.


class DeleteCartView(View):
    """删除购物车数据"""

    def post(self, request):
        """处理删除购物车数据逻辑"""

        # 接收参数：user_id,sku_id
        sku_id = request.POST.get('sku_id')

        # 校验参数，not
        if not sku_id:
            return JsonResponse({'code':1, 'message':'缺少商品sku_id'})

        # 判断用户是否登陆
        # 如果用户已登录，删除redis中某些记录
        if request.user.is_authenticated():
            user_id = request.user.id
            redis_conn = get_redis_connection('default')
            # 删除记录:如果value不存在的，直接会忽略掉
            redis_conn.hdel('cart_%s'%user_id, sku_id)

        else:
            # 如果用户未登录，删除cookie
            cart_json = request.COOKIES.get('cart')
            if cart_json is not None:
                cart_dict = json.loads(cart_json)

                # 删除sku_id对应的value
                if sku_id in cart_dict:
                    del cart_dict[sku_id]

                # 生成新的cart_json
                new_cart_json = json.dumps(cart_dict)

                response = JsonResponse({'code': 0, 'message': '删除购物车数据成功'})
                # 写入cookie
                response.set_cookie('cart', new_cart_json)

                return response

        # 响应结果
        return JsonResponse({'code': 0, 'message': '删除购物车数据成功'})


class UpdateCartView(View):
    """更新购物车数据 : + - 手动输入"""

    def post(self, request):
        """处理更新购物车数据的逻辑"""

        # 接收请求参数：user_id,sku_id,count
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 校验参数：all()
        if not all([sku_id, count]):
            return JsonResponse({'code':1, 'message':'用户未登录'})

        # 判断sku_id是否正确，查一下，try
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'code': 2, 'message': '商品不存在'})

        # 判断count是否正确，是否是整数
        try:
            count = int(count)
        except Exception:
            return JsonResponse({'code': 3, 'message': '商品数量格式错误'})

        # 判断库存
        if count > sku.stock:
            return JsonResponse({'code': 4, 'message': '库存不足'})

        # 判断用户是否登陆
        if request.user.is_authenticated():
            # 如果用户已登陆，更新redis中的购物车数据
            redis_conn = get_redis_connection('default')
            user_id = request.user.id
            # 前后端都遵守幂等的接口设计方式，count就是最终的结果，不需要再计算
            redis_conn.hset('cart_%s'%user_id, sku_id, count)
            return JsonResponse({'code': 0, 'message': '更新购物车成功'})
        else:
            # 如果用户未登陆，更新cookie中的购物车数据
            cart_json = request.COOKIES.get('cart')
            if cart_json is not None:
                cart_dict = json.loads(cart_json)
            else:
                cart_dict = {}

            # 将新的购物车数量赋值到字典
            cart_dict[sku_id] = count

            # 生成新的购物车json字符串
            new_cart_json = json.dumps(cart_dict)

            # 创建response对象
            response = JsonResponse({'code': 0, 'message': '更新购物车成功'})

            # 写入cookie
            response.set_cookie('cart', new_cart_json)

            # 响应结果
            return response


class CartInfoView(View):
    """购物车信息页面"""

    def get(self, request):
        """提供购物车信息页面"""

        # 如果用户已登录，查询redis
        if request.user.is_authenticated():
            # 创建redis连接对象
            redis_conn = get_redis_connection('default')
            # 获取use_id
            user_id = request.user.id
            # 查询redis中所有购物车数据
            cart_dict = redis_conn.hgetall('cart_%s'%user_id)
        else:
            # 如果用户未登录，查询cookie
            cart_json = request.COOKIES.get('cart')
            if cart_json is not None:
                cart_dict = json.loads(cart_json)
            else:
                cart_dict = {}

        # 定义临时变量
        skus = []
        total_amount = 0
        total_count = 0

        # 遍历购物车字典
        for sku_id, count in cart_dict.items():
            # 使用sku_id,查询sku对象
            try:
                sku = GoodsSKU.objects.get(id=sku_id)
            except GoodsSKU.DoesNotExist:
                # 没有就跳过，继续遍历后面存在的商品
                continue

            # 统一redis中和cookie中的count的类型
            count = int(count)

            # 计算商品小计信息
            amount = count * sku.price

            # 动态给sku对象绑定商品数量和小计信息
            sku.count = count
            sku.amount = amount
            # 记录sku
            skus.append(sku)

            # 计算价格合计和总数
            total_amount += amount
            total_count += count

        # 构造上下文
        context = {
            'skus':skus,
            'total_amount':total_amount,
            'total_count':total_count
        }

        # 渲染模板
        return render(request, 'cart.html', context)


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

        # 判断库存:1<2
        # if count > sku.stock:
            # return JsonResponse({'code': 5, 'message': '库存不足'})

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

            # 先计算原有商品的原有的购物车数量，再对库存进行判断
            if count > sku.stock:
                return JsonResponse({'code': 5, 'message': '库存不足'})

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

            # 先计算原有商品的原有的购物车数量，再对库存进行判断
            if count > sku.stock:
                return JsonResponse({'code': 6, 'message': '库存不足'})

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








