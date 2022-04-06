from django.db import models
from django.contrib.auth import get_user_model


User = get_user_model()


class Course(models.Model):
    title = models.CharField(max_length=255, verbose_name='Название курса')

    objects = models.Manager()

    @property
    def first_lesson(self):
        return self.all_lessons.order_by('order').first()

    @property
    def last_lesson(self):
        return self.all_lessons.order_by('-order').first()

    @property
    def all_lessons(self):
        return Lesson.objects.filter(course=self.id)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = '1. Курс'
        verbose_name_plural = '1. Курсы'


class Lesson(models.Model):
    title = models.CharField(max_length=255, verbose_name='Название блока')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='lessons')
    order = models.IntegerField(verbose_name='Порядковый номер лекции')
    content = models.TextField(help_text='Текст лекции', verbose_name='Лекция')

    objects = models.Manager()

    @property
    def lesson_title(self):
        return self.title

    @property
    def test_len(self):
        return len(PresetAnswer.objects.filter(question__lesson=self.id))

    def __str__(self):
        if self.order:
            order = self.order
        else:
            order = '?'
        return f"{self.course.title} #{order}: {self.title}"

    class Meta:
        verbose_name = '1.2 Лекция'
        verbose_name_plural = '1.2 Лекции'
        unique_together = [['order', 'course']]


class Question(models.Model):
    title = models.CharField(max_length=255, help_text='Текст вопроса', verbose_name='Вопрос')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='questions')
    type = models.ForeignKey('QuestionType', on_delete=models.SET_DEFAULT, default=None, null=True)
    order = models.IntegerField(blank=True, null=True)

    objects = models.Manager()

    @property
    def question_title(self):
        return self.title

    @property
    def question_type(self):
        return self.type.title

    @property
    def is_multi_type_answer(self):
        return self.question_type == 'single' or self.question_type == 'multi'

    @property
    def all_options(self):
        if self.is_multi_type_answer:
            return PresetChoosableOption.objects.filter(question=self.id)
        return []

    @property
    def right_options(self):
        if self.is_multi_type_answer:
            return self.all_options.filter(correct_answer=True)
        return []

    def __str__(self):
        return f"{self.lesson.lesson_title}: {self.title}"

    class Meta:
        verbose_name = '1.3 Вопрос к блоку'
        verbose_name_plural = '1.3 Вопросы к блокам'


class QuestionType(models.Model):
    title = models.CharField(max_length=64)

    objects = models.Manager()

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = '1.3 Тип вопроса'
        verbose_name_plural = '1.3 Типы вопросов'


class PresetAnswer(models.Model):
    question = models.OneToOneField(Question, on_delete=models.CASCADE, related_name='preset_answer')
    text = models.TextField(blank=True, null=True)
    boolean = models.BooleanField(blank=True, null=True)
    options = models.ManyToManyField('PresetChoosableOption', blank=True)
    mapped_answers = models.ManyToManyField('PresetMappedOption', blank=True)

    objects = models.Manager()

    @property
    def lesson(self):
        return self.question.lesson

    @property
    def question_type(self):
        return self.question.question_type

    def __str__(self):
        return f"{self.question}: {self.question.question_type}"

    class Meta:
        verbose_name = '2. Задуманный ответ'
        verbose_name_plural = '2. Задуманные ответы'


class PresetChoosableOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='preset_options')
    title = models.CharField(max_length=128)
    correct_answer = models.BooleanField()

    objects = models.Manager()

    @property
    def lesson(self):
        return self.question.lesson

    @property
    def question_related_name(self):
        return 'question_answer'

    def __str__(self):
        return f"{self.title} ({self.correct_answer})"

    class Meta:
        verbose_name = '2.1 Вариант ответа к вопросу'
        verbose_name_plural = '2.1 Варианты ответов к вопросу'


class PresetMappedOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='mapped_preset_options')
    title = models.CharField(max_length=64)
    group = models.ForeignKey('PresetMappedOptionGroup', on_delete=models.CASCADE,
                              related_name='preset_mapped_answers', default=None)

    objects = models.Manager()

    @property
    def lesson(self):
        return self.question.lesson

    @property
    def group_title(self):
        return self.group.title

    @property
    def question_related_name(self):
        return 'mapped_preset_options'

    def __str__(self):
        return f"{self.group}: {self.title} ({self.question.question_title})"

    class Meta:
        verbose_name = '2.2 Вариант ответа с сопоставлением'
        verbose_name_plural = '2.2 Варианты ответов с сопоставлением'


