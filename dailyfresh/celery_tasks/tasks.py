import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'dailyfresh.settings'
import django
django.setup()


from celery import Celery
from django.conf import settings
from django.core.mail import send_mail
from django.template import loader
from goods.models import GoodsCategory,Goods,GoodsSKU,GoodsImage,IndexGoodsBanner,IndexCategoryGoodsBanner,IndexPromotionBanner



# 创建celery客户端
app = Celery('celery_tasks.tasks', broker='redis://192.168.80.128:6379/4')


# 定义异步任务
@app.task
def send_active_email(to_email, user_name, token):
    """发送激活邮件"""

    subject = "天天生鲜用户激活"  # 标题
    body = ""  # 文本邮件体
    sender = settings.EMAIL_FROM  # 发件人
    receiver = [to_email]  # 接收人
    html_body = '<h1>尊敬的用户 %s, 感谢您注册天天生鲜！</h1>' \
                '<br/><p>请点击此链接激活您的帐号<a href="http://127.0.0.1:8000/users/active/%s">' \
                'http://127.0.0.1:8000/users/active/%s</a></p>' % (user_name, token, token)
    send_mail(subject, body, sender, receiver, html_message=html_body)



@app.task
def generate_static_index_html():
    # 查询用户数据
    categorys = GoodsCategory.objects.all()

    # 查询图片轮播图
    index_banners = IndexGoodsBanner.objects.all().order_by('index')

    # 查询商品活动数据
    promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

    # 查询购物车信息
    cart_num = 0

    # 查询主页商品分类数据信息
    for category in categorys:
        # 查询文字形式展示的商品
        title_banners = IndexCategoryGoodsBanner.objects.filter(category=category,display_type=0).order_by('index')
        category.title_banners = title_banners

        image_banners = IndexCategoryGoodsBanner.objects.filter(category=category,display_type=1).order_by('index')
        category.image_banners = image_banners
    # 构造上下文
    context = {
        'categorys':categorys,
        'index_banners':index_banners,
        'promotion_banners':promotion_banners,
        'cart_num':cart_num,
    }

    # 渲染模板:要生成和存储的是被context渲染后的主页模板界面
    template = loader.get_template('static_index.html')
    html_data = template.render(context)

    # 把html存储到某个位置,比如nginx服务器上某个文件夹中
    file_path = os.path.join(settings.STATICFILES_DIRS[0],'index.html')

    with open(file_path,'w') as file:
        file.write(html_data)
