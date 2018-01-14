from django.contrib import admin
from goods.models import GoodsCategory, Goods, IndexPromotionBanner
# from celery_tasks.tasks import generate_static_index_html
from django.core.cache import cache


# Register your models here.


class BaseAdmin(admin.ModelAdmin):

    def save_model(self, request, obj, form, change):
        """后台在保存数据时会自动调用的"""

        # 调用父类的save:实现父类本该实现的事情
        obj.save()

        # 触发异步生成静态主页
        generate_static_index_html.delay()

        # 当发现有人在修改数据时，需要立即清空缓存
        cache.delete('index_page_data')

    def delete_model(self, request, obj):
        """删除数据时调用的"""

        obj.delete()
        generate_static_index_html.delay()
        cache.delete('index_page_data')


class IndexPromotionBannerAdmin(BaseAdmin):
    """主页活动信息模型类的管理类"""

    # 有可能需要处理其他样式可能
    # list_display = []

    pass

class GoodsAdmin(BaseAdmin):
    """主页活动信息模型类的管理类"""

    # 有可能需要处理其他样式可能
    # list_per_page = 10

    pass

admin.site.register(IndexPromotionBanner, IndexPromotionBannerAdmin)
admin.site.register(GoodsCategory)
admin.site.register(Goods, GoodsAdmin)
