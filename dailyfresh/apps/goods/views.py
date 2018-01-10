from django.shortcuts import render
from django.views.generic import View

# Create your views here.


class IndexView(View):
    """主页"""

    def get(self, request):
        """提供主页页面"""
        return render(request, 'index.html')