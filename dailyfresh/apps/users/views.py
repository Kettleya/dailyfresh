from django.shortcuts import render

# Create your views here.

# def register(request):
#     """返回注册页面"""
#     return render(request,'register.html')
from django.views.generic import View


class RegisterView(View):
    def get(self,request):
        return render(request,'register.html')

    def post(self,request):
        pass