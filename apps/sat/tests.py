import json

from django.test import SimpleTestCase

from .answer_matching import check_english_answer, normalize_text_answer


class DummyQuestion:
    def __init__(self, **kwargs):
        self.pk = kwargs.pop("pk", 1)
        self.response_type = kwargs.pop("response_type", "multiple_choice")
        self.answer = kwargs.pop("answer", "")
        self.accepted_answers = kwargs.pop("accepted_answers", "")
        self.answer_patterns = kwargs.pop("answer_patterns", "")


class EnglishAnswerMatchingTests(SimpleTestCase):
    def test_multiple_choice_is_case_and_space_insensitive(self):
        q = DummyQuestion(answer="B")
        self.assertTrue(check_english_answer(q, " b "))
        self.assertFalse(check_english_answer(q, "A"))

    def test_open_text_accepts_normalized_variant(self):
        q = DummyQuestion(
            response_type="open_text",
            answer="She walks to school every day.",
            accepted_answers="She walks to school every day.\nShe goes to school every day.",
        )
        self.assertTrue(check_english_answer(q, "  SHE walks to school every day! "))
        self.assertTrue(check_english_answer(q, "She goes to school every day"))

    def test_open_text_full_match_pattern(self):
        q = DummyQuestion(
            response_type="open_text",
            answer_patterns=r"if it rains tomorrow,? .+ will [a-z]+(?: .+)?",
        )
        self.assertTrue(check_english_answer(q, "If it rains tomorrow, we will stay home."))
        self.assertFalse(check_english_answer(q, "It rains tomorrow."))

    def test_invalid_pattern_is_not_accepted(self):
        q = DummyQuestion(response_type="open_text", answer_patterns="[")
        self.assertFalse(check_english_answer(q, "anything"))

    def test_normalization_does_not_remove_internal_words(self):
        self.assertEqual(normalize_text_answer("  It’s   going—now. "), "it's going-now")

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Classroom, ClassroomMembership


class ClassroomApprovalVisibilityTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="teacher1", password="pass123", is_staff=True)
        teacher_group, _ = Group.objects.get_or_create(name="Teacher")
        self.teacher.groups.add(teacher_group)
        self.student = User.objects.create_user(username="student1", password="pass123")
        self.classroom = Classroom.objects.create(
            teacher=self.teacher,
            name="Visible Classroom",
            description="Approval should become visible to the student.",
        )
        self.membership = ClassroomMembership.objects.create(
            classroom=self.classroom,
            user=self.student,
            role="student",
            status="pending",
        )

    def test_approved_membership_appears_on_student_classroom_entry(self):
        teacher_client = Client()
        teacher_client.force_login(self.teacher)
        response = teacher_client.post(
            reverse("approve_join_request", args=[self.classroom.pk, self.membership.pk])
        )
        self.assertEqual(response.status_code, 302)

        self.membership.refresh_from_db()
        self.assertEqual(self.membership.status, "approved")

        student_client = Client()
        student_client.force_login(self.student)
        response = student_client.get(reverse("student_dashboard_root"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible Classroom")
        self.assertContains(response, "Open your classroom")
        self.assertContains(response, reverse("student_classroom_home_root", args=[self.classroom.pk]))
        self.assertNotContains(response, "waiting for teacher approval")

    def test_pending_request_page_contains_auto_refresh_watcher(self):
        student_client = Client()
        student_client.force_login(self.student)
        response = student_client.get(reverse("classroom_join_status"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-membership-status-watch')
        self.assertContains(response, "Pending")

from .models import (
    StudentProgress,
    StudentSectionAccess,
    VocabularyDeck,
    VocabularyDeckWord,
    VocabularyDeckWordProgress,
    VocabularyQuizAttempt,
    VocabularyUnit,
    VocabularyWord,
    VocabularyWordProgress,
)


class VocabularyLearningProgressTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username='vocab_teacher', password='pass123')
        teacher_group, _ = Group.objects.get_or_create(name='Teacher')
        self.teacher.groups.add(teacher_group)
        self.student = User.objects.create_user(username='vocab_student', password='pass123')
        self.classroom = Classroom.objects.create(
            teacher=self.teacher,
            name='Vocabulary Classroom',
        )
        self.membership = ClassroomMembership.objects.create(
            classroom=self.classroom,
            user=self.student,
            role='student',
            status='approved',
        )
        StudentSectionAccess.objects.create(
            membership=self.membership,
            section='vocabulary',
            has_access=True,
        )
        self.unit = VocabularyUnit.objects.create(title='Core Words', order=1)
        self.words = [
            VocabularyWord.objects.create(unit=self.unit, word='abate', meaning='become less intense'),
            VocabularyWord.objects.create(unit=self.unit, word='lucid', meaning='clear and easy to understand'),
            VocabularyWord.objects.create(unit=self.unit, word='novel', meaning='new or unusual'),
            VocabularyWord.objects.create(unit=self.unit, word='vivid', meaning='producing strong clear images'),
        ]
        self.client.force_login(self.student)

    def test_legacy_classroom_flashcards_write_to_account_scope(self):
        url = reverse('classroom_vocabulary_flashcard_mark', args=[self.classroom.pk])
        for _ in range(2):
            response = self.client.post(
                url,
                data=json.dumps({'word_id': self.words[0].pk, 'outcome': 'known'}),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['ok'])

        progress = VocabularyWordProgress.objects.get(
            user=self.student,
            classroom__isnull=True,
            word=self.words[0],
        )
        self.assertEqual(progress.status, VocabularyWordProgress.STATUS_MASTERED)
        self.assertFalse(VocabularyWordProgress.objects.filter(
            user=self.student,
            classroom=self.classroom,
            word=self.words[0],
        ).exists())

        teacher_client = Client()
        teacher_client.force_login(self.teacher)
        dashboard = teacher_client.get(reverse('classroom_progress_dashboard', args=[self.classroom.pk]))
        self.assertEqual(dashboard.status_code, 200)
        section_progress = StudentProgress.objects.get(
            classroom=self.classroom,
            student=self.student,
            section='vocabulary',
        )
        self.assertEqual(section_progress.completed_items, 1)
        self.assertEqual(section_progress.total_items, 4)
        self.assertEqual(float(section_progress.completion_percent), 25.0)

    def test_legacy_flashcard_retry_is_idempotent(self):
        url = reverse('classroom_vocabulary_flashcard_mark', args=[self.classroom.pk])
        payload = {'word_id': self.words[0].pk, 'outcome': 'known', 'expected_times_seen': 0}

        first = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.json()['duplicate'])
        self.assertEqual(first.json()['times_seen'], 1)

        retry = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(retry.status_code, 200)
        self.assertTrue(retry.json()['duplicate'])
        self.assertEqual(retry.json()['times_seen'], 1)

        progress = VocabularyWordProgress.objects.get(
            user=self.student,
            classroom__isnull=True,
            word=self.words[0],
        )
        self.assertEqual(progress.times_seen, 1)
        self.assertEqual(progress.correct_count, 1)

    def test_personal_deck_review_retry_is_idempotent(self):
        deck = VocabularyDeck.objects.create(owner=self.student, title='Mobile retry deck')
        word = VocabularyDeckWord.objects.create(deck=deck, word='lucid', meaning='clear', order=1)
        url = reverse('vocabulary_deck_mark', args=[deck.pk])
        payload = {'word_id': word.pk, 'outcome': 'known', 'expected_times_seen': 0}

        first = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.json()['duplicate'])
        self.assertEqual(first.json()['times_seen'], 1)

        retry = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(retry.status_code, 200)
        self.assertTrue(retry.json()['duplicate'])
        self.assertEqual(retry.json()['times_seen'], 1)

        progress = VocabularyDeckWordProgress.objects.get(user=self.student, word=word)
        self.assertEqual(progress.times_seen, 1)
        self.assertEqual(progress.correct_count, 1)

    def test_quiz_result_from_legacy_classroom_route_is_saved_to_account_scope(self):
        session = self.client.session
        session['vocab_quiz_questions'] = [
            {
                'word_id': self.words[0].pk,
                'unit_id': self.unit.pk,
                'unit': self.unit.title,
                'question': "What is the meaning of 'abate'?",
                'choices': [word.meaning for word in self.words],
                'answer': self.words[0].meaning,
                'word': self.words[0].word,
                'mode': 'word_to_meaning',
            },
            {
                'word_id': self.words[1].pk,
                'unit_id': self.unit.pk,
                'unit': self.unit.title,
                'question': "What is the meaning of 'lucid'?",
                'choices': [word.meaning for word in self.words],
                'answer': self.words[1].meaning,
                'word': self.words[1].word,
                'mode': 'word_to_meaning',
            },
        ]
        session['vocab_quiz_units'] = [self.unit.title]
        session['vocab_quiz_mode'] = 'word_to_meaning'
        session.save()

        response = self.client.post(
            reverse('classroom_vocabulary_practice_quiz_result', args=[self.classroom.pk]),
            {
                'question_0': self.words[0].meaning,
                'question_1': 'wrong answer',
            },
        )
        self.assertEqual(response.status_code, 200)
        attempt = VocabularyQuizAttempt.objects.get(user=self.student, classroom__isnull=True)
        self.assertEqual(attempt.score, 1)
        self.assertEqual(attempt.total_questions, 2)
        self.assertEqual(float(attempt.percentage), 50.0)
        self.assertFalse(VocabularyQuizAttempt.objects.filter(user=self.student, classroom=self.classroom).exists())

        first_progress = VocabularyWordProgress.objects.get(user=self.student, classroom__isnull=True, word=self.words[0])
        second_progress = VocabularyWordProgress.objects.get(user=self.student, classroom__isnull=True, word=self.words[1])
        self.assertEqual(first_progress.correct_count, 1)
        self.assertEqual(second_progress.incorrect_count, 1)

    def test_progress_dashboard_mirrors_personal_deck_progress(self):
        deck = VocabularyDeck.objects.create(owner=self.student, title='Current vocabulary')
        word = VocabularyDeckWord.objects.create(deck=deck, word='pragmatic', meaning='practical', order=1)
        url = reverse('vocabulary_deck_mark', args=[deck.pk])
        for expected in (0, 1):
            response = self.client.post(
                url,
                data=json.dumps({'word_id': word.pk, 'outcome': 'known', 'expected_times_seen': expected}),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 200)

        teacher_client = Client()
        teacher_client.force_login(self.teacher)
        response = teacher_client.get(reverse('classroom_progress_dashboard', args=[self.classroom.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'vocab_student')
        section_progress = StudentProgress.objects.get(
            classroom=self.classroom,
            student=self.student,
            section='vocabulary',
        )
        self.assertEqual(section_progress.completed_items, 1)
        self.assertEqual(section_progress.total_items, 1)
        self.assertEqual(float(section_progress.completion_percent), 100.0)
        self.assertEqual(section_progress.activity_count, 2)

    def test_legacy_classroom_vocabulary_routes_redirect_student_to_canonical_workspace(self):
        routes = [
            (reverse('classroom_vocabulary', args=[self.classroom.pk]), reverse('vocabulary_root')),
            (reverse('classroom_vocabulary_section', args=[self.classroom.pk, 'word_lists']), reverse('vocabulary_section_root', args=['word_lists'])),
            (reverse('classroom_vocabulary_section', args=[self.classroom.pk, 'flashcards']), reverse('vocabulary_section_root', args=['flashcards'])),
            (reverse('classroom_vocabulary_section', args=[self.classroom.pk, 'practice-quiz']), reverse('vocabulary_section_root', args=['practice-quiz'])),
        ]
        for url, expected_location in routes:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertEqual(response['Location'], expected_location)


from .models import (
    English_Question,
    Math_Question,
    StudentPracticeTestAccess,
    Test,
    TestReview,
    TestStage,
)


class PracticeTestLibraryTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username='practice_teacher', password='pass123')
        self.student = User.objects.create_user(username='practice_student', password='pass123')
        self.classroom = Classroom.objects.create(teacher=self.teacher, name='Practice Classroom')
        self.membership = ClassroomMembership.objects.create(
            classroom=self.classroom,
            user=self.student,
            role='student',
            status='approved',
        )
        StudentSectionAccess.objects.create(
            membership=self.membership,
            section='practice_tests',
            has_access=True,
        )
        self.test_obj = Test.objects.create(name='DAY 60')
        English_Question.objects.create(
            test=self.test_obj,
            module='module_1',
            number=1,
            question='English question',
            answer='A',
        )
        Math_Question.objects.create(
            test=self.test_obj,
            module='module_1',
            number=1,
            question='Math question',
            answer='A',
        )
        StudentPracticeTestAccess.objects.create(
            membership=self.membership,
            test=self.test_obj,
            has_access=True,
        )
        self.client.force_login(self.student)
        self.url = reverse('practice_tests_root')

    def test_fresh_test_card_has_batched_catalog_metadata(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DAY 60')
        self.assertContains(response, '2 questions')
        self.assertContains(response, '2 modules')
        self.assertContains(response, 'Start test')
        self.assertContains(response, 'data-practice-page')

    def test_unfinished_stage_is_presented_as_continue(self):
        TestStage.objects.create(
            user=self.student,
            test=self.test_obj,
            classroom=None,
            stage=1,
            test_type='regular',
        )
        response = self.client.get(self.url)
        self.assertContains(response, 'Continue test')
        self.assertContains(response, 'In progress')
        self.assertContains(response, 'Module 1 of 2')

    def test_completed_review_moves_test_to_past_panel(self):
        TestReview.objects.create(
            user=self.student,
            test=self.test_obj,
            classroom=None,
            score=1280,
            key='practice-library-review-key',
        )
        response = self.client.get(self.url)
        self.assertContains(response, '1280')
        self.assertContains(response, 'View results')
        self.assertContains(response, 'data-practice-panel="history"')

import json
import uuid
from datetime import timedelta
from django.utils import timezone

from .models import TestModule, TestModuleDraft


class SATTestFlowV13Tests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username='flow_teacher', password='pass123')
        self.student = User.objects.create_user(username='flow_student', password='pass123')
        self.classroom = Classroom.objects.create(teacher=self.teacher, name='Flow Classroom')
        self.membership = ClassroomMembership.objects.create(
            classroom=self.classroom,
            user=self.student,
            role='student',
            status='approved',
        )
        StudentSectionAccess.objects.create(
            membership=self.membership,
            section='practice_tests',
            has_access=True,
        )
        self.test_obj = Test.objects.create(name='FLOW TEST')
        self.english_q = English_Question.objects.create(
            test=self.test_obj,
            module='module_1',
            number=1,
            question='Choose A.',
            a='A answer', b='B answer', c='C answer', d='D answer',
            answer='A',
        )
        self.math_q = Math_Question.objects.create(
            test=self.test_obj,
            module='module_1',
            number=1,
            question='Choose B.',
            a='A answer', b='B answer', c='C answer', d='D answer',
            answer='B',
        )
        self.other_english_q = English_Question.objects.create(
            test=self.test_obj,
            module='module_2',
            number=2,
            question='This belongs to another English module.',
            a='A answer', b='B answer', c='C answer', d='D answer',
            answer='A',
        )
        StudentPracticeTestAccess.objects.create(
            membership=self.membership,
            test=self.test_obj,
            has_access=True,
        )
        self.client.force_login(self.student)

    def module_url(self):
        return reverse('practice_test_module_root', args=[self.test_obj.name])

    def open_first_module(self):
        response = self.client.get(self.module_url())
        self.assertEqual(response.status_code, 200)
        stage = TestStage.objects.get(
            user=self.student,
            test=self.test_obj,
            classroom=None,
            test_type='regular',
        )
        draft = TestModuleDraft.objects.get(
            user=self.student,
            test=self.test_obj,
            classroom=None,
            attempt_id=stage.attempt_id,
            section='english',
            module='m1',
        )
        return stage, draft, response

    def test_start_page_shows_current_test_overview(self):
        response = self.client.get(reverse('practice_test_start_root', args=[self.test_obj.name]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<div><span>Questions</span><strong>3</strong></div>', html=True)
        self.assertContains(response, 'Approx. time')
        self.assertContains(response, 'Test-day reminders')
        self.assertContains(response, 'Start test')

    def test_draft_is_server_saved_and_restored(self):
        stage, draft, _ = self.open_first_module()
        response = self.client.post(
            reverse('save_test_module_draft'),
            data=json.dumps({
                'test': self.test_obj.name,
                'attempt_id': str(stage.attempt_id),
                'section': 'english',
                'module': 'm1',
                'answers': [{'questionID': self.english_q.pk, 'answer': 'A', 'time_spent': 8}],
                'current_question_index': 0,
                'marked_for_review': [True],
                'eliminated_choices': [['C']],
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        draft.refresh_from_db()
        self.assertEqual(draft.answers[0]['answer'], 'A')
        self.assertEqual(draft.marked_for_review, [True])

        refreshed = self.client.get(self.module_url())
        self.assertContains(refreshed, '"answers": ["A"]', html=False)

    def test_draft_rejects_question_from_another_module(self):
        stage, _, _ = self.open_first_module()
        response = self.client.post(
            reverse('save_test_module_draft'),
            data=json.dumps({
                'test': self.test_obj.name,
                'attempt_id': str(stage.attempt_id),
                'section': 'english',
                'module': 'm1',
                'answers': [{'questionID': self.other_english_q.pk, 'answer': 'A'}],
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_direct_submit_without_server_timer_draft_is_rejected(self):
        stage = TestStage.objects.create(
            user=self.student,
            test=self.test_obj,
            classroom=None,
            stage=1,
            test_type='regular',
        )
        response = self.client.post(
            reverse('check_the_answers'),
            data=json.dumps({
                'test': self.test_obj.name,
                'attempt_id': str(stage.attempt_id),
                'section': 'english',
                'module': 'm1',
                'answers': [{'questionID': self.english_q.pk, 'answer': 'A', 'time_spent': 0}],
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn('Open the active module', response.json()['error'])
        self.assertFalse(TestModule.objects.filter(attempt_id=stage.attempt_id).exists())

    def test_final_submit_is_idempotent(self):
        stage, _, _ = self.open_first_module()
        payload = {
            'test': self.test_obj.name,
            'attempt_id': str(stage.attempt_id),
            'section': 'english',
            'module': 'm1',
            'answers': [{'questionID': self.english_q.pk, 'answer': 'A', 'time_spent': 3}],
        }
        first = self.client.post(reverse('check_the_answers'), json.dumps(payload), content_type='application/json')
        self.assertEqual(first.status_code, 200)
        stage.refresh_from_db()
        self.assertEqual(stage.stage, 2)

        second = self.client.post(reverse('check_the_answers'), json.dumps(payload), content_type='application/json')
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json().get('already_submitted'))
        stage.refresh_from_db()
        self.assertEqual(stage.stage, 2)
        self.assertEqual(TestModule.objects.filter(user=self.student, test=self.test_obj, attempt_id=stage.attempt_id, section='english', module='m1').count(), 1)

    def test_expired_module_uses_last_server_draft_not_late_answer(self):
        stage, draft, _ = self.open_first_module()
        draft.answers = [{'questionID': self.english_q.pk, 'answer': 'A', 'time_spent': 4}]
        draft.deadline_at = timezone.now() - timedelta(seconds=1)
        draft.save(update_fields=['answers', 'deadline_at', 'updated_at'])

        response = self.client.post(
            reverse('check_the_answers'),
            data=json.dumps({
                'test': self.test_obj.name,
                'attempt_id': str(stage.attempt_id),
                'section': 'english',
                'module': 'm1',
                'answers': [{'questionID': self.english_q.pk, 'answer': 'B', 'time_spent': 100}],
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['submitted_after_deadline'])
        module = TestModule.objects.get(user=self.student, test=self.test_obj, attempt_id=stage.attempt_id, section='english', module='m1')
        stored = json.loads(module.answers)['answers'][0]
        self.assertEqual(stored['answer'], 'A')


    def test_existing_module_advances_by_test_name_not_numeric_pk(self):
        stage = TestStage.objects.create(
            user=self.student,
            test=self.test_obj,
            classroom=None,
            stage=1,
            test_type='regular',
        )
        TestModule.objects.create(
            test=self.test_obj,
            user=self.student,
            classroom=None,
            section='english',
            module='m1',
            attempt_id=stage.attempt_id,
            answers=json.dumps({'answers': [{'questionID': self.english_q.pk, 'answer': 'A', 'time_spent': 1}]}),
        )
        response = self.client.get(
            reverse('practice_test_module_root', args=[self.test_obj.name]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        stage.refresh_from_db()
        self.assertEqual(stage.stage, 2)
        self.assertContains(response, 'Reading and Writing')
        self.assertContains(response, 'Module 2')

    def test_single_required_section_module_is_complete(self):
        from .views import _section_submission_status
        status = _section_submission_status([('math', 'm1')], [])
        self.assertTrue(status['math'])
        self.assertTrue(status['total'])
        self.assertFalse(status['english'])

    def test_complete_ebrw_math_flow_creates_results_and_review_pages(self):
        stage, _, _ = self.open_first_module()
        submissions = [
            ('english', 'm1', self.english_q, 'A'),
            ('english', 'm2', self.other_english_q, 'A'),
            ('math', 'm1', self.math_q, 'B'),
        ]
        for index, (section, module, question, answer) in enumerate(submissions):
            if index:
                # The real runner inserts the SAT subject break between RW and Math.
                # skip_break=1 simulates the student's explicit Continue action and
                # follow=True opens the exact attempt-bound module, creating its
                # server-authoritative timer draft before submission.
                module_page = self.client.get(f"{self.module_url()}?skip_break=1", follow=True)
                self.assertEqual(module_page.status_code, 200)
            response = self.client.post(
                reverse('check_the_answers'),
                data=json.dumps({
                    'test': self.test_obj.name,
                    'attempt_id': str(stage.attempt_id),
                    'section': section,
                    'module': module,
                    'answers': [{'questionID': question.pk, 'answer': answer, 'time_spent': 2}],
                }),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 200, response.content)
            stage.refresh_from_db()

        results_response = self.client.get(reverse('practice_test_results_root', args=[self.test_obj.name]))
        self.assertEqual(results_response.status_code, 200)
        self.assertContains(results_response, 'FLOW TEST')
        review = TestReview.objects.get(
            user=self.student,
            test=self.test_obj,
            classroom=None,
            attempt_id=stage.attempt_id,
        )
        self.assertIsNotNone(review.score)

        english_review = self.client.get(
            reverse('practice_test_review_question_root', args=[review.key, 'english', 'm1', self.english_q.pk])
        )
        math_review = self.client.get(
            reverse('practice_test_review_question_root', args=[review.key, 'math', 'm1', self.math_q.pk])
        )
        self.assertEqual(english_review.status_code, 200)
        self.assertEqual(math_review.status_code, 200)
        self.assertContains(english_review, 'Choose A.')
        self.assertContains(math_review, 'Choose B.')

    def test_review_rejects_question_not_in_selected_module(self):
        attempt_id = uuid.uuid4()
        TestModule.objects.create(
            test=self.test_obj,
            user=self.student,
            classroom=self.classroom,
            section='english',
            module='m1',
            attempt_id=attempt_id,
            answers=json.dumps({'answers': [{'questionID': self.english_q.pk, 'answer': 'A', 'time_spent': 1}]}),
        )
        review = TestReview.objects.create(
            test=self.test_obj,
            user=self.student,
            classroom=self.classroom,
            attempt_id=attempt_id,
            score=800,
            key='flow-review-key',
        )
        response = self.client.get(reverse('practice_test_review_question_root', args=[review.key, 'english', 'm1', self.other_english_q.pk]))
        self.assertEqual(response.status_code, 404)

from .models import (
    GlobalEvent,
    GlobalEventAnswer,
    GlobalEventAttempt,
    GlobalEventModuleDraft,
    GuestParticipant,
)
from .views import get_test_sequence


@override_settings(MAKONBOOK_GUEST_MODE_ENABLED=True)
class GuestModeV18Tests(TestCase):
    def setUp(self):
        self.test_obj = Test.objects.create(name='GUEST FLOW TEST')
        self.english_q = English_Question.objects.create(
            test=self.test_obj,
            module='module_1',
            number=1,
            passage='A short passage.',
            question='Choose A.',
            a='Correct', b='Wrong B', c='Wrong C', d='Wrong D',
            answer='A',
            explained='A is the accepted answer.',
        )
        self.math_q = Math_Question.objects.create(
            test=self.test_obj,
            module='module_1',
            number=1,
            question='Choose B.',
            a='Wrong A', b='Correct', c='Wrong C', d='Wrong D',
            answer='B',
        )
        now = timezone.now()
        self.event = GlobalEvent.objects.create(
            title='Guest Live Event',
            slug='guest-live-event',
            test=self.test_obj,
            start_at=now - timedelta(hours=1),
            end_at=now + timedelta(hours=4),
            english_duration_minutes=30,
            math_duration_minutes=35,
            status='live',
            is_public=True,
            always_live=False,
            show_score_immediately=True,
            show_leaderboard=True,
            allow_resume=True,
        )
        self.guest = GuestParticipant.objects.create(
            full_name='John Smith',
            display_name='',
            session_key='guest-test-session',
        )
        session = self.client.session
        session['guest_mode'] = True
        session['guest_id'] = str(self.guest.guest_id)
        session['guest_name'] = self.guest.full_name
        session.save()

    def create_attempt(self, **overrides):
        values = {
            'event': self.event,
            'guest': self.guest,
            'expires_at': timezone.now() + timedelta(hours=4),
            'total_questions': 2,
        }
        values.update(overrides)
        return GlobalEventAttempt.objects.create(**values)

    def test_guest_autosave_persists_full_ui_state(self):
        attempt = self.create_attempt()
        response = self.client.get(reverse('global_event_attempt_root', args=[attempt.guest_token]))
        self.assertEqual(response.status_code, 200)
        draft = GlobalEventModuleDraft.objects.get(attempt=attempt, section='english', module='m1')
        response = self.client.post(
            reverse('save_global_event_answer_root', args=[attempt.guest_token]),
            data=json.dumps({
                'section': 'english',
                'module': 'm1',
                'answers': [{'questionID': self.english_q.pk, 'answer': 'A', 'time_spent': 12}],
                'current_question_index': 0,
                'marked_for_review': [True],
                'eliminated_choices': [['C', 'D']],
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        draft.refresh_from_db()
        self.assertEqual(draft.answers[0]['answer'], 'A')
        self.assertEqual(draft.marked_for_review, [True])
        self.assertEqual(draft.eliminated_choices, [['C', 'D']])
        self.assertFalse(GlobalEventAnswer.objects.filter(attempt=attempt, question_id=self.english_q.pk).exists())

    def test_guest_math_uses_shared_test_core(self):
        attempt = self.create_attempt(completed_modules=['english:m1'])
        response = self.client.get(reverse('global_event_attempt_root', args=[attempt.guest_token]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'test/shared/attempt_math.html')
        self.assertContains(response, 'sat-test-core-v13.js')
        self.assertContains(response, 'sat-math-tools-v13.js')

    def test_direct_result_url_does_not_submit_active_attempt(self):
        attempt = self.create_attempt()
        response = self.client.get(reverse('global_event_result_root', args=[attempt.guest_token]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('global_event_attempt_root', args=[attempt.guest_token]), response.url)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'in_progress')

    def test_atomic_guest_submit_saves_answers_and_advances(self):
        attempt = self.create_attempt()
        self.client.get(reverse('global_event_attempt_root', args=[attempt.guest_token]))
        response = self.client.post(
            reverse('submit_global_event_root', args=[attempt.guest_token]),
            data=json.dumps({
                'section': 'english',
                'module': 'm1',
                'answers': [{'questionID': self.english_q.pk, 'answer': 'A', 'time_spent': 5}],
                'marked_for_review': [True],
                'eliminated_choices': [['D']],
                'current_question_index': 0,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        attempt.refresh_from_db()
        self.assertIn('english:m1', attempt.completed_modules)
        self.assertEqual(attempt.status, 'in_progress')
        self.assertEqual(GlobalEventAnswer.objects.get(attempt=attempt, question_id=self.english_q.pk).selected_answer, 'A')
        self.assertFalse(GlobalEventModuleDraft.objects.filter(attempt=attempt, section='english', module='m1').exists())

    def test_guest_submit_is_idempotent(self):
        attempt = self.create_attempt()
        self.client.get(reverse('global_event_attempt_root', args=[attempt.guest_token]))
        payload = {
            'section': 'english', 'module': 'm1',
            'answers': [{'questionID': self.english_q.pk, 'answer': 'A'}],
        }
        first = self.client.post(reverse('submit_global_event_root', args=[attempt.guest_token]), json.dumps(payload), content_type='application/json')
        self.assertEqual(first.status_code, 200)
        second = self.client.post(reverse('submit_global_event_root', args=[attempt.guest_token]), json.dumps(payload), content_type='application/json')
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json().get('already_submitted'))
        attempt.refresh_from_db()
        self.assertEqual(attempt.completed_modules.count('english:m1'), 1)

    def test_expired_guest_module_uses_server_draft_not_late_answer(self):
        attempt = self.create_attempt()
        self.client.get(reverse('global_event_attempt_root', args=[attempt.guest_token]))
        draft = GlobalEventModuleDraft.objects.get(attempt=attempt, section='english', module='m1')
        draft.answers = [{'questionID': self.english_q.pk, 'answer': 'A', 'time_spent': 4}]
        draft.deadline_at = timezone.now() - timedelta(seconds=1)
        draft.save(update_fields=['answers', 'deadline_at', 'updated_at'])
        response = self.client.post(
            reverse('submit_global_event_root', args=[attempt.guest_token]),
            json.dumps({
                'section': 'english', 'module': 'm1',
                'answers': [{'questionID': self.english_q.pk, 'answer': 'B', 'time_spent': 99}],
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        answer = GlobalEventAnswer.objects.get(attempt=attempt, question_id=self.english_q.pk)
        self.assertEqual(answer.selected_answer, 'A')
        self.assertTrue(response.json()['submitted_after_deadline'])

    def test_expired_guest_module_accepts_frozen_deadline_snapshot_within_grace(self):
        attempt = self.create_attempt()
        self.client.get(reverse('global_event_attempt_root', args=[attempt.guest_token]))
        draft = GlobalEventModuleDraft.objects.get(attempt=attempt, section='english', module='m1')
        draft.answers = [{'questionID': self.english_q.pk, 'answer': 'A', 'time_spent': 4}]
        draft.deadline_at = timezone.now() - timedelta(seconds=2)
        draft.save(update_fields=['answers', 'deadline_at', 'updated_at'])
        response = self.client.post(
            reverse('submit_global_event_root', args=[attempt.guest_token]),
            json.dumps({
                'section': 'english',
                'module': 'm1',
                'answers': [{'questionID': self.english_q.pk, 'answer': 'B', 'time_spent': 11}],
                'deadline_reached': True,
                'client_deadline_at': int(draft.deadline_at.timestamp() * 1000),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['submitted_after_deadline'])
        self.assertTrue(response.json()['recovered_deadline_snapshot'])
        answer = GlobalEventAnswer.objects.get(attempt=attempt, question_id=self.english_q.pk)
        self.assertEqual(answer.selected_answer, 'B')
        self.assertEqual(answer.time_spent, 11)

    def test_guest_submit_status_reports_pending_then_completed(self):
        attempt = self.create_attempt()
        self.client.get(reverse('global_event_attempt_root', args=[attempt.guest_token]))
        status_url = reverse('global_event_submit_status_root', args=[attempt.guest_token])
        pending = self.client.get(status_url, {'section': 'english', 'module': 'm1'})
        self.assertEqual(pending.status_code, 200)
        self.assertEqual(pending.json()['state'], 'pending')

        payload = {
            'section': 'english',
            'module': 'm1',
            'answers': [{'questionID': self.english_q.pk, 'answer': 'A'}],
        }
        submitted = self.client.post(
            reverse('submit_global_event_root', args=[attempt.guest_token]),
            json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(submitted.status_code, 200)
        completed = self.client.get(status_url, {'section': 'english', 'module': 'm1'})
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()['state'], 'completed')
        self.assertTrue(completed.json()['redirect_url'])

    def test_always_live_event_ignores_calendar_end_and_can_start(self):
        self.event.always_live = True
        self.event.end_at = timezone.now() - timedelta(days=5)
        self.event.save(update_fields=['always_live', 'end_at'])
        response = self.client.post(reverse('start_global_event_root', args=[self.event.slug]), {})
        self.assertEqual(response.status_code, 302)
        attempt = GlobalEventAttempt.objects.get(event=self.event, guest=self.guest)
        self.assertIn(str(attempt.guest_token), response.url)
        self.assertGreater(attempt.expires_at, timezone.now())
        self.assertIsNone(self.event.effective_end_at)

    def test_guest_review_is_only_available_after_submission(self):
        attempt = self.create_attempt()
        response = self.client.get(reverse('global_event_review_root', args=[attempt.guest_token]))
        self.assertEqual(response.status_code, 302)
        GlobalEventAnswer.objects.create(
            attempt=attempt, section='english', module='m1',
            question_id=self.english_q.pk, selected_answer='A',
        )
        attempt.completed_modules = ['english:m1', 'math:m1']
        attempt.save(update_fields=['completed_modules'])
        from .guest_views import finalize_attempt
        finalize_attempt(attempt)
        response = self.client.get(reverse('global_event_review_root', args=[attempt.guest_token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Question review')
        self.assertContains(response, 'Start review')
        detail = self.client.get(reverse(
            'global_event_review_question_root',
            args=[attempt.guest_token, 'english', 'm1', self.english_q.pk],
        ))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, 'A is the accepted answer.')
        self.assertContains(detail, 'Correct Answer')
        self.assertNotContains(detail, 'Time spent')
        self.assertNotContains(detail, 'seconds')

    def test_event_list_hides_ended_event_and_shows_upcoming(self):
        now = timezone.now()
        ended = GlobalEvent.objects.create(
            title='Ended Event', slug='ended-event', test=self.test_obj,
            start_at=now - timedelta(days=2), end_at=now - timedelta(days=1),
            status='live', is_public=True,
        )
        upcoming = GlobalEvent.objects.create(
            title='Upcoming Event', slug='upcoming-event', test=self.test_obj,
            start_at=now + timedelta(hours=2), end_at=now + timedelta(hours=4),
            status='scheduled', is_public=True,
        )
        response = self.client.get(reverse('global_event_list'))
        self.assertNotContains(response, ended.title)
        self.assertContains(response, upcoming.title)
        self.assertContains(response, 'Upcoming')

    def test_leaderboard_masks_full_name_when_no_display_name(self):
        attempt = self.create_attempt(status='submitted', submitted_at=timezone.now(), score=400)
        response = self.client.get(reverse('global_event_leaderboard_root', args=[self.event.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'John S.')
        self.assertNotContains(response, 'John Smith')

    def test_sequence_ignores_invalid_module_values(self):
        English_Question.objects.create(
            test=self.test_obj, module=None, number=99,
            question='Invalid imported module', answer='A',
        )
        self.assertEqual(get_test_sequence(self.test_obj), [('english', 'm1'), ('math', 'm1')])

    def test_hidden_scores_also_hide_leaderboard_ranking(self):
        self.event.show_score_immediately = False
        self.event.save(update_fields=['show_score_immediately'])
        self.create_attempt(status='submitted', submitted_at=timezone.now(), score=600)
        response = self.client.get(reverse('global_event_leaderboard_root', args=[self.event.slug]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('global_event_detail_root', args=[self.event.slug]), response.url)

    def test_admin_disabling_event_stops_active_guest_attempt(self):
        attempt = self.create_attempt()
        self.client.get(reverse('global_event_attempt_root', args=[attempt.guest_token]))
        self.event.status = 'closed'
        self.event.save(update_fields=['status'])
        response = self.client.get(reverse('global_event_attempt_root', args=[attempt.guest_token]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('global_event_result_root', args=[attempt.guest_token]), response.url)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'submitted')

    def test_scheduled_event_extension_updates_attempt_expiry(self):
        attempt = self.create_attempt(expires_at=self.event.end_at)
        extended_end = self.event.end_at + timedelta(hours=2)
        self.event.end_at = extended_end
        self.event.save(update_fields=['end_at'])
        response = self.client.get(reverse('global_event_attempt_root', args=[attempt.guest_token]))
        self.assertEqual(response.status_code, 200)
        attempt.refresh_from_db()
        self.assertEqual(attempt.expires_at, self.event.effective_end_at)

from django.contrib.auth.models import Group
from .models import MakeupTest, MakeupTestModuleDraft


class MakeupTestFlowV18Tests(TestCase):
    def setUp(self):
        self.group = Group.objects.create(name='Makeup Flow Group')
        self.user = User.objects.create_user(username='makeup_student', password='pass123')
        self.user.groups.add(self.group)
        self.makeup = MakeupTest.objects.create(name='MAKEUP FLOW V18')
        self.makeup.groups.add(self.group)
        self.english_q = English_Question.objects.create(
            test=Test.objects.create(name='MAKEUP SOURCE'),
            module='module_1', number=1, question='Choose A.',
            a='A', b='B', c='C', d='D', answer='A',
        )
        self.math_q = Math_Question.objects.create(
            test=self.english_q.test,
            module='module_1', number=1, question='Choose B.',
            a='A', b='B', c='C', d='D', answer='B',
        )
        self.other_english_q = English_Question.objects.create(
            test=self.english_q.test,
            module='module_1', number=2, question='Not in makeup.',
            a='A', b='B', c='C', d='D', answer='A',
        )
        self.makeup.english_questions.add(self.english_q, through_defaults={'order': 1})
        self.makeup.math_questions.add(self.math_q, through_defaults={'order': 1})
        self.stage = TestStage.objects.create(
            user=self.user, makeup_test=self.makeup, test_type='makeup', stage=1,
        )
        self.client.force_login(self.user)

    def submit(self, section, module, question, answer):
        self.client.get(reverse('makeup_test_module_root', args=[self.makeup.name]))
        return self.client.post(
            reverse('check_the_answers'),
            data=json.dumps({
                'test': self.makeup.name,
                'test_type': 'makeup',
                'attempt_id': str(self.stage.attempt_id),
                'section': section,
                'module': module,
                'answers': [{'questionID': question.pk, 'answer': answer, 'time_spent': 3}],
            }),
            content_type='application/json',
        )

    def test_makeup_submit_advances_and_returns_next_url(self):
        response = self.submit('english', 'm1', self.english_q, 'A')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['redirect_url'], reverse('makeup_test_module_root', args=[self.makeup.name]))
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.stage, 2)
        self.assertTrue(TestModule.objects.filter(
            makeup_test=self.makeup, user=self.user, section='english', module='m1',
            attempt_id=self.stage.attempt_id,
        ).exists())

    def test_makeup_submit_rejects_question_outside_module(self):
        response = self.submit('english', 'm1', self.other_english_q, 'A')
        self.assertEqual(response.status_code, 400)
        self.assertIn('do not belong', response.json()['error'])

    def test_makeup_final_module_redirects_to_classroom_entry(self):
        first = self.submit('english', 'm1', self.english_q, 'A')
        self.assertEqual(first.status_code, 200)
        second = self.submit('math', 'm1', self.math_q, 'B')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()['redirect_url'], reverse('student_dashboard_root'))
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.stage, 3)

    def test_makeup_retry_does_not_advance_twice(self):
        first = self.submit('english', 'm1', self.english_q, 'A')
        self.assertEqual(first.status_code, 200)
        retry = self.submit('english', 'm1', self.english_q, 'A')
        self.assertEqual(retry.status_code, 200)
        self.assertTrue(retry.json()['already_submitted'])
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.stage, 2)

    def test_makeup_draft_is_saved_and_restored(self):
        page = self.client.get(reverse('makeup_test_module_root', args=[self.makeup.name]))
        self.assertEqual(page.status_code, 200)
        draft = MakeupTestModuleDraft.objects.get(
            user=self.user, makeup_test=self.makeup, section='english', module='m1'
        )
        response = self.client.post(
            reverse('save_test_module_draft'),
            data=json.dumps({
                'test': self.makeup.name,
                'test_type': 'makeup',
                'attempt_id': str(self.stage.attempt_id),
                'section': 'english',
                'module': 'm1',
                'answers': [{'questionID': self.english_q.pk, 'answer': 'A', 'time_spent': 8}],
                'marked_for_review': [True],
                'eliminated_choices': [['C']],
                'current_question_index': 0,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        draft.refresh_from_db()
        self.assertEqual(draft.answers[0]['answer'], 'A')
        self.assertEqual(draft.marked_for_review, [True])
        restored = self.client.get(reverse('makeup_test_module_root', args=[self.makeup.name]))
        self.assertEqual(restored.status_code, 200)
        self.assertContains(restored, '"answers": ["A"]')

    def test_makeup_expired_module_uses_server_draft(self):
        self.client.get(reverse('makeup_test_module_root', args=[self.makeup.name]))
        draft = MakeupTestModuleDraft.objects.get(
            user=self.user, makeup_test=self.makeup, section='english', module='m1'
        )
        draft.answers = [{'questionID': self.english_q.pk, 'answer': 'A', 'time_spent': 4}]
        draft.deadline_at = timezone.now() - timedelta(seconds=1)
        draft.save(update_fields=['answers', 'deadline_at', 'updated_at'])
        response = self.client.post(
            reverse('check_the_answers'),
            data=json.dumps({
                'test': self.makeup.name,
                'test_type': 'makeup',
                'attempt_id': str(self.stage.attempt_id),
                'section': 'english',
                'module': 'm1',
                'answers': [{'questionID': self.english_q.pk, 'answer': 'B', 'time_spent': 99}],
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['submitted_after_deadline'])
        module = TestModule.objects.get(
            makeup_test=self.makeup, user=self.user, section='english', module='m1'
        )
        saved = json.loads(module.answers)['answers'][0]['answer']
        self.assertEqual(saved, 'A')