class PresetMappedOptionGroup(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='mapped_group_preset', default=None)
    title = models.CharField(max_length=64)

    objects = models.Manager()

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = '2.3 Группа для вопросов с сопоставлением'
        verbose_name_plural = '2.3 Группы для вопросов с сопоставлением'


class CoursePersonalProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='course_progress')
    completed = models.BooleanField(help_text='Лекция завершена?', verbose_name='Завершен', default=False)

    objects = models.Manager()

    @property
    def first_lesson(self):
        return self.course.first_lesson

    @property
    def last_lesson(self):
        return self.course.last_lesson

    @property
    def current_lesson(self):
        lessons_progress = LessonPersonalProgress.objects.filter(course_progress=self.id)
        for lesson in lessons_progress:
            if not lesson.completed:
                return lesson
        return None

    @property
    def next_lesson(self):
        if self.last_lesson != self.current_lesson:
            next_lessons = self.course.all_lessons.filter(order__gt=self.current_lesson.order)
            next_lesson = next_lessons.order_by('order').first()
            return next_lesson
        else:
            return None

    def __str__(self):
        return f"{self.user.username}: {self.course} (пройден: {self.completed})"

    class Meta:
        verbose_name = '3. Курс(Прогресс)'
        verbose_name_plural = '3. Курс(Прогресс)'
        unique_together = [['user', 'course']]


class LessonPersonalProgress(models.Model):
    course_progress = models.ForeignKey(CoursePersonalProgress, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='lesson_progress')
    completed = models.BooleanField(default=False)
    lesson_part_completed = models.BooleanField(help_text='Лекция изучена?', default=False,
                                                verbose_name='Теоретическая часть')
    test_part_completed = models.BooleanField(help_text='Тест пройден?', verbose_name='Тест', default=False)

    objects = models.Manager()

    @property
    def answers(self):
        return Answer.objects.filter(lesson_progress=self.id)

    @property
    def order(self):
        return self.lesson.order

    @property
    def course(self):
        return self.course_progress.course

    @property
    def user(self):
        return self.course_progress.user

    @property
    def course_last_lesson(self):
        return self.course.last_lesson

    @property
    def next_lesson(self):
        return self.course_progress.next_lesson

    @property
    def is_last_block(self):
        return self.course_last_lesson == self.lesson

    def __str__(self):
        return f"{self.course_progress.course.title}: {self.lesson.lesson_title} ({self.completed})"

    class Meta:
        verbose_name = '3.1 Лекция(Прогресс)'
        verbose_name_plural = '3.1 Лекция(Прогресс)'
        unique_together = [['course_progress', 'lesson']]


class Answer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.OneToOneField(Question, on_delete=models.CASCADE, related_name='user_answers')
    lesson_progress = models.ForeignKey(LessonPersonalProgress, on_delete=models.CASCADE, related_name='user_answers')
    text = models.TextField(blank=True, null=True)
    boolean = models.BooleanField(blank=True, null=True)
    single_answer = models.ForeignKey(PresetChoosableOption, on_delete=models.CASCADE,
                                      related_name='user_single_answers',
                                      blank=True, null=True)
    multi_answers = models.ManyToManyField(PresetChoosableOption, blank=True, related_name='user_answers')
    mapped_answers = models.ManyToManyField('MappedAnswer', blank=True, related_name='user_answers')

    objects = models.Manager()

    @property
    def question_type(self):
        return self.question.question_type

    def __str__(self):
        text_templates = {'text': self.text,
                          'multi': ' '.join([answer.title for answer in self.multi_answers.all()]),
                          'boolean': self.boolean,
                          'single': self.single_answer,
                          'mapped': self.mapped_answers}
        return f"{self.user.username}: {text_templates[self.question_type]} / ({self.question.question_title})"

    class Meta:
        verbose_name = '4. Ответ пользователя'
        verbose_name_plural = '4. Ответы пользователей'
        unique_together = [['question', 'user']]


class MappedAnswer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, default=None)
    value = models.ForeignKey(PresetMappedOption, on_delete=models.CASCADE, default=None,
                              related_name='user_mapped_answers')
    group = models.ForeignKey(PresetMappedOptionGroup, on_delete=models.CASCADE, default=None,
                              related_name='user_mapped_answers')

    objects = models.Manager()

    @property
    def title(self):
        return self.value.title

    def __str__(self):
        return f"{self.value} ({self.group})"

    class Meta:
        verbose_name = '4.1 Ответ с сопоставлением'
        verbose_name_plural = '4.1 Ответы с сопоставлением'

