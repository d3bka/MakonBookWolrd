from celery import shared_task
from .assessment_policy import prepare_today_obligations, settle_missed_assessments, send_pending_daily_manager_reports, send_teacher_evening_reminders


@shared_task(name='apps.ratings.tasks.settle_assessments')
def settle_assessments():
    created = prepare_today_obligations()
    fines = settle_missed_assessments()
    sent = send_pending_daily_manager_reports()
    return {'obligations_created': created, 'new_fines': len(fines), 'daily_report_sent': sent}


@shared_task(name='apps.ratings.tasks.remind_teachers_evening')
def remind_teachers_evening():
    return {'reminders_sent': send_teacher_evening_reminders()}
