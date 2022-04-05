from django.contrib.auth import authenticate
from .serializers import CourseSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import CreateAPIView
from django.views.decorators.csrf import csrf_exempt
from rest_framework.viewsets import ModelViewSet, ViewSet
from rest_framework.authtoken.models import Token
from rest_framework.status import HTTP_200_OK
from . import models
from .serializers import UserSerializer
from django.dispatch import receiver
from django.db.models.signals import post_save, pre_save


@receiver(pre_save, sender=models.LessonPersonalProgress)
def lesson_progress_auto_creater(sender, instance, **kwargs):
    if instance.id is None:
        pass
    else:
        previous = models.LessonPersonalProgress.objects.get(id=instance.id)
        if previous.completed != instance.completed and \
                instance.test_part_completed and instance.lesson_part_completed:
            last_block_id = instance.course_progress.last_lesson.id
            create_or_delete_next_lesson_progress(instance, previous, last_block_id)


@receiver(post_save, sender=models.CoursePersonalProgress)
def create_first_lesson_stage(sender, instance, created, **kwargs):
    if created:
        first_block = instance.first_lesson
        models.LessonPersonalProgress.objects.create(course_progress=instance, lesson=first_block)


@csrf_exempt
@api_view(['POST'])
@permission_classes((AllowAny,))
def user_login(request):
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


class CreateUser(CreateAPIView):
    permission_classes = (
        AllowAny,)
    serializer_class = UserSerializer


class CourseAPIViewSet(ModelViewSet):
    queryset = models.Course.objects.all()
    serializer_class = CourseSerializer


@api_view(['GET'])
def get_course_scheme(request, pk=None):
    course_id = request.GET.get('id')
    course = get_object_or_none(models.Course, pk=course_id)
    if course:
        course_data = CourseSerializer(course)
        course_progress = get_model_or_none_from_related_set(course.course_progress.all())
        if course_progress:
            completed_status = course_progress.completed
        else:
            completed_status = False
        return Response({'completed': completed_status, 'course': course_data.data})
    return Response({'error': 'Данного курса не существует'})


@api_view(['GET'])
def get_test(request):
    lesson_id = request.GET.get('id')
    lesson = get_object_or_none(models.Lesson, pk=lesson_id)
    user = get_user_instance(request)
    data = []

    if lesson:
        progress = get_block_progress_or_none(lesson, user)
        if progress and test_available(progress):
            questions = get_model_or_none_from_related_set(lesson.questions).filter()
            if questions:
                for question in questions:
                    answer = get_answers(question)
                    data.append(get_test_data(question, answer))

                return Response(data)
            else:
                error = 'Лекция пока что не имеет тестовой части'
        else:
            error = 'Тест недоступен'
    else:
        error = 'Лекции не существует'
    return Response({'error': error})


@api_view(['POST'])
def start_course(request):
    user = get_user_instance(request)
    course_id = request.GET.get('id')
    course = get_object_or_none(models.Course, pk=course_id)
    if course:
        course_progress, created = models.CoursePersonalProgress.objects.get_or_create(user=user, course=course)
        if created:
            return Response({'course': f"'{course.title}' - начат!"})
        return Response({'error': f"'{course.title}' уже начат"})
    return Response({'error': 'Курса с таким id не существует'})


@api_view(['GET'])
def get_lesson(request):
    user = get_user_instance(request)
    lesson_id = request.GET.get('id')
    lesson = get_object_or_none(models.Lesson, pk=lesson_id)
    if lesson:
        if is_lesson_available_for_user(lesson, user):
            return Response({'lesson_content': lesson.content})
    return Response(
        {'error': 'На данный момент вы не имеете доступ к данному учебному материалу или материал не существует'})


@api_view(['PATCH'])
def complete_lesson(request):
    user = get_user_instance(request)
    lesson_id = request.GET.get('id')
    lesson = get_object_or_none(models.Lesson, pk=lesson_id)
    block_progress = get_block_progress_or_none(lesson, user)

    if lesson:
        if block_progress:
            if is_lesson_available_for_user(lesson, user):
                complete_lesson_text_part(block_progress)
                return Response({'message': f'Этап "{lesson.title}" успешно завершен'})
        error = 'Лекция пройдена или недоступна'
    elif block_progress:
        if block_progress.completed:
            error = 'Данный этап уже завершен'
        else:
            error = 'В данный момент вы не можете завершить эту лекцию'
    else:
        error = 'Данной лекции не существует'
    return Response({'error': error})




