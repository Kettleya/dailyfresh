from django.contrib.auth.decorators import login_required

class LoginRequiredMixin(object):
    """login_required装饰器,装饰类视图调用as_view后的参数"""
    @classmethod
    def as_view(cls,**initkwargs):
        """重写as_view()"""

        # 获取类视图调用as_view()后的结果(view)
        view = super().as_view(**initkwargs)

        return login_required(view)