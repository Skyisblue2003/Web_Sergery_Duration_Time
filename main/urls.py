
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.root_redirect, name='root'), 
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('predict/', views.predict_page, name='predict_page'),
    path('predict_submit/', views.predict_submit, name='predict_submit'),
]