def show(message, func='-'):
    print()
    print(f"---------------------------------------{func}")
    print(message)
    print('----------------------------------------')


def lesson_prepared_for_close(lesson):
    if lesson.lesson_part_completed:
        if lesson.test_part_completed:
            return True
    return False


def is_m2m_type(type_of_question):
    if type_of_question == 'multi' or type_of_question == 'single' or type_of_question == 'mapped':
        return True
    return False


def parsing_mapped_answers(answers, groups, options):
    unique_group = {}
    for option in answers:
        show(option)
        group_title = models.PresetMappedOptionGroup.objects.get(pk=(option['group_id'])).title
        unique_group[group_title] = option['group_id']
        options.append({'id': option['id'], 'title': option['title']})

    for value, pk in unique_group.items():
        groups.append({'id': pk, 'title': value})


def parsing_choosable_answers(answers, options):
    for option in answers:
        options.append({'id': option.id, 'value': option.title})


def get_test_data(question, answers):
    type_of_question = question.question_type
    options = []
    groups = []
    data = {'id': question.id, 'question': question.title}
    show(answers, f'get_test_data {type_of_question}')
    if is_m2m_type(type_of_question):
        if type_of_question == 'mapped':
            parsing_mapped_answers(answers, groups, options)
        else:
            parsing_choosable_answers(answers, options)
        options_data = {'values': options}
        if groups:
            options_data['groups'] = groups
        data['options'] = options_data
        return data
    return data


def get_answers(question):
    type_of_question = question.question_type
    answer = None
    if hasattr(question, 'preset_answers'):
        preset_answer = models.PresetAnswer.objects.get(question=question.id)
        if type_of_question == 'boolean':
            answer = preset_answer.boolean
        elif type_of_question == 'text':
            answer = preset_answer.text
        elif type_of_question == 'single' or type_of_question == 'multi':
            answer = preset_answer.options.all()
        elif type_of_question == 'mapped':
            answer = preset_answer.mapped_answers.values()
    return answer


def create_first_progress_block(course_progress, user):
    models.LessonPersonalProgress.objects.get_or_create(user=user, course_progress=course_progress)


def get_model_instance_or_404(model, pk):
    return model.objects.get_object_or_404(pk=pk)


def get_model_instance(model, pk):
    return model.objects.get(pk=pk)


def get_user_instance(request):
    user_id = Token.objects.get(key=request.auth.key).user_id
    return models.User.objects.get(id=user_id)


def get_object_or_none(model, *args, **kwargs):
    try:
        return model.objects.get(*args, **kwargs)
    except model.DoesNotExist:
        return


def is_lesson_progress_exist(lesson, user):
    try:
        lesson_progress = lesson.lesson_progress.get(course_progress__user=user)
    except:
        return False
    return True


def get_block_progress_or_none(lesson, user):
    if is_lesson_progress_exist(lesson, user):
        return lesson.lesson_progress.get(course_progress__user=user)


def is_lesson_available_for_user(lesson, user):
    if not is_lesson_progress_exist(lesson, user):
        return False
    progress = lesson.lesson_progress.get(course_progress__user=user)
    course_progress = progress.course_progress
    return course_progress.current_lesson == progress.lesson.id and not \
        course_progress.completed


def complete_lesson_text_part(model):
    model.lesson_part_completed = True
    model.save()


def get_model_or_none_from_related_set(related_set):
    if is_related_set_not_empty(related_set):
        if related_set.count() > 1:
            return related_set
        return related_set.first()
    return


def is_related_set_not_empty(related_set):
    if related_set.count() > 0:
        return True
    return False


def create_next_progress_block(current_lesson_progress):
    course_progress = current_lesson_progress.course_progress
    next_block_id = course_progress.next_lesson
    models.LessonPersonalProgress.objects.create(course_progress=course_progress, lesson=next_block_id)


def delete_next_progress_block(current_lesson_progress):
    course_progress = current_lesson_progress.course_progress
    next_block_id = course_progress.next_lesson
    models.LessonPersonalProgress.objects.get(course_progress=course_progress, lesson=next_block_id).delete()


def is_not_last_progress_block(instance, last_block_id):
    if instance.lesson.id != last_block_id:
        return True
    return False


def create_or_delete_next_lesson_progress(instance, previous, last_block_id):
    if is_not_last_progress_block(instance, last_block_id):
        if not previous.completed:
            create_next_progress_block(instance)
        else:
            delete_next_progress_block(instance)


def test_available(progress):
    if progress.lesson_part_completed:
        if not progress.completed:
            return True
    return False
