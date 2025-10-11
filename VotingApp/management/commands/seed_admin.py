from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from VotingApp.models import AdminUser


class Command(BaseCommand):
    help = 'Creates default admin user if it does not exist'

    def handle(self, *args, **options):
        username = 'admin'
        email = 'admin@voting.com'
        password = 'admin123'
        
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'Admin user "{username}" already exists'))
            return
        
        # Create admin user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            is_staff=True,
            is_superuser=True
        )
        
        # Create AdminUser profile
        AdminUser.objects.create(user=user)
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created admin user: {username}'))
        self.stdout.write(self.style.SUCCESS(f'Email: {email}'))
        self.stdout.write(self.style.SUCCESS(f'Password: {password}'))

