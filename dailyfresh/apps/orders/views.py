from django.core.paginator import Paginator, EmptyPage
from django.shortcuts import render,redirect
from utils.views import LoginRequiredMixin,LoginRequiredJsonMixin,TransactionAtomicMixin
from django.views.generic import View
from django.core.urlresolvers import reverse
from goods.models import GoodsSKU
from django_redis import get_redis_connection
from users.models import Address
from django.http import JsonResponse
from orders.models import OrderInfo, OrderGoods
from django.utils import timezone
from django.db import transaction

class PayView(LoginRequiredJsonMixin,View):
    """支付宝支付"""
    def post(self,request):
        """对接到支付宝"""
        # 接收订单id

        # 检验订单id
        

# Create your views here.
class UserOrderView(LoginRequiredMixin,View):
    """我的订单"""
    def get(self,request,page):
        """处理我的订单查询逻辑"""

        # 查询所有订单
        user = request.user
        orders = user.orderinfo_set.all().order_by('-create_time')
        # 遍历所有订单
        for order in orders:
            # 动态绑定:订单状态
            order.status_name = OrderInfo.ORDER_STATUS[order.status]
            # 动态绑定:支付方式
            order.pay_method_name = OrderInfo.PAY_METHODS[order.pay_method]
            order.skus = []
            # 获取所有商品信息
            order_skus = order.ordergoods_set.all()
            # 遍历所有商品,并给属性赋值
            for order_sku in order_skus:
                sku = order_sku.sku
                sku.count = order_sku.count
                sku.amout = sku.count * sku.price
                order.skus.append(sku)
        # 分页
        page = int(page)
        try:
            paginator = Paginator(orders,2)
            page_orders = paginator.page(page)
        except EmptyPage:
            page_orders = paginator.page(1)
            page = 1

        # 页数
        page_list = paginator.page_range
        context = {
            'orders':page_orders,
            'page':page,
            'page_list':page_list,
        }
        return render(request,'user_center_order.html',context)


class CommitOrderView(LoginRequiredJsonMixin,TransactionAtomicMixin,View):
    """订单提交"""

    def post(self, request):
        """处理订单提交逻辑"""

        # 获取参数：user,address_id,pay_method,sku_ids,count
        user = request.user
        address_id = request.POST.get('address_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids') # '1,2,3'

        # 校验参数：all([address_id, pay_method, sku_ids])
        if not all([address_id, pay_method, sku_ids]):
            return JsonResponse({'code':2, 'message':'缺少参数'})

        # 判断地址
        try:
            address = Address.objects.get(id=address_id)
        except Address.DoesNotExist:
            return JsonResponse({'code':3, 'message':'地址不存在'})

        # 判断支付方式
        if not pay_method in OrderInfo.PAY_METHOD:
            return JsonResponse({'code':4, 'message':'支付方式不存在'})

        # 在开始操作数据库之前，创建事务的保存点，J想来直接回滚到此
        save_point = transaction.savepoint()

        try:

            # 手动生成订单id:时间戳+user.id == 2018011612164910
            order_id = timezone.now().strftime('%Y%m%d%H%M%S')+str(user.id)

            # 先创建商品订单信息
            order = OrderInfo.objects.create(
                order_id = order_id,
                user = user,
                address = address,
                total_amount = 0,
                trans_cost = 10,
                pay_method = pay_method
            )

            # 创建redis链接对象和数据
            redis_conn = get_redis_connection('default')
            cart_dict = redis_conn.hgetall('cart_%s' % user.id)

            # 定义临时变量
            total_count = 0
            total_amount = 0 # 包含运费的，实付款

            # 截取出sku_ids列表
            sku_ids = sku_ids.split(',') # '1，2，3' --》 [1,2,3]
            # 遍历sku_ids
            for sku_id in sku_ids:

                # 循环取出sku，判断商品是否存在
                try:
                    sku = GoodsSKU.objects.get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    # 异常，回滚
                    transaction.savepoint_rollback(save_point)
                    return JsonResponse({'code': 5, 'message': '商品不存在'})

                # 获取商品数量，判断库存 (redis)
                sku_count = cart_dict.get(sku_id.encode())
                sku_count = int(sku_count)
                # 判断库存不足
                if sku_count > sku.stock:
                    # 异常，回滚
                    transaction.savepoint_rollback(save_point)
                    return JsonResponse({'code': 6, 'message': '库存不足'})

                # 减少sku库存
                sku.stock -= sku_count
                # 增加sku销量
                sku.sales += sku_count
                sku.save()

                # 保存订单商品数据OrderGoods(能执行到这里说明无异常)
                OrderGoods.objects.create(
                    order = order,
                    sku = sku,
                    count = sku_count,
                    price = sku.price
                )

                # 计算总数和总金额
                total_count += sku_count
                total_amount += sku_count * sku.price

            # 修改订单信息里面的总数和总金额(OrderInfo)
            order.total_count = total_count
            order.total_amount = total_amount + 10
            order.save()

        except Exception:
            # 异常，回滚
            transaction.savepoint_rollback(save_point)
            return JsonResponse({'code':7, 'message':'下单失败'})

        # 没错，直接提交
        transaction.savepoint_commit(save_point)

        # 订单生成后删除购物车(hdel)
        redis_conn.hdel('cart_%s'%user.id, *sku_ids)  # [1,2,3] ==> 1 2 3

        # 响应结果
        return JsonResponse({'code':0, 'message':'提交订单成功'})


