from django.contrib.auth import authenticate
from .serializers import CourseSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.generics import CreateAPIView
from rest_framework.viewsets import GenericViewSet
from rest_framework.authtoken.models import Token
from rest_framework.status import HTTP_200_OK
from django.views.decorators.csrf import csrf_exempt

from django.dispatch import receiver
from django.db.models.signals import post_save, pre_save

from course_API.serializers import UserSerializer
from course_API import models
import json


# Logic/Receivers
@receiver(pre_save, sender=models.LessonPersonalProgress)
def lesson_progress_auto_creater(sender, instance, **kwargs):
    """
    When some lesson_block has been completed or vice versa has been uncompleted
    then create or delete lesson_progress to next_lesson
    """
    if instance.id is None:
        pass
    else:
        progress = instance
        previous_progress = models.LessonPersonalProgress.objects.get(id=progress.id)
        is_last_block = instance.is_last_block
        course = progress.course

        if previous_progress.completed != progress.completed:
            if progress.completed:
                if progress.test_part_completed and progress.lesson_part_completed and not is_last_block:
                    create_next_progress_block(progress)
                else:
                    course.completed = True
            else:
                if not is_last_block:
                    pass
                    delete_next_progress_block(progress)
                else:
                    course.completed = False
                reset_lesson_progress(progress, sender)


@receiver(post_save, sender=models.CoursePersonalProgress)
def create_first_lesson_then_course_start(sender, instance, created, **kwargs):
    """
    Then course has been started, create first lesson_progress
    """
    if created:
        models.LessonPersonalProgress.objects.create(course_progress=instance,
                                                     lesson=instance.first_lesson)


# Views
class CreateUser(CreateAPIView):
    """
    POST method
    In POST body take username field and password, and after registering your Token
    """
    permission_classes = (
        AllowAny,)
    serializer_class = UserSerializer


@csrf_exempt
@api_view(['POST'])
@permission_classes((AllowAny,))
def user_login(request):
    """
    POST method
    In post body take username field and password, after sending you your authToken
    """
    username = request.data.get('username')
    password = request.data.get('password')
    if username is None or password is None:
        return Response({'error': 'Please username and password'})
    else:
        user = authenticate(username=username, password=password)
        if not user:
            Response({'error': 'Invalid data'})
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key}, status=HTTP_200_OK)


class CommonCourseAPIGenericSet(GenericViewSet):
    """
    Collect general func and properties for the APISet
    """
    def __init__(self):
        super(CommonCourseAPIGenericSet, self).__init__()
        self.error_message = None

    @staticmethod
    def get_error_response(message):
        return Response({"success": False,
                         "error": message})

    @staticmethod
    def get_success_response(message):
        return Response({"success": True,
                         "message": message})

    @property
    def user(self):
        user_id = Token.objects.get(key=self.request.auth.key).user_id
        return models.User.objects.get(id=user_id)

    def get_id_from_params(self):
        return self.request.GET.get('id')

    def get_queryset(self):
        return self.queryset.get(pk=self.get_id_from_params())

    def get_serialized_data(self):
        return self.serializer_class(self.get_queryset())


class CourseGenericSet(CommonCourseAPIGenericSet):
    """
    GET method - in params need field "id" with course id/
        Give you course scheme with lesson and questions without answers
    POST method (start_course) - in params need field "id" with course id
        Open for you that course if you don't do it before. Now you can take a lesson and test
    """
    queryset = models.Course.objects.all()
    serializer_class = CourseSerializer

    @property
    def is_course_available(self):
        course_progress = self.get_queryset().get_course_progress(self.user)
        return course_progress and not course_progress.completed

    def get_course_scheme(self, request):
        if self.is_course_available:
            return Response({"course": self.get_serialized_data().data})
        return self.get_error_response("Курс не существует или недоступен")

    def start_course(self, request):
        course_progress, created = self.create_course_progress()
        if created:
            return self.get_success_response("Курс успешно начат")
        return self.get_error_response("Курс уже был начат")

    def create_course_progress(self):
        instance, created = models.CoursePersonalProgress.objects.get_or_create(
            user=self.user,
            course=self.get_queryset()
        )
        return instance, created


class LessonGenericMIX(GenericViewSet):
    queryset = models.Lesson.objects.all()

    @property
    def lesson(self):
        return self.get_queryset()

    @property
    def progress(self):
        lesson = self.get_queryset()
        return lesson.get_personal_progress(self.user)

    @property
    def is_test_available(self):
        return self.progress and not self.progress.completed and \
               self.progress.lesson_part_completed and self.lesson

    @property
    def is_can_complete_lesson_part(self):
        return self.lesson and self.progress and self.lesson.is_lesson_available_for_user(self.user) \
               and not self.progress.lesson_part_completed


