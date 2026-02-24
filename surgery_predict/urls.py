from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # บรรทัดนี้สำคัญมาก! ถ้าไม่มี Django จะมองไม่เห็น urls ใน main
    path('', include('main.urls')), 
]