class PlaceOrderView(LoginRequiredMixin, View):
    """订单确认"""

    def post(self, request):
        """处理去结算和立即购买逻辑"""

        # 获取参数：sku_ids, count
        sku_ids = request.POST.getlist('sku_ids')
        count = request.POST.get('count')

        # 校验sku_ids参数：not
        if not sku_ids:
            return redirect(reverse('cart:info'))

        # 创建redis连接对象和获取购物车数据
        redis_conn = get_redis_connection('default')
        user_id = request.user.id
        cart_dict = redis_conn.hgetall('cart_%s' % user_id)

        # 定义临时变量
        skus = []
        total_count = 0
        total_sku_amount = 0 # 不包含运费
        trans_cost = 10
        total_amount = 0

        # 校验count参数：用于区分用户从哪儿进入订单确认页面
        if count is None:
            # 如果是从购物车页面过来
            # 查询商品数据
            for sku_id in sku_ids:
                try:
                    sku = GoodsSKU.objects.get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    return redirect(reverse('cart:info'))

                # 商品的数量从redis中获取
                sku_count = cart_dict.get(sku_id.encode())
                try:
                    sku_count = int(sku_count)
                except Exception:
                    # 此处上课时，响应json是错误的
                    #return JsonResponse({'code':10, 'message':'没有商品'})
                    # 需要重定向到某个页面，比如重定向到购物车
                    return redirect(reverse('cart:info'))

                # 计算小计
                amount = sku_count * sku.price

                # 动态绑定属性
                sku.count = sku_count
                sku.amount = amount
                # 记录sku
                skus.append(sku)

                # 累加总件数和总金额（不含运费）
                total_count += sku_count
                total_sku_amount += amount # 不含运费

        else:
            # 如果是从详情页面过来
            # 查询商品数据：只会遍历一次，就一个元素
            for sku_id in sku_ids:
                try:
                    sku = GoodsSKU.objects.get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    return redirect(reverse('cart:info'))

                # 校验count:# 商品的数量从request中获取,并try校验
                try:
                    sku_count = int(count)
                except Exception:
                    return redirect(reverse('goods:detail', args=sku_id))

                # 判断库存：立即购买没有判断库存
                if sku_count > sku.stock:
                    return redirect(reverse('goods:detail', args=sku_id))

                # 计算小计
                amount = sku_count * sku.price
                # 动态绑定属性
                sku.count = sku_count
                sku.amount = amount
                # 记录sku
                skus.append(sku)
                # 累加总数量和总金额（不包含运费）
                total_count += sku_count
                total_sku_amount += amount # 不包含运费

                # 写入到购物车
                redis_conn.hset('cart_%s'%user_id, sku_id, count)

        # 计算实付款
        total_amount = total_sku_amount + trans_cost

        # 查询用户地址信息:按照最近的地址排序
        try:
            address = Address.objects.filter(user=request.user).latest('create_time')
        except Address.DoesNotExist:
            address = None

        # 构造上下文
        context = {
            'skus':skus,
            'total_count':total_count,
            'total_sku_amount':total_sku_amount,
            'trans_cost':trans_cost,
            'total_amount':total_amount,
            'address':address,
            'sku_ids':','.join(sku_ids) # [1,2,3] ==> '1,2,3'
        }

        # 响应结果:html页面
        return render(request, 'place_order.html', context)
