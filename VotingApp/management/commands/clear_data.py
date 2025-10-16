from django.core.management.base import BaseCommand
from VotingApp.models import Voter, Candidate, Vote, ElectionSettings


class Command(BaseCommand):
    help = 'Clear test data from the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Delete all data including candidates',
        )
        parser.add_argument(
            '--votes-only',
            action='store_true',
            help='Delete only votes',
        )
        parser.add_argument(
            '--voters-only',
            action='store_true',
            help='Delete only voters (and their votes)',
        )

    def handle(self, *args, **options):
        if options['votes_only']:
            # Delete only votes
            vote_count = Vote.objects.count()
            Vote.objects.all().delete()
            
            # Reset has_voted flag for all voters
            Voter.objects.update(has_voted=False)
            
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted {vote_count} votes'))
            self.stdout.write(self.style.SUCCESS('Reset all voters has_voted status'))
            
        elif options['voters_only']:
            # Delete voters (this will cascade delete votes too)
            voter_count = Voter.objects.count()
            vote_count = Vote.objects.count()
            Voter.objects.all().delete()
            
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted {voter_count} voters and {vote_count} votes'))
            
        elif options['all']:
            # Delete everything except admin users and settings
            vote_count = Vote.objects.count()
            voter_count = Voter.objects.count()
            candidate_count = Candidate.objects.count()
            
            Vote.objects.all().delete()
            Voter.objects.all().delete()
            Candidate.objects.all().delete()
            
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted:'))
            self.stdout.write(self.style.SUCCESS(f'  - {vote_count} votes'))
            self.stdout.write(self.style.SUCCESS(f'  - {voter_count} voters'))
            self.stdout.write(self.style.SUCCESS(f'  - {candidate_count} candidates'))
            self.stdout.write(self.style.WARNING('Admin users and election settings preserved'))
            
        else:
            # Default: Delete votes and voters, keep candidates
            vote_count = Vote.objects.count()
            voter_count = Voter.objects.count()
            
            Vote.objects.all().delete()
            Voter.objects.all().delete()
            
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted:'))
            self.stdout.write(self.style.SUCCESS(f'  - {vote_count} votes'))
            self.stdout.write(self.style.SUCCESS(f'  - {voter_count} voters'))
            self.stdout.write(self.style.WARNING('Candidates, admin users, and settings preserved'))

