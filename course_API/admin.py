from django.contrib import admin
from . import models

admin.site.register(models.Course)
admin.site.register(models.Lesson)
admin.site.register(models.Question)
admin.site.register(models.QuestionType)

admin.site.register(models.PresetAnswer)
admin.site.register(models.PresetChoosableOption)
admin.site.register(models.PresetMappedOption)
admin.site.register(models.PresetMappedOptionGroup)

admin.site.register(models.CoursePersonalProgress)
admin.site.register(models.LessonPersonalProgress)

admin.site.register(models.Answer)
admin.site.register(models.MappedAnswer)
