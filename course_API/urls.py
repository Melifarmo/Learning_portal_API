from django.urls import path, include
from . import views

urlpatterns = [
    path('create-user/', views.CreateUser.as_view()),
    path('login/', views.user_login),

    path('get-lesson-scheme/', views.get_course_scheme),
    path('start-course/', views.start_course),
    path('complete-lesson-part/', views.complete_lesson),
    # path('complete-test-part/', views.complete_lesson),
    path('get-lesson-content/', views.get_lesson),

    path('get-test/', views.get_test)
]