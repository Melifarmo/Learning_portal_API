from django.urls import path
from . import views

urlpatterns = [
    path('course/', views.CourseAPIView.as_view()),
]