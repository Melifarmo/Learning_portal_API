from rest_framework import serializers
from django.contrib.auth.models import User
from . import models


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ('username', 'password')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class SubChoosableOptionSerializer(serializers.ModelSerializer):

    class Meta:
        models = models.PresetChoosableOption
        fields = ['title']


class SubQuestionSerializer(serializers.ModelSerializer):
    title = serializers.CharField(max_length=255)
    order = serializers.IntegerField(read_only=True)

    class Meta:
        model = models.Question
        fields = ['id', 'title', 'order']


class SubLessonSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    order = serializers.IntegerField()
    test = SubQuestionSerializer(many=True, source='questions')

    class Meta:
        model = models.Lesson
        fields = ['title', 'course', 'order']

    def to_representation(self, instance):
        response = super().to_representation(instance)
        try:
            response['test'] = sorted((response['test']), key=(lambda x: x['order']))
        except TypeError:
            response['test'] = sorted((response['test']), key=(lambda x: x['id']))

        return response


class CourseSerializer(serializers.ModelSerializer):
    title = serializers.CharField(max_length=255)
    lessons = SubLessonSerializer(many=True)

    class Meta:
        model = models.Course
        fields = ['id', 'title', 'lessons']

    def to_representation(self, instance):
        response = super().to_representation(instance)
        try:
            response['lessons'] = sorted((response['lessons']), key=(lambda x: x['order']))
        except TypeError:
            response['questions'] = sorted((response['questions']), key=(lambda x: x['id']))

        return response
