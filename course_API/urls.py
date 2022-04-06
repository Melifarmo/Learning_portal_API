from django.urls import path, include
from . import views

urlpatterns = [
    path('create-user/', views.CreateUser.as_view()),
    path('login/', views.user_login),

    path('course/', views.CourseGenericSet.as_view({"get": "get_course_scheme",
                                                    "post": "start_course"})),

    path('lesson/', views.LessonViewSet.as_view({"get": "get_lesson",
                                                 "post": "complete_lesson"})),

    path('test/', views.TestViewSet.as_view({"get": "get_test",
                                             "post": "complete_test"})),
    path('save-test/', views.TestViewSet.as_view({"post": "save_test_stage"})),
]