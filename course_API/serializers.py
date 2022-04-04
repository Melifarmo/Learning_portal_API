from rest_framework import serializers


class CourseSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    premium = serializers.BooleanField()
