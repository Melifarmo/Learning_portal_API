from django.urls import path, include
from . import views

urlpatterns = [
    path('create-user/', views.CreateUser.as_view()),
    path('login/', views.user_login),

    path('get-course-scheme/', views.get_course_scheme),
    path('start-course/', views.start_course),

    path('get-lesson-content/', views.get_lesson),
    path('complete-lesson-part/', views.complete_lesson),

    path('get-test/', views.get_test),
    path('save-test/', views.save_test_stage),
    path('complete-test/', views.complete_test),
]