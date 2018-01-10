from celery import Celery
from django.conf import settings
from django.core.mail import send_mail
import os

os.environ['DJANGO_SETTINGS_MODULE'] = 'dailyfresh.settings'
import django
django.setup()


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
