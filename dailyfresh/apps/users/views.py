from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.generic import View,TemplateView
from django.core.urlresolvers import reverse
import re
from users.models import User, Address
from django.db import IntegrityError
from celery_tasks.tasks import send_active_email
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from django.conf import settings
from itsdangerous import SignatureExpired
from django.contrib.auth import authenticate, login, logout
from utils.views import LoginRequiredMixin
from django_redis import get_redis_connection
from goods.models import GoodsSKU


# Create your views here.


class UserInfoView(LoginRequiredMixin, View):
    """个人信息"""

    def get(self, request):
        """查询用户信息和浏览记录信息，并展示"""

        # 获取用户user：作用是为了作为Address的外键辅助查询
        user = request.user

        # 查询用户地址信息：查询后，需要按照时间倒序，就是按照时间取出最近编辑的地址信息
        # latest:会根据参数，进行倒序排序，并默认取出第0个
        try:
            address = user.address_set.latest('create_time')
        except Address.DoesNotExist:
            address = None

        # 从Redis数据库中，查询商品浏览记录
        # 创建redis连接对象
        redis_conn = get_redis_connection('default')
        # 查询列表中的浏览记录:假装浏览记录设计已经通过，浏览记录已经在详情页实现了
        sku_ids = redis_conn.lrange('history_%s'%user.id, 0, 4)

        sku_list = []
        # 遍历sku_ids,取出sku_id,用于查询商品sku信息
        for sku_id in sku_ids:
            sku = GoodsSKU.objects.get(id=sku_id)
            sku_list.append(sku)

        # 构造上下文
        context = {
            'address': address,
            'sku_list':sku_list
        }

        # 渲染模板
        return render(request, 'user_center_info.html', context)


class AddressView(LoginRequiredMixin, View):
    """用户地址"""

    def get(self, request):
        """提供地址页面"""

        # 获取用户user：作用是为了作为Address的外键辅助查询
        user = request.user

        # 查询用户地址信息：查询后，需要按照时间倒序，就是按照时间取出最近编辑的地址信息
        # address = Address.objects.filter(user=user).order_by('-create_time')[0]
        # address = user.address_set.order_by('-create_time')[0]
        # latest:会根据参数，进行倒序排序，并默认取出第0个
        try:
            address = user.address_set.latest('create_time')
        except Address.DoesNotExist:
            address = None

        # 构造上下文
        context = {
            # 由于模板中，render函数，已经接收了request,所以user不需要再上下文中
            # 'user':user,
            'address':address
        }

        # 渲染模板
        return render(request, 'user_center_site.html', context)

    def post(self, request):
        """编辑地址"""

        # 获取用户编辑地址的请求参数
        recv_name = request.POST.get('recv_name')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        recv_mobile = request.POST.get('recv_mobile')

        # 校验参数 all()
        if all([recv_name, addr, zip_code, recv_mobile]):

            # 保存地址信息到数据库中
            Address.objects.create(
                user = request.user,
                receiver_name = recv_name,
                receiver_mobile = recv_mobile,
                detail_addr = addr,
                zip_code = zip_code
            )

        # 响应结果:根据文档开发，我在这里是重新刷新一个地址页，测试地址是否保存
        return redirect(reverse('users:address'))


class LogoutView(View):
    """退出登录"""

    def get(self, request):
        """处理退出登录逻辑"""
        logout(request)
        return redirect(reverse('goods:index'))


class LoginView(View):
    """登陆"""

    def get(self, request):
        """提供登陆界面"""
        return render(request, 'login.html')

    def post(self, request):
        """处理登陆逻辑"""

        # 获取用户登陆请求参数
        user_name = request.POST.get('username')
        pwd = request.POST.get('pwd')
        remembered = request.POST.get('remembered')
        # 获取next请求参数：用户login_required装饰，回到起点（从哪来，回哪去）'/users/address'
        next = request.GET.get('next')

        # 校验参数
        # 判断参数是否齐全，all()
        if not all([user_name, pwd]):
            return redirect(reverse('users:login'))

        # 验证用户，验证是否是我们的用户,django提供了用户验证
        user = authenticate(username=user_name, password=pwd)
        if user is None:
            return render(request, 'login.html', {'errmsg':'用户名或密码错误'})

        # 如果用户验证通过，判断是否激活
        if user.is_active is False:
            return render(request, 'login.html', {'errmsg': '请激活'})

        # 将该用户登入,login()：生成用户的session数据，并把sessionid写入到cookie
        login(request, user)

        # 记住用户名
        if remembered != 'on':
            request.session.set_expiry(0)
        else:
            request.session.set_expiry(60*60*24*10)

        # 在响应结果之前，需要判断请求地址中，是否有next参数，如果有，就说明是被login_required装饰器重定向过来的
        if next is not None:
            return redirect(next)
        else:
            # 响应结果:重定向到主页
            return redirect(reverse('goods:index'))


class ActiveView(View):
    """激活"""

    def get(self, request, token):
        """处理激活逻辑"""

        # 创建序列化器，要求跟序列化user_id时参数一致
        serializer = Serializer(settings.SECRET_KEY, 3600)

        # 翻转token,{'confirm':'user_id'}
        try:
            result = serializer.loads(token)
        except SignatureExpired:
            # 过期异常处理
            return HttpResponse('激活链接已过期')

        # 获取user_id
        user_id = result.get('confirm')

        # 查询要激活的用户
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return HttpResponse('用户不存在')

        # 修改激活状态
        user.is_active = True
        user.save()

        # 响应结果:根据开发文档而定
        return redirect(reverse('users:login'))


class RegisterView(View):
    """类视图：注册"""

    def get(self, request):
        """提供注册页面"""
        return render(request, 'register.html')

    def post(self, request):
        """处理注册逻辑"""

        # 1.获取请求参数，注册数据
        user_name = request.POST.get('user_name')
        pwd = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 2.校验请求参数
        # 判断请求参数是否齐全：all(可迭代对象)，只要有一个为空，就返回空、假
        if not all([user_name, pwd, email]):
            # 具体如何处理用户参数不全，根据需求文档而定
            return redirect(reverse('users:register'))

        # 3.判断邮箱格式
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg':'邮箱格式错误'})

        # 4.判断是否勾选用户协议
        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请勾选用户协议'})

        # 5.保存用户注册数据到数据库：Django的用户认证系统，自动加密密码，重名的异常，不需要调用save()
        try:
            user = User.objects.create_user(user_name, email, pwd)
        except IntegrityError:
            # 重名异常
            return render(request, 'register.html', {'errmsg': '用户已存在'})

        # 6.重置激活状态（注意）:默认为True
        user.is_active = False
        # 修改后自己保存
        user.save()

        # 7.生成token
        token = user.generate_active_token()

        # 8.Celery异步发送激活邮件
        send_active_email.delay(email, user_name, token)

        # 9.响应结果：实际开发根据需求文档，我在这里重定向到首页
        return redirect(reverse('goods:index'))


# def register(request):
#     """函数视图：注册"""
#
#     if request.method == 'GET':
#         # 提供注册页面
#         return render(request, 'register.html')
#
#     if request.method == 'POST':
#         # 处理注册逻辑
#         return HttpResponse('收到POST请求，需要处理注册逻辑')