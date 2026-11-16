import datetime
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Task

User = get_user_model()


class TaskModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword123',
        )

    def test_string_representation(self):
        task = Task.objects.create(
            title='Sample Task',
            user=self.user,
        )
        self.assertEqual(str(task), 'Sample Task')

    def test_field_defaults(self):
        task = Task.objects.create(
            title='Default Values Task',
            user=self.user,
        )
        self.assertFalse(task.is_completed)
        self.assertEqual(task.date, timezone.localdate())
        self.assertEqual(task.description, '')
        self.assertIsNotNone(task.created_at)

    def test_optional_description(self):
        task_without_desc = Task.objects.create(
            title='No Description Task',
            user=self.user,
        )
        self.assertEqual(task_without_desc.description, '')

        task_with_desc = Task.objects.create(
            title='With Description Task',
            description='This is a test description.',
            user=self.user,
        )
        self.assertEqual(task_with_desc.description, 'This is a test description.')

    def test_user_relationship(self):
        task1 = Task.objects.create(title='Task 1', user=self.user)
        task2 = Task.objects.create(title='Task 2', user=self.user)

        self.assertEqual(self.user.tasks.count(), 2)
        self.assertIn(task1, self.user.tasks.all())
        self.assertIn(task2, self.user.tasks.all())
        self.assertEqual(task1.user, self.user)

    def test_user_cascade_delete(self):
        Task.objects.create(title='Task to Delete', user=self.user)
        self.assertEqual(Task.objects.count(), 1)

        self.user.delete()
        self.assertEqual(Task.objects.count(), 0)


