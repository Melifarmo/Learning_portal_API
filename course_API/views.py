import json

from functools import wraps
from django.contrib.auth import authenticate
from .serializers import CourseSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import CreateAPIView
from rest_framework.viewsets import ModelViewSet, ViewSet
from rest_framework.authtoken.models import Token
from rest_framework.status import HTTP_200_OK
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpRequest
from .serializers import UserSerializer, AnswerSerializer
from . import models

from django.dispatch import receiver
from django.db.models.signals import post_save, pre_save

from course_API import models


# Logic
@receiver(pre_save, sender=models.LessonPersonalProgress)
def lesson_progress_auto_creater(sender, instance, **kwargs):
    if instance.id is None:
        pass
    else:
        progress = instance
        previous_progress = models.LessonPersonalProgress.objects.get(id=progress.id)
        is_last_block = progress.lesson.id == progress.course_last_lesson.id
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
                    # delete_next_progress_block(progress)
                else:
                    course.completed = False
                reset_lesson_progress(progress, sender)


@receiver(post_save, sender=models.CoursePersonalProgress)
def create_first_lesson_stage(sender, instance, created, **kwargs):
    if created:
        first_block = instance.first_lesson
        models.LessonPersonalProgress.objects.create(course_progress=instance, lesson=first_block)


@receiver(post_save, sender=models.Answer)
def add_user_answer_in_lesson_progress(sender, instance, created, **kwargs):
    user = instance.user
    lesson = instance.question.lesson
    progress = get_lesson_progress(lesson, user)
    progress.answers.add(instance)
    progress.save()


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


@api_view(['GET'])
def get_test(request):
    lesson_id = request.GET.get('id')
    lesson = get_object_or_none(models.Lesson, pk=lesson_id)
    user = get_user_instance(request)
    data = []

    if lesson:
        progress = get_lesson_progress(lesson, user)
        if progress and is_test_available(progress):
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
def complete_lesson(request):
    user = get_user_instance(request)
    lesson_id = request.GET.get('id')
    lesson = get_object_or_none(models.Lesson, pk=lesson_id)
    block_progress = get_lesson_progress(lesson, user)

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


@api_view(['POST'])
def save_test_stage(request):
    success, message = save_answers_from_json(request)
    if success:
        return Response({"message": message})
    return Response({"error": message})


@api_view(['POST'])
def complete_test(request):
    success, _ = save_answers_from_json(request)
    user = get_user_instance(request)
    show(_)
    raw_data = request.POST.get('answers')
    data = json.loads(raw_data)

    lesson = models.Lesson.objects.get(pk=data['lesson'])
    progress = get_lesson_progress(lesson, user)
    answers = progress.answers

    if lesson.test_len == len(answers):

        for answer in answers:
            if not check_answer(answer):
                return Response({"test_result": "К сожалению, вы не прошли тест"})
        complete_lesson_block(progress)
        return Response({"test_result": "Поздравляю! Тест успешно пройдет, "
                                        "вы можете перейти к следующему этапу, "
                                        "если он доступен"})
    else:
        error = 'Завершите тест до конца, у вас недостаточно ответов'

    return Response({'id', 'kek'})




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


def save_answers_from_json(request):
    user = get_user_instance(request)
    raw_data = request.POST.get('answers')
    progress = models.LessonPersonalProgress.objects.get(course_progress__user=user.id, lesson=1)
    error = None

    if raw_data:
        try:
            data = json.loads(raw_data)
        except ValueError as except_text:
            error = f'Произошла ошибка при декодирование JSON - {except_text}'
        else:
            answers = data['answers']
            lesson_id = data['lesson']
            lesson = get_object_or_none(models.Lesson, pk=lesson_id)

            if lesson:
                progress = lesson.lesson_progress.get(course_progress__user=user.id)
                if is_test_available(progress):
                    for answer in answers:
                        save_answer(answer, user)
                    return True, 'Промежуточный результат теста сохранен'

                else:
                    error = 'Сдача данного теста недоступна'
            else:
                error = 'id лекции указан неверно'
    else:
        error = "В body отсутствует 'answers'"
    return False, error


def save_answer(answer_data, user):
    """
    Answer JSON structure
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
    """
    question = get_object_or_none(models.Question, pk=answer_data['question'])
    answers = answer_data['answer']
    show('xczczxczxczxc')
    if question:
        question_type = question.question_type
        answer_model = get_answer_model(question, user)

        if question_type == 'text':
            answer_model.text = answers
        elif question_type == 'boolean':
            answer_model.boolean = answers
        elif question_type == 'single' or question_type == 'multi':
            update_option_answer(answer_model, answers)
        else:
            update_mapped_answer(answer_model, answers)
        update_question_answers(answer_model)


