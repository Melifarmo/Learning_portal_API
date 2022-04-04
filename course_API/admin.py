from django.contrib import admin

# Register your models here.
from . import models


admin.site.register(models.LessonCourse)
admin.site.register(models.LearningBlock)