class AuthenticationTests(TestCase):
    def setUp(self):
        self.username = 'authuser'
        self.email = 'authuser@example.com'
        self.password = 'ComplexPass123!'
        self.user = User.objects.create_user(
            username=self.username,
            email=self.email,
            password=self.password,
        )

    # 1. Registration Tests
    def test_registration_page_get(self):
        response = self.client.get(reverse('tasks:register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/register.html')
        self.assertIn('form', response.context)

    def test_successful_registration(self):
        response = self.client.post(reverse('tasks:register'), {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'StrongSecret123!',
            'password2': 'StrongSecret123!',
        })
        self.assertRedirects(response, reverse('tasks:login'))
        self.assertTrue(User.objects.filter(username='newuser').exists())

        new_user = User.objects.get(username='newuser')
        self.assertEqual(new_user.email, 'newuser@example.com')
        self.assertNotEqual(new_user.password, 'StrongSecret123!')
        self.assertTrue(new_user.check_password('StrongSecret123!'))

    def test_invalid_registration_missing_fields(self):
        response = self.client.post(reverse('tasks:register'), {
            'username': '',
            'email': '',
            'password1': '',
            'password2': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/register.html')
        self.assertTrue(response.context['form'].errors)

    def test_registration_password_mismatch(self):
        response = self.client.post(reverse('tasks:register'), {
            'username': 'mismatchuser',
            'email': 'mismatch@example.com',
            'password1': 'StrongSecret123!',
            'password2': 'DifferentSecret456!',
        })
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertIn('password2', form.errors)
        self.assertFalse(User.objects.filter(username='mismatchuser').exists())

    def test_registration_duplicate_username(self):
        response = self.client.post(reverse('tasks:register'), {
            'username': self.username,
            'email': 'another@example.com',
            'password1': 'StrongSecret123!',
            'password2': 'StrongSecret123!',
        })
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn('username', form.errors)

    # 2. Login Tests
    def test_login_page_get(self):
        response = self.client.get(reverse('tasks:login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/login.html')
        self.assertIn('form', response.context)

    def test_successful_login(self):
        response = self.client.post(reverse('tasks:login'), {
            'username': self.username,
            'password': self.password,
        })
        self.assertRedirects(response, reverse('tasks:dashboard'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_invalid_login_wrong_password(self):
        response = self.client.post(reverse('tasks:login'), {
            'username': self.username,
            'password': 'WrongPassword!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/login.html')
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_invalid_login_nonexistent_user(self):
        response = self.client.post(reverse('tasks:login'), {
            'username': 'nobody',
            'password': 'AnyPassword123!',
        })
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertNotIn('_auth_user_id', self.client.session)

    # 3. Logout Tests
    def test_successful_logout(self):
        self.client.login(username=self.username, password=self.password)
        self.assertIn('_auth_user_id', self.client.session)

        response = self.client.post(reverse('tasks:logout'))
        self.assertRedirects(response, reverse('tasks:login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_via_get_method_not_allowed(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse('tasks:logout'))
        self.assertEqual(response.status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)

    # 4. Protection & Redirect Tests
    def test_unauthenticated_user_redirected_to_login(self):
        dashboard_url = reverse('tasks:dashboard')
        response = self.client.get(dashboard_url)
        expected_redirect = f"{reverse('tasks:login')}?next={dashboard_url}"
        self.assertRedirects(response, expected_redirect)

    def test_unauthenticated_user_redirected_from_root(self):
        root_url = reverse('tasks:index')
        response = self.client.get(root_url)
        expected_redirect = f"{reverse('tasks:login')}?next={root_url}"
        self.assertRedirects(response, expected_redirect)

    def test_authenticated_user_access_protected_page(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse('tasks:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tasks/dashboard.html')
        self.assertContains(response, f"Welcome, {self.username}!")

    def test_authenticated_user_redirected_away_from_login(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse('tasks:login'))
        self.assertRedirects(response, reverse('tasks:dashboard'))

    def test_authenticated_user_redirected_away_from_register(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse('tasks:register'))
        self.assertRedirects(response, reverse('tasks:dashboard'))


class TaskManagementTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(
            username='user_a',
            email='user_a@example.com',
            password='PasswordA123!',
        )
        self.user_b = User.objects.create_user(
            username='user_b',
            email='user_b@example.com',
            password='PasswordB123!',
        )
        self.task_a = Task.objects.create(
            title="User A Task",
            description="Details for Task A",
            date=datetime.date(2026, 11, 20),
            is_completed=False,
            user=self.user_a,
        )
        self.task_b = Task.objects.create(
            title="User B Task",
            description="Details for Task B",
            date=datetime.date(2026, 11, 25),
            is_completed=False,
            user=self.user_b,
        )

    # 1. Creating a task
    def test_create_task(self):
        self.client.login(username='user_a', password='PasswordA123!')
        response = self.client.post(reverse('tasks:task_create'), {
            'title': 'New Created Task',
            'description': 'Description for new task',
            'date': '2026-11-22',
        })
        self.assertRedirects(response, reverse('tasks:task_list'))

        task = Task.objects.get(title='New Created Task')
        self.assertEqual(task.user, self.user_a)
        self.assertEqual(task.description, 'Description for new task')
        self.assertEqual(task.date, datetime.date(2026, 11, 22))
        self.assertFalse(task.is_completed)

    def test_invalid_task_create_data(self):
        self.client.login(username='user_a', password='PasswordA123!')
        response = self.client.post(reverse('tasks:task_create'), {
            'title': '',
            'description': 'No title provided',
            'date': '2026-11-22',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertIn('title', response.context['form'].errors)

    # 2. Viewing task lists
    def test_view_task_list(self):
        self.client.login(username='user_a', password='PasswordA123!')
        response = self.client.get(reverse('tasks:task_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tasks/task_list.html')
        self.assertContains(response, self.task_a.title)
        self.assertNotContains(response, self.task_b.title)

    # 3. Editing a task
    def test_edit_task(self):
        self.client.login(username='user_a', password='PasswordA123!')
        response = self.client.post(reverse('tasks:task_update', kwargs={'pk': self.task_a.pk}), {
            'title': 'Updated Task A Title',
            'description': 'Updated Description',
            'date': '2026-11-28',
        })
        self.assertRedirects(response, reverse('tasks:task_list'))

        self.task_a.refresh_from_db()
        self.assertEqual(self.task_a.title, 'Updated Task A Title')
        self.assertEqual(self.task_a.description, 'Updated Description')
        self.assertEqual(self.task_a.date, datetime.date(2026, 11, 28))
        self.assertEqual(self.task_a.user, self.user_a)

    # 4. Deleting a task
    def test_delete_task(self):
        self.client.login(username='user_a', password='PasswordA123!')
        # GET renders confirmation page
        get_response = self.client.get(reverse('tasks:task_delete', kwargs={'pk': self.task_a.pk}))
        self.assertEqual(get_response.status_code, 200)
        self.assertTemplateUsed(get_response, 'tasks/task_confirm_delete.html')

        # POST performs deletion
        post_response = self.client.post(reverse('tasks:task_delete', kwargs={'pk': self.task_a.pk}))
        self.assertRedirects(post_response, reverse('tasks:task_list'))
        self.assertFalse(Task.objects.filter(pk=self.task_a.pk).exists())

    # 5. Marking a task completed
    def test_mark_task_completed(self):
        self.client.login(username='user_a', password='PasswordA123!')
        self.assertFalse(self.task_a.is_completed)

        response = self.client.post(reverse('tasks:task_toggle', kwargs={'pk': self.task_a.pk}))
        self.assertRedirects(response, reverse('tasks:task_list'))

        self.task_a.refresh_from_db()
        self.assertTrue(self.task_a.is_completed)

    # 6. Marking a task pending
    def test_mark_task_pending(self):
        self.task_a.is_completed = True
        self.task_a.save()

        self.client.login(username='user_a', password='PasswordA123!')
        response = self.client.post(reverse('tasks:task_toggle', kwargs={'pk': self.task_a.pk}))
        self.assertRedirects(response, reverse('tasks:task_list'))

        self.task_a.refresh_from_db()
        self.assertFalse(self.task_a.is_completed)

    # 7. Unauthenticated access
    def test_unauthenticated_access_to_task_endpoints(self):
        endpoints = [
            reverse('tasks:task_list'),
            reverse('tasks:task_create'),
            reverse('tasks:task_detail', kwargs={'pk': self.task_a.pk}),
            reverse('tasks:task_update', kwargs={'pk': self.task_a.pk}),
            reverse('tasks:task_delete', kwargs={'pk': self.task_a.pk}),
        ]
        login_url = reverse('tasks:login')
        for url in endpoints:
            response = self.client.get(url)
            self.assertRedirects(response, f"{login_url}?next={url}")

        toggle_url = reverse('tasks:task_toggle', kwargs={'pk': self.task_a.pk})
        post_response = self.client.post(toggle_url)
        self.assertRedirects(post_response, f"{login_url}?next={toggle_url}")

    # 8. User A cannot view User B's task
    def test_user_a_cannot_view_user_b_task(self):
        self.client.login(username='user_a', password='PasswordA123!')
        response = self.client.get(reverse('tasks:task_detail', kwargs={'pk': self.task_b.pk}))
        self.assertEqual(response.status_code, 404)

        list_response = self.client.get(reverse('tasks:task_list'))
        self.assertNotContains(list_response, self.task_b.title)

    # 9. User A cannot edit User B's task
    def test_user_a_cannot_edit_user_b_task(self):
        self.client.login(username='user_a', password='PasswordA123!')
        get_response = self.client.get(reverse('tasks:task_update', kwargs={'pk': self.task_b.pk}))
        self.assertEqual(get_response.status_code, 404)

        post_response = self.client.post(reverse('tasks:task_update', kwargs={'pk': self.task_b.pk}), {
            'title': 'Hacked Task B Title',
            'date': '2026-11-25',
        })
        self.assertEqual(post_response.status_code, 404)

        self.task_b.refresh_from_db()
        self.assertEqual(self.task_b.title, "User B Task")

    # 10. User A cannot delete User B's task
    def test_user_a_cannot_delete_user_b_task(self):
        self.client.login(username='user_a', password='PasswordA123!')
        get_response = self.client.get(reverse('tasks:task_delete', kwargs={'pk': self.task_b.pk}))
        self.assertEqual(get_response.status_code, 404)

        post_response = self.client.post(reverse('tasks:task_delete', kwargs={'pk': self.task_b.pk}))
        self.assertEqual(post_response.status_code, 404)

        self.assertTrue(Task.objects.filter(pk=self.task_b.pk).exists())

    # User A cannot toggle User B's task
    def test_user_a_cannot_toggle_user_b_task(self):
        self.client.login(username='user_a', password='PasswordA123!')
        response = self.client.post(reverse('tasks:task_toggle', kwargs={'pk': self.task_b.pk}))
        self.assertEqual(response.status_code, 404)

        self.task_b.refresh_from_db()
        self.assertFalse(self.task_b.is_completed)



class DashboardAndUIEnhancementTests(TestCase):
    def setUp(self):
        self.user_main = User.objects.create_user(
            username='main_user',
            email='main_user@example.com',
            password='Password123!',
        )
        self.user_other = User.objects.create_user(
            username='other_user',
            email='other_user@example.com',
            password='Password123!',
        )
        self.today = timezone.localdate()
        self.yesterday = self.today - datetime.timedelta(days=1)
        self.last_week = self.today - datetime.timedelta(days=7)
        self.tomorrow = self.today + datetime.timedelta(days=1)

    # 1. Dashboard requires authentication
    def test_dashboard_requires_authentication(self):
        dashboard_url = reverse('tasks:dashboard')
        response = self.client.get(dashboard_url)
        self.assertRedirects(response, f"{reverse('tasks:login')}?next={dashboard_url}")

    # 2. Dashboard displays correct total task count
    def test_dashboard_displays_correct_total_task_count(self):
        Task.objects.create(title='Task 1', date=self.today, user=self.user_main)
        Task.objects.create(title='Task 2', date=self.yesterday, user=self.user_main)
        Task.objects.create(title='Task 3', date=self.tomorrow, user=self.user_main)
        # Other user's task must not be counted
        Task.objects.create(title='Other Task', date=self.today, user=self.user_other)

        self.client.login(username='main_user', password='Password123!')
        response = self.client.get(reverse('tasks:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_count'], 3)
        self.assertContains(response, 'id="stat-total">3</div>')

    # 3. Completed and pending counts are accurate
    def test_completed_and_pending_counts_accurate(self):
        Task.objects.create(title='Done 1', date=self.today, is_completed=True, user=self.user_main)
        Task.objects.create(title='Done 2', date=self.yesterday, is_completed=True, user=self.user_main)
        Task.objects.create(title='Pending 1', date=self.today, is_completed=False, user=self.user_main)
        # Other user's tasks
        Task.objects.create(title='Other Done', date=self.today, is_completed=True, user=self.user_other)
        Task.objects.create(title='Other Pending', date=self.today, is_completed=False, user=self.user_other)

        self.client.login(username='main_user', password='Password123!')
        response = self.client.get(reverse('tasks:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['completed_count'], 2)
        self.assertEqual(response.context['pending_count'], 1)
        self.assertEqual(response.context['completion_rate'], 66.7)

    # 4. Today's tasks are filtered correctly
    def test_todays_tasks_filtered_correctly(self):
        today_task1 = Task.objects.create(title='Today Task Alpha', date=self.today, user=self.user_main)
        today_task2 = Task.objects.create(title='Today Task Beta', date=self.today, user=self.user_main)
        past_task = Task.objects.create(title='Yesterday Task', date=self.yesterday, user=self.user_main)
        future_task = Task.objects.create(title='Tomorrow Task', date=self.tomorrow, user=self.user_main)

        self.client.login(username='main_user', password='Password123!')
        response = self.client.get(reverse('tasks:dashboard'))
        self.assertEqual(response.status_code, 200)

        today_tasks = list(response.context['today_tasks'])
        self.assertEqual(len(today_tasks), 2)
        self.assertIn(today_task1, today_tasks)
        self.assertIn(today_task2, today_tasks)
        self.assertNotIn(past_task, today_tasks)
        self.assertNotIn(future_task, today_tasks)

        self.assertContains(response, 'Today Task Alpha')
        self.assertContains(response, 'Today Task Beta')

    # 5. Task history is grouped correctly
    def test_task_history_grouped_correctly(self):
        past1 = Task.objects.create(title='Yesterday Task 1', date=self.yesterday, user=self.user_main)
        past2 = Task.objects.create(title='Yesterday Task 2', date=self.yesterday, user=self.user_main)
        past3 = Task.objects.create(title='Last Week Task', date=self.last_week, user=self.user_main)
        today_task = Task.objects.create(title='Current Today Task', date=self.today, user=self.user_main)

        self.client.login(username='main_user', password='Password123!')
        # Test history on dashboard
        response = self.client.get(reverse('tasks:dashboard'))
        self.assertEqual(response.status_code, 200)
        history_tasks = list(response.context['history_tasks'])
        self.assertEqual(len(history_tasks), 3)
        self.assertIn(past1, history_tasks)
        self.assertIn(past2, history_tasks)
        self.assertIn(past3, history_tasks)
        self.assertNotIn(today_task, history_tasks)

        # Test dedicated history page
        history_response = self.client.get(reverse('tasks:task_history'))
        self.assertEqual(history_response.status_code, 200)
        self.assertTemplateUsed(history_response, 'tasks/task_history.html')
        self.assertContains(history_response, 'Yesterday Task 1')
        self.assertContains(history_response, 'Yesterday Task 2')
        self.assertContains(history_response, 'Last Week Task')

    # 6. Users cannot see other users' tasks
    def test_users_cannot_see_other_users_tasks(self):
        Task.objects.create(title='Secret Other Today', date=self.today, user=self.user_other)
        Task.objects.create(title='Secret Other Past', date=self.yesterday, user=self.user_other)

        self.client.login(username='main_user', password='Password123!')
        response = self.client.get(reverse('tasks:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_count'], 0)
        self.assertNotContains(response, 'Secret Other Today')
        self.assertNotContains(response, 'Secret Other Past')

        history_response = self.client.get(reverse('tasks:task_history'))
        self.assertNotContains(history_response, 'Secret Other Past')

    # 7. Empty dashboard states work correctly
    def test_empty_dashboard_states(self):
        self.client.login(username='main_user', password='Password123!')
        response = self.client.get(reverse('tasks:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_count'], 0)
        self.assertEqual(response.context['completed_count'], 0)
        self.assertEqual(response.context['pending_count'], 0)
        self.assertContains(response, 'No tasks scheduled for today')
        self.assertContains(response, 'No previous task history')

        history_response = self.client.get(reverse('tasks:task_history'))
        self.assertEqual(history_response.status_code, 200)
        self.assertContains(history_response, 'No Task History Found')