def update_question_answers(answer_model):
    user = answer_model.user
    lesson = answer_model.question.lesson
    progress = get_lesson_progress(lesson, user)
    progress.answers.add(answer_model)
    progress.save()


def update_mapped_answer(answer_model, answers):
    mapped_answers = get_mapped_answers_list(answer_model, answers)
    answer_model.mapped_answers.clear()
    for answer in mapped_answers:
        answer_model.mapped_answers.add(answer)
    answer_model.save()


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
    option_models = []

    if question_type == 'single':
        answers = [answers]
    for option_id in answers:
        option_models.append(get_option_model(option_id))
    update_answer(answer_model, option_models, question_type)


def get_option_model(option_id):
    return models.PresetChoosableOption.objects.get(pk=option_id)


def get_answer_model(question, user):
    progress = get_lesson_progress(question.lesson, user)
    answer_model, _ = models.Answer.objects.get_or_create(question=question, user=user, lesson_progress=progress)
    return answer_model


def update_answer(answer_model, options, question_type):
    if question_type == 'single':
        answer_model.single_answer = options[0]
    elif question_type == 'multi':
        answer_model.multi_answers.clear()
        for option in options:
            answer_model.multi_answers.add(option)
    answer_model.save()
    answer_model.lesson_progress.answers.add(answer_model)



# Support function
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


def is_m2m_type(question_type):
    if question_type == 'multi' or question_type == 'single' or question_type == 'mapped':
        return True
    return False


def parsing_mapped_answers(answers, groups, options):
    unique_group = {}
    for option in answers:
        option_id = option['id']
        title = option['title']
        group_id = option['group_id']

        group_title = models.PresetMappedOptionGroup.objects.get(pk=option_id).title
        unique_group[group_title] = group_id
        options.append({'id': option_id, 'title': title})

    for value, pk in unique_group.items():
        groups.append({'id': pk, 'title': value})


def parsing_choosable_answers(answers, options):
    for option in answers:
        options.append({'id': option.id, 'value': option.title})


def get_test_data(question, answers):
    question_type = question.question_type
    options = []
    groups = []
    data = {'id': question.id, 'question': question.title}
    if is_m2m_type(question_type):
        if question_type == 'mapped':
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
    question_type = question.question_type
    answer = None
    if hasattr(question, 'preset_answer'):
        preset_answer = models.PresetAnswer.objects.get(question=question.id)
        if question_type == 'boolean':
            answer = preset_answer.boolean
        elif question_type == 'text':
            answer = preset_answer.text
        elif question_type == 'single' or question_type == 'multi':
            answer = preset_answer.options.all()
        elif question_type == 'mapped':
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


def get_lesson_progress(lesson, user):
    if is_lesson_progress_exist(lesson, user):
        return lesson.lesson_progress.get(course_progress__user=user)


def is_lesson_available_for_user(lesson, user):
    if not is_lesson_progress_exist(lesson, user):
        return False
    progress = lesson.lesson_progress.get(course_progress__user=user)
    course_progress = progress.course_progress
    return course_progress.current_lesson.id == progress.lesson.id and not \
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


def is_test_available(progress):
    if progress and progress.lesson_part_completed and not \
            progress.completed:
        return True
    return False


def complete_lesson_block(progress):
    progress.test_part_completed = True
    progress.completed = True
    progress.save()


# Receivers func
def create_next_progress_block(current_lesson_progress):
    course_progress = current_lesson_progress.course_progress
    next_block_id = course_progress.next_lesson
    show(course_progress, 'asd')

    _ = models.LessonPersonalProgress.objects.get_or_create(course_progress=course_progress, lesson=next_block_id)


def delete_next_progress_block(current_lesson_progress):
    course_progress = current_lesson_progress.course_progress

    if current_lesson_progress.next_lesson:
        current_lesson = course_progress.next_lesson.id
    else:
        current_lesson = course_progress.current_lesson.id

    models.LessonPersonalProgress.objects.get(course_progress=course_progress, lesson=current_lesson).delete()


def reset_lesson_progress(progress, sender):
    progress.test_part_completed = False
    progress.lesson_part_completed = False
