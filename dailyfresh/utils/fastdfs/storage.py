from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client
from django.conf import settings

class FastDFSStorage(Storage):
    """自定义Django存储的类"""

    def __init__(self,client_conf=None,server_ip=None):
        """初始化数值,设置参数"""
        if client_conf is None:
            client_conf = settings.CLIENT_CONF
        self.client_conf = client_conf

        if server_ip is None:
            server_ip = settings.SERVER_IP
        self.server_ip = server_ip


    def open(self, name, mode='rb'):
        """读取文件时使用"""
        pass


    def save(self, name, content):
        """存储文件时使用,第二个参数是文件名,第三个参数是上传的file对象"""

        # 创建fdsf客户端对象
        client = Fdfs_client(self.client_conf)

        # 获取client中的数据
        file_data = content.read()

        # 调用上传文件的方法,upload_file_by_filename,by_buffer
        try:
            ret = client.upload_by_buffer(file_data)
        except Exception as e:
            print(e) # 方便自己测试时查询异常
            raise

        # 判断是否上传成功
        if ret.get('Status') == 'Upload successed.':
            # 上传成功,取出file_id,储存到Django数据表中
            file_id = ret.get('Remote file_id')
            # 通过那个模型保存的类,就会自动的保存到该模型类对应的表中
            return file_id
        else:
            # 上传失败,抛出异常
            raise Exception('文件上传失败')

    def exists(self, name):
        """判断要上传的文件,在Django中是否存在,如果存在返回True,就不用调用save,反之,就会调用save"""
        return False

    def url(self,name):
        """会返回存储文件的地址"""
        return self.server_ip + name