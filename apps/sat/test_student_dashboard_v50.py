from django.contrib.auth.models import Group, User
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from .models import (
    Classroom, ClassroomMembership, ClassroomJoinCode, StudentSectionAccess, StudentPracticeTestAccess,
    ChatMessage, UserChatSticker, UserChatStickerPack, SecretCode, Test, QuestionDomain, QuestionType, English_Question,
    VocabularyDeck, VocabularyDeckWord, VocabularyDeckWordProgress, VocabularyUnit, VocabularyWord,
    VocabularyWordProgress, VocabularyQuizAttempt, ClassroomHomeworkAssignment, ClassroomLesson,
    ClassroomLessonResource, StudentProgress, SupportTeacherProfile,
)
from apps.apclasses.models import APMockExam, APExamEvent
from apps.gamification.models import GamificationProfile, QuestProgress, UserAchievement, XPEvent


class StudentDashboardV50Tests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="v50_teacher", password="pass123")
        teacher_group, _ = Group.objects.get_or_create(name="Teacher")
        self.teacher.groups.add(teacher_group)
        self.student = User.objects.create_user(
            username="v50_student",
            password="pass123",
            first_name="V50",
            last_name="Student",
        )
        self.classroom = Classroom.objects.create(
            teacher=self.teacher,
            name="V50 Classroom",
            description="Stable classroom used by the V50 student shell tests.",
        )
        self.membership = ClassroomMembership.objects.create(
            classroom=self.classroom,
            user=self.student,
            role="student",
            status="approved",
            approved_at=timezone.now(),
        )
        StudentSectionAccess.objects.create(membership=self.membership, section="practice_tests", has_access=True)
        StudentSectionAccess.objects.create(membership=self.membership, section="vocabulary", has_access=True)

    def test_student_home_uses_v50_workspace_and_locked_navigation(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_dashboard_root"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-student-workspace')
        self.assertContains(response, 'STUDENT DASHBOARD')
        for label in (
            "Home", "Learn", "Practice", "Homework", "Tests", "MakonBook World",
            "Classrooms", "Vocabulary", "AP Classes", "Progress", "Support sessions",
            "Messages", "Events", "Placement Tests", "Help &amp; Support",
        ):
            self.assertContains(response, label)
        self.assertContains(response, 'data-workspace-sidebar-customize-open')
        self.assertContains(response, 'data-workspace-command="search"')
        self.assertNotContains(response, 'data-issue-report-open')

    def test_v50_dashboard_prioritizes_continue_today_and_keeps_goal_editor(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_dashboard_root"))

        self.assertContains(response, "Target university")
        self.assertContains(response, "Continue")
        self.assertContains(response, "Due work")
        self.assertContains(response, "Weak topics")
        self.assertContains(response, "Roadmap")
        self.assertContains(response, "data-goal-modal-open")
        self.assertContains(response, "Set your dream university")
        self.assertNotContains(response, "Continue learning")
        self.assertNotContains(response, "Today")

    def test_home_no_longer_dumps_world_or_mako_preview_cards(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_dashboard_root"))

        self.assertContains(response, "MakonBook World")
        self.assertNotContains(response, "Mako preview")
        self.assertNotContains(response, "For V50.1 this is rule-based")
        self.assertNotContains(response, "Matchmaking is not live yet.")
        self.assertNotContains(response, "Your World rating")

    def test_sidebar_customization_is_client_side_and_home_is_pinned(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_dashboard_root"))

        self.assertContains(response, "Customize sidebar")
        self.assertContains(response, 'data-sidebar-sortable')
        markup = response.content.decode()
        self.assertRegex(
            markup,
            r'<a(?=[^>]*data-nav-key="home")(?=[^>]*data-sidebar-item)(?=[^>]*data-sidebar-locked="1")[^>]*>',
        )
        self.assertContains(response, 'data-sidebar-save')
        self.assertContains(response, 'data-sidebar-reset')
        self.assertRegex(
            markup,
            r'<a(?=[^>]*data-nav-key="question-bank")(?=[^>]*data-sidebar-item)(?=[^>]*data-sidebar-default-hidden="1")[^>]*>',
        )
        self.assertRegex(
            markup,
            r'<a(?=[^>]*data-nav-key="mentors")(?=[^>]*data-sidebar-item)(?=[^>]*data-sidebar-default-hidden="1")[^>]*>',
        )

    def test_student_classroom_progress_and_ranking_are_separate_workspace_pages(self):
        self.client.force_login(self.student)

        classroom_response = self.client.get(reverse("student_classroom_home", args=[self.classroom.id]))
        self.assertEqual(classroom_response.status_code, 200)
        self.assertContains(classroom_response, 'data-student-workspace')
        self.assertContains(classroom_response, 'data-nav-key="classrooms"')

        progress_response = self.client.get(reverse("student_progress"))
        self.assertEqual(progress_response.status_code, 200)
        self.assertContains(progress_response, 'data-student-workspace')
        self.assertContains(progress_response, 'Your learning progress, not teacher rating.')
        self.assertContains(progress_response, 'data-nav-key="progress"')

        rating_response = self.client.get(reverse("rating_home"))
        self.assertEqual(rating_response.status_code, 200)
        self.assertContains(rating_response, 'data-student-workspace')
        self.assertContains(rating_response, 'Teacher rating is one signal.')
        self.assertNotContains(rating_response, 'href="%s" data-nav-key="progress" class="mb50-nav-item is-active' % reverse("student_progress"))

    def test_v523_profile_and_settings_are_separate_workspace_pages(self):
        self.client.force_login(self.student)
        profile = self.client.get(reverse("edit_profile"))
        settings = self.client.get(reverse("settings_page"))
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(settings.status_code, 200)
        self.assertContains(profile, 'data-student-workspace')
        self.assertContains(profile, 'Basic information')
        self.assertNotContains(profile, 'App maintenance')
        self.assertContains(settings, 'Appearance')
        self.assertContains(settings, 'App maintenance')
        self.assertContains(settings, 'Help &amp; Support')
        self.assertContains(settings, 'data-v524-support-toggle="bug"')
        self.assertContains(settings, 'data-v524-support-form="bug"')
        self.assertContains(settings, 'data-v524-support-toggle="suggestion"')
        self.assertContains(settings, 'data-v524-support-form="suggestion"')

    def test_v523_tests_are_classroom_gated_and_require_explicit_assignment(self):
        test = Test.objects.create(name="V523 Assigned Test")
        self.client.force_login(self.student)

        unassigned = self.client.get(reverse("practice_tests"))
        self.assertEqual(unassigned.status_code, 200)
        self.assertContains(unassigned, 'assigned')
        self.assertNotContains(unassigned, 'V523 Assigned Test')

        StudentPracticeTestAccess.objects.create(membership=self.membership, test=test, has_access=True)
        assigned = self.client.get(reverse("practice_tests"))
        self.assertEqual(assigned.status_code, 200)
        self.assertContains(assigned, 'V523 Assigned Test')

        outsider = User.objects.create_user(username="v523_outsider", password="pass123")
        self.client.force_login(outsider)
        locked = self.client.get(reverse("practice_tests"))
        self.assertEqual(locked.status_code, 200)
        self.assertContains(locked, 'locked')
        self.assertNotContains(locked, 'V523 Assigned Test')

    def test_v524_sat_homework_grants_the_full_test_gate(self):
        assigned_test = Test.objects.create(name="V524 Homework SAT")
        section = StudentSectionAccess.objects.get(
            membership=self.membership, section="practice_tests"
        )
        section.has_access = False
        section.save(update_fields=["has_access"])

        self.client.force_login(self.teacher)
        created = self.client.post(
            reverse("teacher_classroom_homework", args=[self.classroom.id]),
            {
                "assignment_type": ClassroomHomeworkAssignment.TYPE_TEST,
                "title": "Assigned mock for homework",
                "test": assigned_test.pk,
                "assign_all": "1",
            },
        )
        self.assertEqual(created.status_code, 302)
        section.refresh_from_db()
        self.assertTrue(section.has_access)
        self.assertTrue(
            StudentPracticeTestAccess.objects.filter(
                membership=self.membership, test=assigned_test, has_access=True
            ).exists()
        )

        self.client.force_login(self.student)
        tests_page = self.client.get(reverse("practice_tests_root"))
        self.assertEqual(tests_page.status_code, 200)
        self.assertContains(tests_page, assigned_test.name)

    def test_v523_practice_and_question_bank_use_assigned_sat_questions(self):
        test = Test.objects.create(name="V523 Topic Test")
        StudentPracticeTestAccess.objects.create(membership=self.membership, test=test, has_access=True)
        domain = QuestionDomain.objects.create(name="Craft and Structure")
        qtype = QuestionType.objects.create(name="Words in Context", domain=domain)
        English_Question.objects.create(
            test=test, module="module_1", domain=domain, type=qtype, number=1,
            passage="A short assigned passage.", question="Which choice is best?",
            a="A", b="B", c="C", d="D", answer="A",
        )
        self.client.force_login(self.student)

        practice = self.client.get(reverse("student_practice"))
        self.assertEqual(practice.status_code, 200)
        self.assertContains(practice, "Words in Context")
        self.assertContains(practice, "Craft and Structure")
        self.assertNotContains(practice, "Open Vocabulary Arena")

        bank = self.client.get(reverse("student_question_bank"))
        self.assertEqual(bank.status_code, 200)
        self.assertContains(bank, "Which choice is best?")
        self.assertContains(bank, "Words in Context")
        self.assertNotContains(bank, '>A</')

        search = self.client.get(reverse("workspace_search"), {"q": "short assigned"})
        self.assertEqual(search.status_code, 200)
        question_groups = [group for group in search.json()["groups"] if group["label"] == "Questions"]
        self.assertTrue(question_groups)
        self.assertEqual(question_groups[0]["items"][0]["type"], "QUESTION")

    def test_v523_enter_code_accepts_active_classroom_join_code(self):
        second_classroom = Classroom.objects.create(teacher=self.teacher, name="Join Me")
        join_code = ClassroomJoinCode.objects.create(classroom=second_classroom, code="123456", is_active=True, expires_at=timezone.now() + timedelta(hours=2))
        self.client.force_login(self.student)
        response = self.client.post(reverse("enter_secret_code"), {"code": join_code.code}, follow=True)
        self.assertEqual(response.status_code, 200)
        membership = ClassroomMembership.objects.get(classroom=second_classroom, user=self.student)
        self.assertEqual(membership.status, "pending")
        self.assertContains(response, "Join Me")

    def test_v523_unassigned_test_code_does_not_grant_legacy_group_access(self):
        gated_test = Test.objects.create(name="V523 Code Gated")
        legacy_group = Group.objects.create(name="V523 Legacy Code Group")
        SecretCode.objects.create(code="A1B2C3", group=legacy_group, test=gated_test)
        self.client.force_login(self.student)

        response = self.client.post(reverse("enter_secret_code"), {"code": "A1B2C3"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertFalse(self.student.groups.filter(pk=legacy_group.pk).exists())
        self.assertContains(response, "not assigned through one of your classrooms")

    def test_v523_messages_can_send_reusable_custom_sticker(self):
        sticker = UserChatSticker.objects.create(
            user=self.student,
            image="classroom_chat_stickers/v523-test.webp",
            title="V523 sticker",
        )
        self.client.force_login(self.student)
        page = self.client.get(reverse("student_messages"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'data-chat-sticker-upload')
        self.assertContains(page, 'data-chat-custom-sticker="%s"' % sticker.id)

        sent = self.client.post(
            reverse("send_classroom_message", args=[self.classroom.id]),
            {"message": "", "sticker_id": str(sticker.id)},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(sent.status_code, 200)
        self.assertTrue(sent.json()["message"]["sticker_url"])
        self.assertTrue(ChatMessage.objects.filter(classroom=self.classroom, sender=self.student, sticker=sticker).exists())

    def test_v523_more_search_mentors_and_messages_are_real_workspace_routes(self):
        self.client.force_login(self.student)
        home = self.client.get(reverse("student_dashboard_root"))
        for label in ("Question Bank", "Ranking", "Mentors", "Events", "Placement Tests", "Admissions"):
            self.assertContains(home, label)

        search = self.client.get(reverse("workspace_search"), {"q": "me"})
        self.assertEqual(search.status_code, 200)
        payload = search.json()
        flattened = [item["title"] for group in payload["groups"] for item in group["items"]]
        self.assertIn("Messages", flattened)

        mentor_search = self.client.get(reverse("workspace_search"), {"q": "v50"})
        mentor_titles = [item["title"] for group in mentor_search.json()["groups"] for item in group["items"]]
        self.assertIn(self.teacher.get_full_name() or self.teacher.username, mentor_titles)

        messages_page = self.client.get(reverse("student_messages"))
        self.assertEqual(messages_page.status_code, 200)
        self.assertContains(messages_page, "Classroom chats")
        self.assertContains(messages_page, self.classroom.name)

    def test_dark_sidebar_uses_white_brand_mark(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_dashboard_root"))

        self.assertContains(response, 'assets/img/icons/white-icon-nobg.png')

    def test_tests_and_vocabulary_use_workspace_for_students_only(self):
        self.client.force_login(self.student)

        tests_response = self.client.get(reverse("practice_tests"), follow=True)
        self.assertEqual(tests_response.status_code, 200)
        self.assertContains(tests_response, 'data-student-workspace')
        self.assertContains(tests_response, 'data-nav-key="tests"')
        self.assertContains(tests_response, 'id="practiceTestsLibrary"')

        vocabulary_response = self.client.get(reverse("vocabulary"), follow=True)
        self.assertEqual(vocabulary_response.status_code, 200)
        self.assertContains(vocabulary_response, 'data-student-workspace')
        self.assertContains(vocabulary_response, 'data-nav-key="vocabulary"')
        self.assertEqual(vocabulary_response.request["PATH_INFO"], reverse("vocabulary"))
        self.assertContains(vocabulary_response, '>Ranking<')
        self.assertContains(vocabulary_response, 'data-workspace-more-open')

        flashcards_response = self.client.get(reverse("vocabulary_section", args=["flashcards"]), follow=True)
        self.assertEqual(flashcards_response.status_code, 200)
        self.assertContains(flashcards_response, 'data-student-workspace')

        self.client.force_login(self.teacher)
        teacher_tests = self.client.get(reverse("practice_tests"))
        self.assertEqual(teacher_tests.status_code, 200)
        self.assertNotContains(teacher_tests, 'data-student-workspace')

    def test_v524_teacher_lessons_are_visible_in_student_classroom(self):
        self.client.force_login(self.teacher)
        created = self.client.post(
            reverse("teacher_classroom_lessons", args=[self.classroom.id]),
            {
                "action": "lesson",
                "order": "1",
                "title": "Introduction to the SAT",
                "summary": "Read the slides before class.",
                "is_published": "1",
            },
        )
        self.assertEqual(created.status_code, 302)
        lesson = ClassroomLesson.objects.get(classroom=self.classroom)
        ClassroomLessonResource.objects.create(
            lesson=lesson,
            title="Lesson slides",
            resource_type=ClassroomLessonResource.RESOURCE_LINK,
            url="https://example.com/sat-intro",
            is_visible=True,
        )

        self.client.force_login(self.student)
        classroom_page = self.client.get(
            reverse("student_classroom_home_root", args=[self.classroom.id])
        )
        self.assertEqual(classroom_page.status_code, 200)
        self.assertContains(classroom_page, 'data-v524-classroom-course')
        self.assertContains(classroom_page, "Course timeline")
        self.assertContains(classroom_page, "Introduction to the SAT")
        self.assertContains(classroom_page, "Lesson slides")
        self.assertContains(classroom_page, "https://example.com/sat-intro")
        self.assertNotContains(classroom_page, "Build your score with a")
        self.assertNotContains(classroom_page, 'data-issue-report-open')

    def test_v524_vocabulary_does_not_require_a_classroom_membership(self):
        independent = User.objects.create_user(username="v524_independent_vocab", password="pass123")
        self.client.force_login(independent)
        response = self.client.get(reverse("vocabulary_root"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-student-workspace')
        self.assertContains(response, 'data-nav-key="vocabulary"')

    def test_v524_student_classroom_keeps_vocabulary_standalone(self):
        self.client.force_login(self.student)

        classroom_home = self.client.get(reverse("student_classroom_home_root", args=[self.classroom.id]))
        self.assertEqual(classroom_home.status_code, 200)
        self.assertNotContains(classroom_home, reverse("classroom_vocabulary", args=[self.classroom.id]))
        self.assertNotContains(classroom_home, "Strengthen vocabulary")

        legacy_vocab = self.client.get(reverse("classroom_vocabulary", args=[self.classroom.id]))
        self.assertEqual(legacy_vocab.status_code, 302)
        self.assertEqual(legacy_vocab["Location"], reverse("vocabulary_root"))

        legacy_flashcards = self.client.get(
            reverse("classroom_vocabulary_section", args=[self.classroom.id, "flashcards"])
        )
        self.assertEqual(legacy_flashcards.status_code, 302)
        self.assertEqual(legacy_flashcards["Location"], reverse("vocabulary_section_root", args=["flashcards"]))

    def test_v524_vocabulary_homework_quiz_writes_to_standalone_history(self):
        unit = VocabularyUnit.objects.create(title="Homework standalone unit", order=778)
        for index in range(4):
            VocabularyWord.objects.create(
                unit=unit, word=f"homeword{index}", meaning=f"meaning {index}"
            )
        assignment = ClassroomHomeworkAssignment.objects.create(
            classroom=self.classroom,
            created_by=self.teacher,
            title="Standalone vocabulary quiz",
            assignment_type=ClassroomHomeworkAssignment.TYPE_VOCAB_QUIZ,
            vocabulary_unit=unit,
            vocabulary_quiz_mode=VocabularyQuizAttempt.MODE_WORD_TO_MEANING,
            question_count=4,
            assign_all=True,
        )

        self.client.force_login(self.student)
        launch = self.client.get(reverse("student_homework_launch_root", args=[assignment.id]))
        self.assertEqual(launch.status_code, 200)
        session = self.client.session
        questions = session.get("vocab_quiz_questions")
        self.assertEqual(len(questions), 4)
        self.assertNotIn("vocab_quiz_classroom_id", session)

        payload = {f"question_{index}": question["answer"] for index, question in enumerate(questions)}
        result = self.client.post(
            reverse("student_homework_vocab_quiz_result_root", args=[assignment.id]), payload
        )
        self.assertEqual(result.status_code, 200)
        attempt = VocabularyQuizAttempt.objects.get(user=self.student)
        self.assertIsNone(attempt.classroom_id)
        self.assertEqual(attempt.score, 4)

    def test_v524_teacher_progress_reads_standalone_vocabulary_history(self):
        unit = VocabularyUnit.objects.create(title="Standalone teacher progress", order=777)
        word = VocabularyWord.objects.create(unit=unit, word="coherent", meaning="logical and consistent")
        VocabularyWordProgress.objects.create(
            user=self.student,
            classroom=None,
            word=word,
            status=VocabularyWordProgress.STATUS_MASTERED,
            times_seen=3,
            correct_count=3,
            consecutive_correct=3,
            last_reviewed_at=timezone.now(),
            mastered_at=timezone.now(),
        )

        self.client.force_login(self.teacher)
        response = self.client.get(
            reverse("classroom_student_vocab_progress", args=[self.classroom.id, self.student.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vocabulary is no longer tied to one classroom")
        self.assertContains(response, "Standalone teacher progress")

        record = StudentProgress.objects.get(
            classroom=self.classroom, student=self.student, section="vocabulary"
        )
        self.assertGreaterEqual(record.completed_items, 1)
        self.assertGreaterEqual(record.activity_count, 1)

    def test_v524_workspace_prefers_root_student_routes(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_dashboard_root"))
        self.assertEqual(response.status_code, 200)

        expected = {
            "home": reverse("student_dashboard_root"),
            "practice": reverse("student_practice_root"),
            "homework": reverse("student_homework_root"),
            "tests": reverse("practice_tests_root"),
            "classrooms": reverse("student_classrooms_root"),
            "vocabulary": reverse("vocabulary_root"),
            "progress": reverse("student_progress_root"),
            "messages": reverse("student_messages_root"),
            "events": reverse("events"),
            "placement": reverse("placement_tests"),
            "mentors": reverse("mentors"),
        }
        for key, url in expected.items():
            self.assertContains(response, f'href="{url}" data-nav-key="{key}"')
        self.assertNotContains(response, ">Enter code<")

    def test_ap_event_library_uses_student_workspace_and_staff_workspace_by_role(self):
        exam = APMockExam.objects.create(title="V50 AP Exam", status="published")
        event = APExamEvent.objects.create(
            title="V50 AP Event",
            exam=exam,
            status="live",
            always_live=True,
            is_public=True,
            is_global=True,
        )

        self.client.force_login(self.student)
        student_response = self.client.get(reverse("apclasses:event_list"))
        self.assertEqual(student_response.status_code, 200)
        self.assertContains(student_response, 'data-student-workspace')
        self.assertContains(student_response, 'data-nav-key="ap"')
        self.assertContains(student_response, 'AP exams without the clutter.')
        self.assertContains(student_response, event.title)

        detail_response = self.client.get(reverse("apclasses:event_detail", args=[event.slug]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'data-student-workspace')
        self.assertContains(detail_response, event.title)
        self.assertContains(detail_response, 'class="ap50-back"')

        self.client.force_login(self.teacher)
        teacher_response = self.client.get(reverse("apclasses:event_list"))
        self.assertEqual(teacher_response.status_code, 200)
        self.assertNotContains(teacher_response, 'data-student-workspace')
        self.assertContains(teacher_response, 'data-staff-workspace')
        self.assertContains(teacher_response, 'data-staff-mode="teacher"')
        self.assertContains(teacher_response, 'AP mock events')

    def test_v52_dashboard_shows_server_backed_level_streak_and_quests(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_dashboard_root"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-v50-gamification')
        self.assertContains(response, 'Daily quests')
        self.assertContains(response, 'Weekly quests')
        self.assertContains(response, 'Your consistency, measured.')
        self.assertContains(response, 'Level 1')
        self.assertTrue(GamificationProfile.objects.filter(user=self.student).exists())
        self.assertEqual(QuestProgress.objects.filter(user=self.student).count(), 6)

    def test_v52_vocabulary_review_awards_idempotent_xp_and_unlocks_first_badge(self):
        self.client.force_login(self.student)
        deck = VocabularyDeck.objects.create(owner=self.student, title="V52 deck")
        word = VocabularyDeckWord.objects.create(deck=deck, word="lucid", meaning="clear", order=1)

        first = self.client.post(
            reverse("vocabulary_deck_mark", args=[deck.id]),
            data='{"word_id": %d, "outcome": "known"}' % word.id,
            content_type="application/json",
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["gamification_xp"], 5)
        self.assertTrue(XPEvent.objects.filter(user=self.student, source_key=f"vocab:start:deckword:{word.id}").exists())
        self.assertTrue(UserAchievement.objects.filter(user=self.student, code="first_xp").exists())

        second = self.client.post(
            reverse("vocabulary_deck_mark", args=[deck.id]),
            data='{"word_id": %d, "outcome": "known"}' % word.id,
            content_type="application/json",
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["gamification_xp"], 15)
        self.assertEqual(XPEvent.objects.filter(user=self.student, source_key=f"vocab:start:deckword:{word.id}").count(), 1)
        self.assertEqual(XPEvent.objects.filter(user=self.student, source_key=f"vocab:mastered:deckword:{word.id}").count(), 1)

    def test_personal_vocabulary_decks_can_be_created_and_cloned_from_library(self):
        self.client.force_login(self.student)

        create_response = self.client.post(reverse("vocabulary_deck_create"), {
            "title": "My SAT Words",
            "description": "Private deck",
            "new_cards_per_day": "15",
            "max_reviews_per_day": "120",
        })
        self.assertEqual(create_response.status_code, 302)
        deck = VocabularyDeck.objects.get(owner=self.student, title="My SAT Words")

        add_response = self.client.post(reverse("vocabulary_deck_detail", args=[deck.id]), {
            "action": "add_word",
            "word": "laconic",
            "meaning": "using few words",
            "example": "Her reply was laconic.",
        })
        self.assertEqual(add_response.status_code, 302)
        self.assertTrue(VocabularyDeckWord.objects.filter(deck=deck, word="laconic").exists())

        unit = VocabularyUnit.objects.create(title="V50 Library Unit", order=99)
        VocabularyWord.objects.create(unit=unit, word="pragmatic", meaning="practical")
        clone_response = self.client.post(
            reverse("vocabulary_deck_clone_unit", args=[unit.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(clone_response.status_code, 201)
        self.assertTrue(clone_response.json()["added"])
        cloned = VocabularyDeck.objects.get(owner=self.student, source_unit=unit)
        self.assertTrue(cloned.words.filter(word="pragmatic").exists())

        duplicate_response = self.client.post(
            reverse("vocabulary_deck_clone_unit", args=[unit.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(duplicate_response.status_code, 200)
        self.assertTrue(duplicate_response.json()["already_added"])
        self.assertEqual(VocabularyDeck.objects.filter(owner=self.student, source_unit=unit).count(), 1)

        study_response = self.client.get(reverse("vocabulary_deck_study", args=[cloned.id]))
        self.assertEqual(study_response.status_code, 200)
        self.assertContains(study_response, 'data-memory-layers')

        word = cloned.words.get(word="pragmatic")
        mark_response = self.client.post(
            reverse("vocabulary_deck_mark", args=[cloned.id]),
            data='{"word_id": %d, "outcome": "known"}' % word.id,
            content_type="application/json",
        )
        self.assertEqual(mark_response.status_code, 200)
        self.assertTrue(mark_response.json()["ok"])
        self.assertTrue(VocabularyDeckWordProgress.objects.filter(user=self.student, word=word).exists())

        library_response = self.client.get(reverse("vocabulary_deck_library"))
        self.assertEqual(library_response.status_code, 200)
        self.assertContains(library_response, "Vocabulary library")
        self.assertContains(library_response, 'data-student-workspace')

    def test_vocabulary_v511_flow_is_deck_first_and_clone_is_in_place(self):
        unit = VocabularyUnit.objects.create(title="V505 Official", order=101)
        VocabularyWord.objects.create(unit=unit, word="terse", meaning="brief")
        self.client.force_login(self.student)

        overview = self.client.get(reverse("vocabulary"), follow=True)
        self.assertEqual(overview.status_code, 200)
        self.assertContains(overview, "Study modes")
        self.assertContains(overview, "Memory Layers")
        self.assertContains(overview, "Animated Immersion")
        self.assertContains(overview, "Word Bounce")
        self.assertContains(overview, "Meaning Match")
        self.assertContains(overview, "My decks")
        self.assertNotContains(overview, "Classroom flashcards")
        self.assertContains(overview, "Vocabulary rank")
        self.assertContains(overview, "Daily challenge")
        self.assertContains(overview, "Leaderboard")
        self.assertContains(overview, 'data-deck-carousel')
        self.assertContains(overview, 'vocabulary-home-v511.css')
        self.assertContains(overview, 'vocabulary-home-v511.js')

        library = self.client.get(reverse("vocabulary_deck_library"))
        self.assertEqual(library.status_code, 200)
        self.assertContains(library, "data-deck-clone-form")
        self.assertContains(library, "Adding a deck no longer sends you to another page")

        clone = self.client.post(
            reverse("vocabulary_deck_clone_unit", args=[unit.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(clone.status_code, 201)
        deck = VocabularyDeck.objects.get(owner=self.student, source_unit=unit)

        detail = self.client.get(reverse("vocabulary_deck_detail", args=[deck.id]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "data-word-create-dialog")
        self.assertContains(detail, "Study queue")

        study = self.client.get(reverse("vocabulary_deck_study", args=[deck.id]))
        self.assertEqual(study.status_code, 200)
        self.assertContains(study, "Still learning")
        self.assertContains(study, "data-save-state")
        self.assertContains(study, 'data-memory-layers')
        self.assertContains(study, 'vocabulary-arena-v509.css')
        self.assertContains(study, '?v=510')
        self.assertContains(study, 'vocabulary-memory-v509.js')

    def test_vocabulary_mode_picker_includes_all_personal_decks(self):
        self.client.force_login(self.student)
        for index in range(6):
            deck = VocabularyDeck.objects.create(owner=self.student, title=f"Picker Deck {index + 1}")
            VocabularyDeckWord.objects.create(deck=deck, word=f"word-{index}", meaning=f"meaning-{index}")

        response = self.client.get(reverse("vocabulary"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'vh506-deck-choices is-scrollable')
        for index in range(6):
            self.assertContains(response, f"Picker Deck {index + 1}")

    def test_vocabulary_decks_follow_unit_order_and_carousel_has_manual_controls(self):
        self.client.force_login(self.student)
        unit_two = VocabularyUnit.objects.create(title="Ordering Unit 2", order=202)
        unit_one = VocabularyUnit.objects.create(title="Ordering Unit 1", order=201)
        deck_two = VocabularyDeck.objects.create(owner=self.student, title="Ordering Unit 2", source_unit=unit_two)
        deck_one = VocabularyDeck.objects.create(owner=self.student, title="Ordering Unit 1", source_unit=unit_one)
        custom = VocabularyDeck.objects.create(owner=self.student, title="Custom Notes")
        for deck, token in ((deck_two, "two"), (deck_one, "one"), (custom, "custom")):
            VocabularyDeckWord.objects.create(deck=deck, word=token, meaning=token)

        response = self.client.get(reverse("vocabulary"), follow=True)
        self.assertEqual(response.status_code, 200)
        titles = [deck.title for deck in response.context["personal_decks"]]
        self.assertEqual(titles[:3], ["Ordering Unit 1", "Ordering Unit 2", "Custom Notes"])
        self.assertContains(response, 'data-deck-prev')
        self.assertContains(response, 'data-deck-next')
        self.assertContains(response, 'data-deck-dot')

        decks_response = self.client.get(reverse("vocabulary_decks"))
        self.assertEqual(decks_response.status_code, 200)
        self.assertEqual([deck.title for deck in decks_response.context["decks"]][:3], titles[:3])

    def test_learn_practice_and_tests_are_separate_routes(self):
        self.client.force_login(self.student)
        learn_url = reverse("student_learn_root")
        practice_url = reverse("student_practice_root")
        tests_url = reverse("practice_tests_root")
        self.assertNotEqual(learn_url, practice_url)
        self.assertNotEqual(practice_url, tests_url)
        self.assertNotEqual(learn_url, tests_url)

        learn = self.client.get(learn_url)
        practice = self.client.get(practice_url)
        tests = self.client.get(tests_url, follow=True)
        self.assertEqual(learn.status_code, 200)
        self.assertEqual(practice.status_code, 200)
        self.assertEqual(tests.status_code, 200)
        self.assertContains(learn, "Build the skill before you test it.")
        self.assertContains(practice, "Short reps. One skill at a time.")
        self.assertContains(tests, 'id="practiceTestsLibrary"')

        shell = self.client.get(reverse("student_dashboard_root"))
        self.assertContains(shell, f'href="{learn_url}" data-nav-key="learn"')
        self.assertContains(shell, f'href="{practice_url}" data-nav-key="practice"')
        self.assertContains(shell, f'href="{tests_url}" data-nav-key="tests"')

    def test_personal_deck_has_memory_and_arena_modes(self):
        self.client.force_login(self.student)
        deck = VocabularyDeck.objects.create(owner=self.student, title="Arena Deck")
        for index, pair in enumerate((("terse", "brief"), ("lucid", "clear"), ("novel", "new")), start=1):
            VocabularyDeckWord.objects.create(deck=deck, word=pair[0], meaning=pair[1], order=index)

        detail = self.client.get(reverse("vocabulary_deck_detail", args=[deck.id]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Memory Layers")
        self.assertContains(detail, "Animated")
        self.assertContains(detail, "Word Bounce")
        self.assertContains(detail, "Meaning Match")

        for mode in ("animated-immersion", "word-bounce", "meaning-match"):
            response = self.client.get(reverse("vocabulary_deck_arena", args=[deck.id, mode]))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'data-vocab-arena')
            self.assertContains(response, deck.title)

        bounce = self.client.get(reverse("vocabulary_deck_arena", args=[deck.id, "word-bounce"]))
        self.assertContains(bounce, 'data-lives="3"')
        self.assertContains(bounce, 'vocabulary-arena-v509.css')
        self.assertContains(bounce, 'vocabulary-arena-v509.js')
        self.assertContains(bounce, 'data-arena-score')
        self.assertContains(bounce, 'data-arena-streak')
        self.assertContains(bounce, 'data-arena-lives-wrap')

        legacy = self.client.get(reverse("vocabulary_deck_arena", args=[deck.id, "visual-match"]))
        self.assertEqual(legacy.status_code, 302)
        self.assertIn('/meaning-match/', legacy['Location'])

    def test_v525_legacy_sat_entry_redirects_to_canonical_dashboard(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("sat_menu"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("student_dashboard_root"))

    def test_v525_classroom_join_code_is_digit_only_in_ui_and_backend(self):
        self.client.force_login(self.student)
        page = self.client.get(reverse("student_classrooms_root"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'inputmode="numeric"')
        self.assertContains(page, 'pattern="[0-9]{6}"')
        self.assertContains(page, "replace(/\\D/g,'')")

        invalid = self.client.post(
            reverse("student_join_classroom_request_root"),
            {"code": "12AB34"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["message"], "Enter the 6-digit classroom code from your teacher.")

    def test_v525_dashboard_customizer_is_drag_only_and_optional_widgets_have_grid_contract(self):
        dashboard_js = (settings.BASE_DIR / "static/assets/js/student-dashboard-v524.js").read_text(encoding="utf-8")
        workspace_css = (settings.BASE_DIR / "static/assets/css/student-workspace-v525.css").read_text(encoding="utf-8")
        self.assertNotIn("data-up", dashboard_js)
        self.assertNotIn("data-down", dashboard_js)
        self.assertIn("Drag inside this list to reorder", dashboard_js)
        self.assertIn(".v524-optional-widget", workspace_css)
        self.assertIn("grid-column:span 3", workspace_css)

    def test_v525_sidebar_supports_custom_sections_and_direct_drag_without_moving_home(self):
        workspace_js = (settings.BASE_DIR / "static/assets/js/student-workspace-v50.js").read_text(encoding="utf-8")
        self.assertIn("New section name", workspace_js)
        self.assertIn("data-builder-group-section", workspace_js)
        self.assertIn("data-sidebar-custom", workspace_js)
        self.assertIn("item.dataset.sidebarLocked!=='1'", workspace_js)
        self.assertIn("group.remove()", workspace_js)

    def test_v525_messages_expose_media_drawer_themes_and_personal_sticker_packs(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_messages_root"))
        self.assertEqual(response.status_code, 200)
        for marker in (
            'data-chat-media-tab="emoji"',
            'data-chat-media-tab="stickers"',
            'data-chat-media-tab="gif"',
            'data-chat-pack-manager-open',
            'data-chat-pack-create',
            'data-chat-theme="makon"',
            'data-chat-theme="paper"',
            'data-chat-theme="midnight"',
            'data-chat-theme="blue"',
            'data-chat-theme-custom',
            'student-messages-v525.js?v=5265',
        ):
            self.assertContains(response, marker)

        created = self.client.post(
            reverse("student_chat_sticker_pack_create_root"),
            {"title": "Study reactions"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(created.status_code, 200)
        pack = UserChatStickerPack.objects.get(user=self.student, title="Study reactions")
        deleted = self.client.post(
            reverse("student_chat_sticker_pack_delete_root", args=[pack.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(UserChatStickerPack.objects.filter(pk=pack.id).exists())

    def test_v525_more_does_not_duplicate_placement_tests(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_dashboard_root"))
        self.assertEqual(response.status_code, 200)
        markup = response.content.decode()
        self.assertEqual(markup.count("<strong>Placement Tests</strong>"), 0)
        self.assertEqual(markup.count("<span>Placement Tests</span>"), 1)

    def test_v525_practice_has_inline_section_search_and_domain_filters(self):
        assigned_test = Test.objects.create(name="V525 Practice Filters", is_available=True)
        StudentPracticeTestAccess.objects.create(
            membership=self.membership,
            test=assigned_test,
            has_access=True,
        )
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_practice_root"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-practice-search')
        self.assertContains(response, 'data-practice-section="english"')
        self.assertContains(response, 'data-practice-section="math"')
        self.assertContains(response, 'data-practice-domain')

    def test_v525_mentor_directory_includes_regular_teacher_accounts(self):
        self.teacher.first_name = "Mentor"
        self.teacher.last_name = "Example"
        self.teacher.save(update_fields=["first_name", "last_name"])
        SupportTeacherProfile.objects.create(
            user=self.teacher,
            display_name="Mentor Example",
            education="SAT educator certificate",
            bio="Build the concept first, then add speed.",
            sat_total_score=1500,
            sat_math_score=780,
            sat_reading_writing_score=720,
        )
        self.client.force_login(self.student)
        response = self.client.get(reverse("mentors"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mentor Example")
        self.assertContains(response, "Certificates &amp; credentials")
        self.assertContains(response, "SAT educator certificate")
        self.assertContains(response, "Teacher note")
        self.assertNotContains(response, "Support profile")

    def test_v525_profile_is_compact_without_balance_or_student_id(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("edit_profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student account")
        self.assertContains(response, "SAT goal")
        self.assertNotContains(response, "Balance")
        self.assertNotContains(response, "Student ID")

    def test_v525_regular_teacher_can_open_and_fill_mentor_profile(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("mentor_profile_edit_root"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mentor Profile")
        self.assertContains(response, "Experience and credentials")
        self.assertContains(response, "SAT score profile")
        self.assertNotContains(response, "Lesson delivery")
        self.assertTrue(SupportTeacherProfile.objects.filter(user=self.teacher).exists())

    def test_v5261_sidebar_drag_is_handle_only_and_customize_supports_cross_section_drop(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_dashboard_root"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "student-workspace-v5261.css")
        self.assertContains(response, "student-workspace-v50.js?v=5261")

        js = (settings.BASE_DIR / "static" / "assets" / "js" / "student-workspace-v50.js").read_text(encoding="utf-8")
        css = (settings.BASE_DIR / "static" / "assets" / "css" / "student-workspace-v5261.css").read_text(encoding="utf-8")
        self.assertIn("mb526-nav-drag-handle", js)
        self.assertIn("mb526-section-drag-handle", js)
        self.assertIn("item.draggable=false", js.replace(" ", ""))
        self.assertIn("data-builder-group-list", js)
        self.assertIn(".mb526-nav-drag-handle", css)
        self.assertIn(".mb526-section-drag-handle", css)

    def test_v5261_more_does_not_duplicate_events(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_dashboard_root"))
        self.assertEqual(response.status_code, 200)
        markup = response.content.decode()
        self.assertIn('data-nav-key="events"', markup)
        self.assertEqual(markup.count("<strong>Events</strong>"), 0)
        self.assertEqual(markup.count("<span>Events</span>"), 1)

    def test_v5261_messages_expose_grouped_emoji_pack_creator_and_personal_background(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_messages_root"))
        self.assertEqual(response.status_code, 200)
        for marker in (
            'data-chat-emoji-search',
            'data-chat-pack-create-modal',
            'data-chat-pack-create-files',
            'data-chat-custom-background',
            'student-messages-v525.js?v=5265',
        ):
            self.assertContains(response, marker)
        self.assertContains(response, "Smileys")
        self.assertContains(response, "Hands &amp; reactions")
        self.assertContains(response, "Study &amp; symbols")

        js = (settings.BASE_DIR / "static" / "assets" / "js" / "student-messages-v525.js").read_text(encoding="utf-8")
        self.assertIn("makonbook.chat.background.v5261", js)
        self.assertIn("is-closing", js)
        self.assertIn("setTimeout", js)

    def test_v5261_mentors_are_split_between_main_and_support_tabs(self):
        support_teacher = User.objects.create_user(
            username="v526_support_teacher",
            password="pass123",
            first_name="Support",
            last_name="Mentor",
        )
        support_group, _ = Group.objects.get_or_create(name="Support Teacher")
        support_teacher.groups.add(support_group)
        SupportTeacherProfile.objects.create(
            user=support_teacher,
            display_name="Support Mentor",
            is_active=True,
            bio="Support mentor profile",
        )
        self.teacher.first_name = "Main"
        self.teacher.last_name = "Mentor"
        self.teacher.save(update_fields=["first_name", "last_name"])

        self.client.force_login(self.student)
        response = self.client.get(reverse("mentors"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-mentor-tab="main"')
        self.assertContains(response, 'data-mentor-tab="support"')
        self.assertContains(response, "Main Teachers")
        self.assertContains(response, "Support Teachers")
        self.assertContains(response, "Main Mentor")
        self.assertContains(response, "Support Mentor")
        self.assertContains(response, "Swipe left or right to switch")

    def test_v5261_practice_controls_keep_equal_width_contract_for_both_sections(self):
        css = (settings.BASE_DIR / "static" / "assets" / "css" / "student-workspace-v5261.css").read_text(encoding="utf-8")
        compact = css.replace(" ", "").replace("\n", "")
        self.assertIn("grid-template-columns:minmax(0,1fr)194px330px", compact)
        self.assertIn(".v525-practice-segment", css)
        self.assertIn(".v525-practice-filter", css)

    def test_v5261_profile_uses_modals_and_password_change_keeps_session(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("edit_profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-profile-modal="profile"')
        self.assertContains(response, 'data-profile-modal="password"')
        self.assertContains(response, 'name="profile_action" value="password"')
        self.assertContains(response, "Change password")
        self.assertContains(response, "Edit profile")
        self.assertNotContains(response, "Rewards count")
        self.assertContains(response, "No XP, discount or cash reward is configured yet.")

        changed = self.client.post(
            reverse("edit_profile"),
            {
                "profile_action": "password",
                "old_password": "pass123",
                "new_password1": "V5261-Strong-Password!",
                "new_password2": "V5261-Strong-Password!",
            },
        )
        self.assertEqual(changed.status_code, 302)
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password("V5261-Strong-Password!"))
        followup = self.client.get(reverse("student_dashboard_root"))
        self.assertEqual(followup.status_code, 200)
        self.assertEqual(followup.wsgi_request.user.pk, self.student.pk)

    def test_v5261_admissions_cards_and_mentor_cards_have_spacing_rounding_contracts(self):
        css = (settings.BASE_DIR / "static" / "assets" / "css" / "student-workspace-v5261.css").read_text(encoding="utf-8")
        compact = css.replace(" ", "").replace("\n", "")
        self.assertIn(".v524-admissions-content", css)
        self.assertIn("gap:18px", compact)
        self.assertIn(".v526-mentor-panel .v524-mentor-grid", css)
        self.assertIn("border-radius:24px", compact)

    def test_v5262_chat_header_profile_spacing_and_dark_preloader_contract(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_messages_root"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "student-workspace-v5262.css?v=5262")
        self.assertContains(response, "makon-theme.css?v=5262")

        css = (settings.BASE_DIR / "static" / "assets" / "css" / "student-workspace-v5262.css").read_text(encoding="utf-8")
        compact = css.replace(" ", "").replace("\n", "")
        self.assertIn("grid-template-rows:72pxminmax(0,1fr)auto!important", compact)
        self.assertIn("position:sticky!important", compact)
        self.assertIn(".v525-profile-page{gap:8px!important}", compact)
        self.assertIn(".v526-profile-lower{gap:8px!important", compact)

        theme_css = (settings.BASE_DIR / "static" / "assets" / "css" / "makon-theme.css").read_text(encoding="utf-8")
        self.assertIn('html[data-theme="dark"] #preloader', theme_css)
        self.assertIn("makon-dark-preloader-orbit", theme_css)
        self.assertIn("makon-dark-preloader-pulse", theme_css)
    def test_v5263_chat_header_collapsed_rail_and_selection_guard_contract(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_messages_root"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "student-workspace-v5263.css?v=5263")

        css = (settings.BASE_DIR / "static" / "assets" / "css" / "student-workspace-v5263.css").read_text(encoding="utf-8")
        compact = css.replace(" ", "").replace("\n", "")
        self.assertIn("position:absolute!important", compact)
        self.assertIn("padding-top:94px!important", compact)
        self.assertIn("background:var(--mb50-panel)!important", compact)
        self.assertIn(".mb50-nav-item.mb526-nav-drag-enabled", css)
        self.assertIn("padding:0!important", compact)
        self.assertIn("width:220px!important", compact)
        self.assertIn(".mb50-shell,.mb50-shell*", compact)
        self.assertIn("user-select:none!important", compact)
        self.assertIn(".mb50-shelltextarea", compact)
        self.assertIn("user-select:text!important", compact)

    def test_v5264_chat_header_is_structurally_outside_the_themed_canvas(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_messages_root") + f"?classroom={self.classroom.id}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "student-workspace-v5264.css?v=5264")
        self.assertContains(response, 'class="v5264-chat-room-head"')
        self.assertContains(response, 'class="v5264-chat-canvas"')

        markup = response.content.decode()
        self.assertLess(markup.index('class="v5264-chat-room-head"'), markup.index('class="v5264-chat-canvas"'))

        css = (settings.BASE_DIR / "static" / "assets" / "css" / "student-workspace-v5264.css").read_text(encoding="utf-8")
        compact = css.replace(" ", "").replace("\n", "")
        self.assertIn("grid-template-rows:72pxminmax(0,1fr)!important", compact)
        self.assertIn(".v5264-chat-canvas", css)
        self.assertIn("background-image:none!important", compact)
        self.assertIn('[data-chat-theme="makon"].v5264-chat-canvas', compact)

    def test_v5265_chat_header_is_top_level_and_hover_emoji_stays_open(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_messages_root") + f"?classroom={self.classroom.id}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "student-workspace-v5265.css?v=5265")
        self.assertContains(response, "student-messages-v525.js?v=5265")
        self.assertContains(response, 'v5265-chat-has-room')
        self.assertContains(response, 'class="v523-chat-thread v5265-chat-thread-has-room"')

        markup = response.content.decode()
        inbox_end = markup.index("</aside>")
        room_head = markup.index('class="v5264-chat-room-head"')
        thread = markup.index('class="v523-chat-thread v5265-chat-thread-has-room"')
        self.assertLess(inbox_end, room_head)
        self.assertLess(room_head, thread)

        css = (settings.BASE_DIR / "static" / "assets" / "css" / "student-workspace-v5265.css").read_text(encoding="utf-8")
        compact_css = css.replace(" ", "").replace("\n", "")
        self.assertIn("grid-template-rows:72pxminmax(0,1fr)!important", compact_css)
        self.assertIn("grid-row:1!important", compact_css)
        self.assertIn("--v5265-media-preview-top", css)
        self.assertIn("transform-origin:bottomleft!important", compact_css)

        js = (settings.BASE_DIR / "static" / "assets" / "js" / "student-messages-v525.js").read_text(encoding="utf-8")
        self.assertIn("function positionMediaPreview()", js)
        self.assertIn("root.dataset.chatReady = '5265'", js)
        emoji_handler = js.split("root.querySelectorAll('[data-chat-sticker]').forEach", 1)[1].split("function customStickerMarkup", 1)[0]
        self.assertNotIn("closeMedia", emoji_handler)
