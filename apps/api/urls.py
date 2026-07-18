from django.urls import path

from . import views

app_name = 'api'

urlpatterns = [
    path('', views.index, name='index'),
    path('create-token/', views.create_token, name='create_token'),
    path('delete-token/<int:token_id>/', views.delete_token, name='delete_token'),
]