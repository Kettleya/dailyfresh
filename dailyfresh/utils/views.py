from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from functools import wraps
from django.db import transaction


class LoginRequiredMixin(object):
    """login_required装饰器，装饰类视图调用as_view()后的结果"""

    @classmethod
    def as_view(cls, **initkwargs):
        """重写as_view()"""

        # 获取类视图调用as_view()后的结果（view）
        view = super().as_view(**initkwargs)

        # login_required装饰器结果(view)
        return login_required(view)


def login_required_json(view_func):
    """用户限制访问和json交互的装饰器"""

    # 还原被装饰的函数的名字和说明文档
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        if not request.user.is_authenticated():
            # 当用户未登陆，响应json数据ajax,提示用户未登录
            return JsonResponse({'code':1,'message':'用户未登录'})
        else:
            # 当用户已登陆，进入到具体要执行的view_func
            return view_func(request, *args, **kwargs)

    return wrapper


class LoginRequiredJsonMixin(object):
    """封装用户限制访问和json交互的装饰器的类"""

    @classmethod
    def as_view(cls, **initkwargs):
        """重写as_view()"""

        # 获取类视图调用as_view()后的结果（view）
        view = super().as_view(**initkwargs)

        # login_required_json装饰器结果(view)
        return login_required_json(view)


class TransactionAtomicMixin(object):
    """封装事务的装饰器的类"""

    @classmethod
    def as_view(cls, **initkwargs):
        """重写as_view()"""

        # 获取类视图调用as_view()后的结果（view）
        view = super().as_view(**initkwargs)

        # login_required_json装饰器结果(view)
        return transaction.atomic(view)

