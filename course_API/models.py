from django.db import models


# Create your models here.
class LessonCourse(models.Model):
    title = models.CharField(max_length=255, verbose_name="Название курса")
    premium = models.BooleanField(default=False)

    objects = models.Manager()

    def __str__(self):
        return self.title


class LearningBlock(models.Model):
    title = models.CharField(max_length=255, verbose_name='Название блока')
    course = models.ForeignKey(LessonCourse, on_delete=models.CASCADE)
    order_priority = models.IntegerField(blank=True, null=True, verbose_name='Приоритет внутри курса')
    content = models.TextField(help_text='Текст лекции', verbose_name='Лекция')
    # test = models.ForeignKey('asd', on_delete=models.CASCADE)

    objects = models.Manager()

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'Блок обучения'
        verbose_name_plural = 'Блоки обучения'
        unique_together = [['course', 'order_priority']]
