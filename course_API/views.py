from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from .serializers import CourseSerializer

from . import models


# Create your views here.
class CourseAPIView(APIView):
    def get(self, request):
        course = models.LessonCourse.objects.all()
        serializer = CourseSerializer(course, many=True)
        return Response({"courses": serializer.data})
