
from django.shortcuts import render
from django.http import HttpResponse

def index(request):
    data = {"status": "success", "count": 42}
    return render(request, 'base/index.html')

def telegram(request):
    return render(request, 'base/telegram.html')