class LessonGenericViewSet(CommonCourseAPIGenericSet, LessonGenericMIX):
    """
    GET method - in params need field "id" with lesson id
        give you a text part of lesson
    POST method - in params need field "id" with lesson id
        complete a text part of lesson and give you access to test
    """

    def get_lesson(self, request):
        if self.is_can_complete_lesson_part:
            return Response({'lesson_content': self.lesson.content})

        return Response({'error': 'На данный момент вы не имеете доступ к данному учебному материалу '
                                  'или материал не существует'})

    def complete_lesson(self, request):
        if self.is_can_complete_lesson_part:
            complete_lesson_text_part(self.progress)
            return Response({'message': f'Этап "{self.lesson.title}" успешно завершен'})
        else:
            if self.lesson:
                error = 'Вы не можете завершить изучение лекции, или уже завершили его в прошлом'
            else:
                error = 'Данной лекции не существует'
        return self.get_error_response(error)


class TestGenericViewSet(CommonCourseAPIGenericSet, LessonGenericMIX):
    """
    GET method - takes lesson's id in params
        give you a test. Questions + options if it has.
    POST method to save-test/ - takes lesson's id in params and field answers in POST body
        save a test temporary stage
    POST method to test/ - takes lesson's id in params and field answers in POST body
        try complete test part if correct, if it's complete lesson block
        and create next or complete course if it is the last lesson
    JSON structure -
{
    "answers":
    {
        answers : [
            {
                // text
                "question": id,
                "answer": str
            },
            {
                // boolean
                "question": id,
                "answer": True/False
            },
            {
                // single
                "question": id,
                "answer": id
            },
            {
                // multi
                "question": id,
                "answer": [id, id, ...]
            },
            {
                // mapped
                "question": id,
                "answer": [{"title": id, "group": id}, {"title": id, "group": id}, ...]
            }
        ]
    }
}
    """

    @property
    def questions(self):
        related_set = self.lesson.questions.filter()
        if related_set.count() > 1:
            return related_set
        return related_set.first()

    def get_test(self, request):
        if self.questions and self.is_test_available:
            data = []
            for question in self.questions:

                answer = get_answers(question)
                data.append(get_test_data(question, answer))
            return Response(data)

        if self.lesson:
            error = 'Тест недоступен'
        else:
            error = 'Лекции не существует'

        return self.get_error_response(error)

    def save_test_stage(self, request):

        success = message = False
        if self.is_test_available and self.questions:
            success, message = self.save_answers_from_json(request)
        if success:
            return Response({"message": message})
        return self.get_error_response(message)

    def complete_test(self, request):
        if self.is_test_available:
            answers = self.get_answers()
            success, _ = self.save_answers_from_json(request)

            if self.lesson.test_len == answers.count() and self.is_test_available:
                for answer in answers:
                    if not check_answer(answer):
                        return Response({"test_result": "К сожалению, вы не прошли тест"})
                complete_lesson_block(self.progress)
                return Response({"test_result": "Поздравляю! Тест успешно пройдет, "
                                                "вы можете перейти к следующему этапу, "
                                                "если он доступен"})

        error = 'Данный тест недоступен или недостаточно данных'
        return Response({'error': error})

    def get_answers(self):
        return self.progress.answers

    def get_raw_data(self):
        return self.request.POST.get('answers')

    def save_answers_from_json(self, request):
        raw_data = self.get_raw_data()

        if raw_data:
            try:
                data = json.loads(raw_data)
            except ValueError as except_text:
                message = f'Произошла ошибка при декодирование JSON - {except_text}'
            else:
                answers = data['answers']
                if answers:
                    for answer in answers:
                        self.save_answer(answer)

                    return True, 'Промежуточный результат теста сохранен'
                message = 'Нет ответов'
        else:
            message = "В body отсутствует 'answers'"
        return False, message

    def save_answer(self, answer_data):
        question = get_object_or_none(models.Question, pk=answer_data['question'])
        answers = answer_data['answer']
        if question:
            question_type = question.question_type
            answer_model = self.get_answer_model(question)

            if question_type == 'text':
                answer_model.text = answers
            elif question_type == 'boolean':
                answer_model.boolean = answers
            elif question_type == 'single' or question_type == 'multi':
                update_option_answer(answer_model, answers)
            else:
                update_mapped_answer(answer_model, answers)
            answer_model.save()

    def get_answer_model(self, question):
        answer_model, _ = models.Answer.objects.get_or_create(
            question=question,
            user=self.user,
            lesson_progress=self.progress)
        return answer_model


def check_answer(current_answer):
    question = current_answer.question
    question_type = question.question_type
    correct_answer = question.preset_answer

    if question_type == 'boolean':
        result = current_answer.boolean == correct_answer.boolean
    elif question_type == 'text':
        result = current_answer.text == correct_answer.text
    elif question_type == 'single':
        result = check_single_answer(current_answer, correct_answer)
    elif question_type == 'multi':
        result = check_multi_answer(current_answer, correct_answer)
    else:
        result = check_mapped_answer(current_answer, correct_answer)

    return result


def check_mapped_answer(current_answer, correct_answer):
    answers = current_answer.mapped_answers.all()
    right_mapped_answers = correct_answer.mapped_answers.all()
    if len(answers) == len(right_mapped_answers):
        for answer in answers:
            group = answer.group
            title = answer.title
            if not title == answer.value.title or not group == answer.value.group:
                return False
        return True
    return False


def check_multi_answer(current_answer, correct_answer):
    right_answers_set = set(correct_answer.question.right_options)
    user_correct_answers_set = set()
    answers = current_answer.multi_answers.all()

    if len(right_answers_set) == len(answers):
        user_correct_answers_set = [answer for answer in answers if answer in right_answers_set]

    if not right_answers_set.difference(user_correct_answers_set):
        return True
    return False


def check_single_answer(current_answer, correct_answer):
    right_answers_set = set(correct_answer.question.right_options)
    return current_answer.single_answer in right_answers_set


def update_mapped_answer(answer_model, answers):
    mapped_answers = get_mapped_answers_list(answer_model, answers)
    answer_model.mapped_answers.clear()
    for answer in mapped_answers:
        answer_model.mapped_answers.add(answer)


def get_mapped_answers_list(answer_model, answers):
    mapped_data = []
    for answer in answers:
        mapped_data.append(get_mapped_answer_model(answer, answer_model.question, answer_model.user))
    return mapped_data


def get_mapped_answer_model(answer, question, user):
    mapped_group = models.PresetMappedOptionGroup.objects.get(pk=answer['group'])
    mapped_option = models.PresetMappedOption.objects.get(pk=answer['value'])

    mapped_answer, _ = models.MappedAnswer.objects.get_or_create(group=mapped_group, value=mapped_option, user=user)
    return mapped_answer


def update_option_answer(answer_model, answers):
    question_type = answer_model.question.question_type

    if question_type == 'single':
        answer_model.single_answer = get_option_model(answers)
    else:
        for option_id in answers:
            answer_model.multi_answers.add(get_option_model(option_id))
    return answer_model


def get_option_model(option_id):
    return models.PresetChoosableOption.objects.get(pk=option_id)


def parsing_mapped_answers(answers):
    unique_group = {}
    options = []
    groups = []

    for option in answers:
        option_id = option['id']
        group_id = option['group_id']

        mapped_option = models.PresetMappedOption.objects.get(pk=option_id)
        group_title = models.PresetMappedOptionGroup.objects.get(pk=group_id).title

        unique_group[group_title] = group_id
        options.append({'id': mapped_option.id, 'title': mapped_option.title})

    for value, pk in unique_group.items():
        groups.append({'id': pk, 'title': value})
    return options, groups


def parsing_choosable_answers(answers):
    options = []
    for option in answers:
        options.append({'id': option.id, 'value': option.title})
    return options


def get_test_data(question, answers):
    question_type = question.question_type
    groups = []
    data = {'id': question.id, 'question': question.title}
    if question.is_multi_type_answer:
        if question_type == 'mapped':
            options, groups = parsing_mapped_answers(answers)
        else:
            options = parsing_choosable_answers(answers)
        options_data = {'values': options}
        if groups:
            options_data['groups'] = groups
        data['options'] = options_data
        return data
    return data


def get_answers(question):
    if hasattr(question, 'preset_answer'):
        preset_answer = models.PresetAnswer.objects.get(question=question.id)
        question_type = question.question_type

        if question_type == 'boolean':
            answer = preset_answer.boolean
        elif question_type == 'text':
            answer = preset_answer.text
        elif question_type == 'single' or question_type == 'multi':
            answer = preset_answer.options.all()
        elif question_type == 'mapped':
            answer = preset_answer.mapped_answers.values()
        else:
            answer = None
    return answer


def complete_lesson_text_part(model):
    model.lesson_part_completed = True
    model.save()


def complete_lesson_block(progress):
    progress.test_part_completed = True
    progress.completed = True
    progress.save()


# Support function
def show(message, func='', *args):
    print(f"\n---------------------------------------{func}")
    print(message)
    print('----------------------------------------')
    for arg in args:
        print(arg)


def get_object_or_none(model, *args, **kwargs):
    try:
        return model.objects.get(*args, **kwargs)
    except model.DoesNotExist:
        return


def get_model_or_none_from_related_set(related_set):
    if related_set.count() > 1:
        if related_set.count() > 1:
            return related_set
        return related_set.first()
    return None


# Receivers func
def create_next_progress_block(current_lesson_progress):
    course_progress = current_lesson_progress.course_progress
    models.LessonPersonalProgress.objects.create(course_progress=course_progress,
                                                 lesson=course_progress.next_lesson)


def delete_next_progress_block(current_lesson_progress):
    course_progress = current_lesson_progress.course_progress
    if course_progress.next_lesson:
        if current_lesson_progress.next_lesson:
            current_lesson = course_progress.next_lesson.id
        else:
            current_lesson = course_progress.current_lesson.id
        models.LessonPersonalProgress.objects.get(course_progress=course_progress, lesson=current_lesson).delete()


def reset_lesson_progress(progress, sender):
    progress.test_part_completed = False
    progress.lesson_part_completed = False
