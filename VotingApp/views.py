from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.models import User
from .models import Voter, Candidate, Vote, AdminUser, ElectionSettings
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.utils import timezone
from django.views.decorators.http import require_http_methods
import pytz
from datetime import datetime
import csv
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

def landing_page(request):
    """Landing page for the chairperson election with real-time results"""
    # Get all candidates with their vote counts
    candidates_qs = Candidate.objects.annotate(votes_count=Count('vote')).order_by('position', '-votes_count', 'name')
    
    # Calculate total votes cast
    total_votes = Vote.objects.count()
    total_voters = Voter.objects.count()
    
    # Build candidate list with percentages and group by position
    candidates_by_position = {}
    for c in candidates_qs:
        percentage = round((c.votes_count / total_votes) * 100, 1) if total_votes else 0
        candidate_data = {
            'id': c.id,
            'name': c.name,
            'nickname': c.nickname,
            'position': c.position,
            'photo': c.photo,
            'votes': c.votes_count,
            'percentage': percentage,
            'is_winner': False,  # Will be set below
        }
        
        if c.position not in candidates_by_position:
            candidates_by_position[c.position] = []
        candidates_by_position[c.position].append(candidate_data)
    
    # Mark winners for each position
    for position, candidates in candidates_by_position.items():
        if candidates and candidates[0]['votes'] > 0:
            # Check if there's a tie (top 2 candidates have same votes)
            is_tie = len(candidates) >= 2 and candidates[0]['votes'] == candidates[1]['votes']
            # Mark the first candidate as winner only if no tie
            if not is_tie:
                candidates[0]['is_winner'] = True
    
    # Determine winner per position
    winners = {}
    for position, candidates in candidates_by_position.items():
        if candidates and candidates[0]['votes'] > 0:
            # Check for tie in this position
            is_tie = len(candidates) >= 2 and candidates[0]['votes'] == candidates[1]['votes']
            winners[position] = {
                'candidate': candidates[0] if not is_tie else None,
                'is_tie': is_tie
            }
    
    # Get election settings
    settings = ElectionSettings.get_settings()
    
    # Determine election status
    now = timezone.now()
    election_status = 'Active'
    if settings.end_time:
        if now > settings.end_time:
            election_status = 'Ended'
        elif settings.start_time and now < settings.start_time:
            election_status = 'Not Started'
    
    context = {
        'election_title': settings.election_title,
        'election_description': settings.election_description,
        'election_status': election_status,
        'end_time': settings.end_time,
        'start_time': settings.start_time,
        'timezone_name': settings.timezone,
        'candidate_count': candidates_qs.count(),
        'candidates_by_position': candidates_by_position,
        'total_votes': total_votes,
        'total_voters': total_voters,
        'winners': winners,
    }
    return render(request, 'landing.html', context)

def login_page(request):
    """Login page for phone number entry"""
    # Check election settings
    settings = ElectionSettings.get_settings()
    now = timezone.now()
    
    # Check if voting is active
    if not settings.is_active:
        messages.error(request, 'Voting is currently disabled.')
        return redirect('landing')
    
    # Check if voting has started
    if settings.start_time and now < settings.start_time:
        messages.error(request, f'Voting has not started yet. Please come back after {settings.start_time.strftime("%B %d, %Y at %I:%M %p")}.')
        return redirect('landing')
    
    # Check if voting has ended
    if settings.end_time and now > settings.end_time:
        messages.error(request, f'Voting has ended on {settings.end_time.strftime("%B %d, %Y at %I:%M %p")}.')
        return redirect('landing')
    
    if request.method == 'POST':
        phone = request.POST.get('phone_number', '').strip()
        normalized = Voter.normalize_phone_number(phone)
        voter = Voter.objects.filter(phone_number=normalized).first()
        if voter:
            request.session['voter_phone'] = voter.phone_number
            return redirect('vote')
        messages.error(request, 'Phone number not found. Please contact admin.')
    return render(request, 'login.html')

def results_page(request):
    """Results page showing election results - Admin only"""
    if not request.session.get('is_admin'):
        return render(request, 'admin_login.html')

    # Overall totals
    total_votes = Vote.objects.count()
    total_voters = Voter.objects.count()
    unique_voters_voted = Vote.objects.values('voter_id').distinct().count()
    turnout_pct = round((unique_voters_voted / total_voters) * 100, 2) if total_voters else 0

    # Candidates annotated with vote counts
    candidates_qs = Candidate.objects.annotate(votes_count=Count('vote')).order_by('-votes_count', 'name')

    # Winner (overall top by votes)
    top_candidate = candidates_qs.first()
    winner_name = top_candidate.name if top_candidate else '—'

    # Build overall list with percentage (out of overall total)
    overall = []
    for c in candidates_qs:
        percent = round((c.votes_count / total_votes) * 100, 2) if total_votes else 0
        overall.append({'name': c.name, 'votes': c.votes_count, 'percentage': percent})

    # Group by position
    by_section = {}
    for c in candidates_qs:
        by_section.setdefault(c.position, []).append(c)

    grouped_sections = []
    for position, items in by_section.items():
        section_total = sum(i.votes_count for i in items)
        items_sorted = sorted(items, key=lambda x: (-x.votes_count, x.name))
        section_rows = [
            {
                'name': i.name,
                'votes': i.votes_count,
                'percentage': round((i.votes_count / section_total) * 100, 2) if section_total else 0,
            }
            for i in items_sorted
        ]
        grouped_sections.append({
            'position': position,
            'total': section_total,
            'rows': section_rows,
        })

    # Approximate duration from first vote to now
    try:
        first_vote_time = Vote.objects.earliest('voted_at').voted_at
        duration_hours = int((timezone.now() - first_vote_time).total_seconds() // 3600)
    except Vote.DoesNotExist:
        duration_hours = 0

    context = {
        'election_title': 'Chairperson Election 2024',
        'winner': winner_name,
        'total_votes': total_votes,
        'candidate_count': candidates_qs.count(),
        'turnout_pct': turnout_pct,
        'duration_hours': duration_hours,
        'overall': overall,
        'grouped_sections': grouped_sections,
    }
    return render(request, 'results.html', context)


def public_results(request):
    """Public read-only results page (no admin session required)"""
    total_votes = Vote.objects.count()
    total_voters = Voter.objects.count()
    unique_voters_voted = Vote.objects.values('voter_id').distinct().count()
    turnout_pct = round((unique_voters_voted / total_voters) * 100, 2) if total_voters else 0
    candidates_qs = Candidate.objects.annotate(votes_count=Count('vote')).order_by('-votes_count', 'name')

    overall = []
    for c in candidates_qs:
        percent = round((c.votes_count / total_votes) * 100, 2) if total_votes else 0
        overall.append({'name': c.name, 'position': c.position, 'votes': c.votes_count, 'percentage': percent})

    # Group by position
    by_section = {}
    for c in candidates_qs:
        by_section.setdefault(c.position, []).append(c)

    grouped_sections = []
    for position, items in by_section.items():
        section_total = sum(i.votes_count for i in items)
        items_sorted = sorted(items, key=lambda x: (-x.votes_count, x.name))
        section_rows = [
            {
                'name': i.name,
                'votes': i.votes_count,
                'percentage': round((i.votes_count / section_total) * 100, 2) if section_total else 0,
            }
            for i in items_sorted
        ]
        grouped_sections.append({
            'position': position,
            'total': section_total,
            'rows': section_rows,
        })

    # Approximate duration from first vote to now
    try:
        first_vote_time = Vote.objects.earliest('voted_at').voted_at
        duration_hours = int((timezone.now() - first_vote_time).total_seconds() // 3600)
    except Vote.DoesNotExist:
        duration_hours = 0

    context = {
        'election_title': 'Chairperson Election 2024',
        'total_votes': total_votes,
        'candidate_count': candidates_qs.count(),
        'turnout_pct': turnout_pct,
        'duration_hours': duration_hours,
        'overall': overall,
        'grouped_sections': grouped_sections,
    }
    return render(request, 'public_results.html', context)

def admin_login(request):
    """Admin login page - supports email or username"""
    if request.method == 'POST':
        username_or_email = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        # Determine if input is email or username
        user = None
        if '@' in username_or_email:
            # Try to find user by email
            try:
                user_obj = User.objects.get(email=username_or_email)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass
        else:
            # Try username
            user = authenticate(request, username=username_or_email, password=password)
        
        if user is not None and user.is_staff:
            # Set session for compatibility with existing code
            request.session['is_admin'] = True
            request.session['admin_user_id'] = user.id
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('results')
        else:
            messages.error(request, 'Invalid credentials or not authorized as admin')
    
    return render(request, 'admin_login.html')

def admin_logout(request):
    """Admin logout"""
    request.session.pop('is_admin', None)
    return redirect('admin_login')

def add_voters(request):
    """Add voters page - Admin only"""
    # Check if user is admin
    if not request.session.get('is_admin'):
        messages.error(request, 'Please login as admin to access this page')
        return redirect('admin_login')
    
    if request.method == 'POST':
        phone_numbers = request.POST.get('phone_numbers', '')
        
        # Split by newlines and commas
        phone_list = []
        for line in phone_numbers.split('\n'):
            for phone in line.split(','):
                phone = phone.strip()
                if phone:
                    phone_list.append(phone)
        
        success_count = 0
        error_count = 0
        errors = []
        
        for phone in phone_list:
            try:
                # Normalize the phone number
                normalized_phone = Voter.normalize_phone_number(phone)
                
                # Check if voter already exists
                if Voter.objects.filter(phone_number=normalized_phone).exists():
                    errors.append(f"{phone} - Already registered")
                    error_count += 1
                    continue
                
                # Create new voter
                voter = Voter(phone_number=normalized_phone)
                voter.full_clean()  # Validate
                voter.save()
                success_count += 1
                
            except ValidationError as e:
                errors.append(f"{phone} - Invalid format")
                error_count += 1
            except Exception as e:
                errors.append(f"{phone} - Error: {str(e)}")
                error_count += 1
        
        # Show success message
        if success_count > 0:
            messages.success(request, f'Successfully added {success_count} voter(s)')
        
        # Show error messages
        if error_count > 0:
            for error in errors[:10]:  # Show only first 10 errors
                messages.warning(request, error)
            if len(errors) > 10:
                messages.warning(request, f'...and {len(errors) - 10} more errors')
    
    # Get all voters
    voters = Voter.objects.all()
    
    context = {
        'voters': voters,
        'total_voters': voters.count(),
        'voted_count': voters.filter(has_voted=True).count(),
    }
    
    return render(request, 'add_voters.html', context)

def delete_voter(request, voter_id):
    """Delete a voter - Admin only"""
    if not request.session.get('is_admin'):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        voter = Voter.objects.get(id=voter_id)
        phone = voter.phone_number
        voter.delete()
        messages.success(request, f'Voter {phone} deleted successfully')
        return JsonResponse({'success': True})
    except Voter.DoesNotExist:
        return JsonResponse({'error': 'Voter not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET", "POST"])
def add_candidates(request):
    """Add candidates page - Admin only"""
    if not request.session.get('is_admin'):
        messages.error(request, 'Please login as admin to access this page')
        return redirect('admin_login')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        nickname = request.POST.get('nickname', '').strip()
        position = request.POST.get('position', '').strip() or 'Candidate'
        description = request.POST.get('description', '').strip()
        photo = request.FILES.get('photo')

        if not name:
            messages.error(request, 'Full Name is required')
        else:
            candidate = Candidate(name=name, nickname=nickname, position=position, description=description)
            if photo:
                candidate.photo = photo
            candidate.save()
            messages.success(request, f'Candidate {name} added successfully')

    candidates = Candidate.objects.all()
    context = {
        'candidates': candidates,
        'total_candidates': candidates.count(),
    }
    return render(request, 'add_candidates.html', context)


@require_http_methods(["GET", "POST"])
def edit_candidate(request, candidate_id: int):
    """Edit an existing candidate"""
    if not request.session.get('is_admin'):
        messages.error(request, 'Please login as admin to access this page')
        return redirect('admin_login')

    try:
        candidate = Candidate.objects.get(id=candidate_id)
    except Candidate.DoesNotExist:
        messages.error(request, 'Candidate not found')
        return redirect('add_candidates')

    if request.method == 'POST':
        candidate.name = request.POST.get('name', candidate.name).strip()
        candidate.nickname = request.POST.get('nickname', candidate.nickname).strip()
        candidate.position = request.POST.get('position', candidate.position).strip() or candidate.position
        candidate.description = request.POST.get('description', candidate.description).strip()
        photo = request.FILES.get('photo')
        if photo:
            candidate.photo = photo
        candidate.save()
        messages.success(request, 'Candidate updated')
        return redirect('add_candidates')

    context = { 'candidate': candidate }
    return render(request, 'edit_candidate.html', context)


@require_http_methods(["GET", "POST"])
def admin_change_password(request):
    """Admin change password page"""
    if not request.session.get('is_admin'):
        messages.error(request, 'Please login as admin to access this page')
        return redirect('admin_login')
    
    # Get current admin user
    admin_user_id = request.session.get('admin_user_id')
    if not admin_user_id:
        messages.error(request, 'Session expired. Please login again.')
        return redirect('admin_login')
    
    try:
        user = User.objects.get(id=admin_user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found')
        return redirect('admin_login')
    
    if request.method == 'POST':
        old_password = request.POST.get('old_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        # Validate old password
        if not user.check_password(old_password):
            messages.error(request, 'Current password is incorrect')
        elif new_password != confirm_password:
            messages.error(request, 'New passwords do not match')
        elif len(new_password) < 6:
            messages.error(request, 'New password must be at least 6 characters')
        else:
            # Update password
            user.set_password(new_password)
            user.save()
            messages.success(request, 'Password changed successfully!')
            return redirect('results')
    
    context = {'user': user}
    return render(request, 'admin_change_password.html', context)


@require_http_methods(["GET", "POST"])
def vote(request):
    """Voter selects a candidate to vote for"""
    voter_phone = request.session.get('voter_phone')
    if not voter_phone:
        messages.error(request, 'Please login to vote')
        return redirect('login')

    voter = Voter.objects.filter(phone_number=voter_phone).first()
    if not voter:
        messages.error(request, 'Voter not found')
        return redirect('login')

    # Check election settings - if voting is allowed
    settings = ElectionSettings.get_settings()
    now = timezone.now()
    
    # Check if voting is active
    if not settings.is_active:
        messages.error(request, 'Voting is currently disabled by the administrator.')
        return redirect('landing')
    
    # Check if voting has started
    if settings.start_time and now < settings.start_time:
        messages.error(request, f'Voting has not started yet. Please come back after {settings.start_time.strftime("%B %d, %Y at %I:%M %p")}.')
        return redirect('landing')
    
    # Check if voting has ended
    if settings.end_time and now > settings.end_time:
        messages.error(request, f'Voting has ended on {settings.end_time.strftime("%B %d, %Y at %I:%M %p")}. Thank you for your interest.')
        return redirect('landing')

    if request.method == 'POST':
        candidate_id = request.POST.get('candidate_id')
        try:
            candidate = Candidate.objects.get(id=candidate_id)
            # Enforce one vote per section/position
            if Vote.objects.filter(voter=voter, candidate__position=candidate.position).exists():
                messages.warning(request, f'You have already voted in the "{candidate.position}" section.')
            else:
                Vote.objects.create(voter=voter, candidate=candidate)
                # Mark that the voter has participated at least once
                if not voter.has_voted:
                    voter.has_voted = True
                    voter.save(update_fields=['has_voted'])
                messages.success(request, f'Thank you! Your vote for {candidate.name} in "{candidate.position}" has been recorded.')
        except Candidate.DoesNotExist:
            messages.error(request, 'Candidate not found')

    # Group candidates by position for clearer UI
    candidates = Candidate.objects.all().order_by('position', 'name')
    grouped = {}
    for c in candidates:
        grouped.setdefault(c.position, []).append(c)
    return render(request, 'vote.html', { 'grouped': grouped, 'voter_phone': voter_phone })


@require_http_methods(["GET", "POST"])
def election_settings(request):
    """Election settings page - Admin only"""
    if not request.session.get('is_admin'):
        messages.error(request, 'Please login as admin to access this page')
        return redirect('admin_login')
    
    settings = ElectionSettings.get_settings()
    
    if request.method == 'POST':
        # Update settings
        settings.election_title = request.POST.get('election_title', settings.election_title)
        settings.election_description = request.POST.get('election_description', settings.election_description)
        settings.timezone = request.POST.get('timezone', settings.timezone)
        settings.is_active = request.POST.get('is_active') == 'on'
        
        # Handle start_time
        start_time_str = request.POST.get('start_time')
        if start_time_str:
            try:
                # Parse the datetime string
                naive_start = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
                # Make it timezone aware
                tz = pytz.timezone(settings.timezone)
                settings.start_time = tz.localize(naive_start)
            except (ValueError, pytz.exceptions.UnknownTimeZoneError) as e:
                messages.error(request, f'Invalid start time or timezone: {e}')
        
        # Handle end_time
        end_time_str = request.POST.get('end_time')
        if end_time_str:
            try:
                naive_end = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
                tz = pytz.timezone(settings.timezone)
                settings.end_time = tz.localize(naive_end)
            except (ValueError, pytz.exceptions.UnknownTimeZoneError) as e:
                messages.error(request, f'Invalid end time or timezone: {e}')
        
        settings.save()
        messages.success(request, 'Election settings updated successfully!')
        return redirect('election_settings')
    
    # Get common timezones for the dropdown
    common_timezones = [
        'UTC',
        'Africa/Freetown',  # Sierra Leone
        'Africa/Lagos',  # Nigeria
        'Africa/Accra',  # Ghana
        'Europe/London',
        'America/New_York',
        'America/Los_Angeles',
        'Asia/Dubai',
    ]
    
    # Format datetime for HTML input
    start_time_formatted = settings.start_time.strftime('%Y-%m-%dT%H:%M') if settings.start_time else ''
    end_time_formatted = settings.end_time.strftime('%Y-%m-%dT%H:%M') if settings.end_time else ''
    
    context = {
        'settings': settings,
        'common_timezones': common_timezones,
        'start_time_formatted': start_time_formatted,
        'end_time_formatted': end_time_formatted,
    }
    return render(request, 'election_settings.html', context)


def download_results(request):
    """Download election results as CSV"""
    # Get election settings
    settings = ElectionSettings.get_settings()
    
    # Calculate statistics
    total_votes = Vote.objects.count()
    total_voters = Voter.objects.count()
    unique_voters_voted = Vote.objects.values('voter_id').distinct().count()
    turnout_pct = round((unique_voters_voted / total_voters) * 100, 2) if total_voters else 0
    
    # Get candidates with vote counts
    candidates_qs = Candidate.objects.annotate(votes_count=Count('vote')).order_by('position', '-votes_count', 'name')
    
    # Create the HttpResponse object with CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="election_results_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    
    # Write header information
    writer.writerow(['ELECTION RESULTS REPORT'])
    writer.writerow([])
    writer.writerow(['Election Title:', settings.election_title])
    writer.writerow(['Generated On:', timezone.now().strftime('%B %d, %Y at %I:%M %p')])
    writer.writerow(['Timezone:', settings.timezone])
    writer.writerow([])
    
    # Write summary statistics
    writer.writerow(['SUMMARY STATISTICS'])
    writer.writerow(['Total Votes Cast:', total_votes])
    writer.writerow(['Total Registered Voters:', total_voters])
    writer.writerow(['Voters Who Voted:', unique_voters_voted])
    writer.writerow(['Turnout Percentage:', f'{turnout_pct}%'])
    writer.writerow([])
    
    # Write overall results
    writer.writerow(['OVERALL RESULTS'])
    writer.writerow(['Rank', 'Candidate Name', 'Position', 'Votes', 'Percentage'])
    
    rank = 1
    for c in candidates_qs:
        percentage = round((c.votes_count / total_votes) * 100, 1) if total_votes else 0
        writer.writerow([rank, c.name, c.position, c.votes_count, f'{percentage}%'])
        rank += 1
    
    writer.writerow([])
    
    # Write results by position
    writer.writerow(['RESULTS BY POSITION'])
    writer.writerow([])
    
    # Group by position
    by_position = {}
    for c in candidates_qs:
        if c.position not in by_position:
            by_position[c.position] = []
        percentage = round((c.votes_count / total_votes) * 100, 1) if total_votes else 0
        by_position[c.position].append({
            'name': c.name,
            'votes': c.votes_count,
            'percentage': percentage
        })
    
    for position, candidates in by_position.items():
        writer.writerow([f'Position: {position}'])
        writer.writerow(['Rank', 'Candidate Name', 'Votes', 'Percentage', 'Status'])
        
        for idx, c in enumerate(candidates, 1):
            status = 'WINNER' if idx == 1 and c['votes'] > 0 else ''
            # Check for tie
            if idx == 1 and len(candidates) >= 2 and candidates[0]['votes'] == candidates[1]['votes']:
                status = 'TIE'
            writer.writerow([idx, c['name'], c['votes'], f"{c['percentage']}%", status])
        
        writer.writerow([])
    
    # Write vote details
    writer.writerow(['DETAILED VOTE LOG'])
    writer.writerow(['Voter Phone', 'Candidate', 'Position', 'Voted At'])
    
    votes = Vote.objects.select_related('voter', 'candidate').order_by('-voted_at')
    for vote in votes:
        writer.writerow([
            vote.voter.phone_number,
            vote.candidate.name,
            vote.candidate.position,
            vote.voted_at.strftime('%B %d, %Y at %I:%M %p')
        ])
    
    return response


def download_results_pdf(request):
    """Download election results as PDF with complete analysis"""
    # Get election settings
    settings = ElectionSettings.get_settings()
    
    # Calculate statistics
    total_votes = Vote.objects.count()
    total_voters = Voter.objects.count()
    unique_voters_voted = Vote.objects.values('voter_id').distinct().count()
    turnout_pct = round((unique_voters_voted / total_voters) * 100, 2) if total_voters else 0
    
    # Get candidates with vote counts
    candidates_qs = Candidate.objects.annotate(votes_count=Count('vote')).order_by('position', '-votes_count', 'name')
    
    # Create the HttpResponse object with PDF header
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="election_results_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
    
    # Create the PDF object using BytesIO buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Container for PDF elements
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2563eb'),
        spaceAfter=12,
        spaceBefore=20,
        fontName='Helvetica-Bold'
    )
    
    normal_style = styles['Normal']
    
    # Title
    elements.append(Paragraph("ELECTION RESULTS REPORT", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Election Information
    info_data = [
        ['Election Title:', settings.election_title],
        ['Generated On:', timezone.now().strftime('%B %d, %Y at %I:%M %p')],
        ['Timezone:', settings.timezone],
    ]
    
    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#374151')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Summary Statistics
    elements.append(Paragraph("SUMMARY STATISTICS", heading_style))
    
    stats_data = [
        ['Metric', 'Value'],
        ['Total Votes Cast', str(total_votes)],
        ['Total Registered Voters', str(total_voters)],
        ['Voters Who Voted', str(unique_voters_voted)],
        ['Turnout Percentage', f'{turnout_pct}%'],
    ]
    
    stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
    ]))
    elements.append(stats_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Overall Results
    elements.append(Paragraph("OVERALL RESULTS", heading_style))
    
    overall_data = [['Rank', 'Candidate Name', 'Position', 'Votes', 'Percentage']]
    rank = 1
    for c in candidates_qs:
        percentage = round((c.votes_count / total_votes) * 100, 1) if total_votes else 0
        overall_data.append([str(rank), c.name, c.position, str(c.votes_count), f'{percentage}%'])
        rank += 1
    
    overall_table = Table(overall_data, colWidths=[0.6*inch, 2*inch, 1.5*inch, 0.8*inch, 1*inch])
    overall_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        # Highlight first row (winner)
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#dcfce7')),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#166534')),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
    ]))
    elements.append(overall_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Results by Position
    elements.append(Paragraph("RESULTS BY POSITION", heading_style))
    
    # Group by position
    by_position = {}
    for c in candidates_qs:
        if c.position not in by_position:
            by_position[c.position] = []
        percentage = round((c.votes_count / total_votes) * 100, 1) if total_votes else 0
        by_position[c.position].append({
            'name': c.name,
            'votes': c.votes_count,
            'percentage': percentage
        })
    
    for position, candidates in by_position.items():
        # Position title
        elements.append(Paragraph(f"<b>{position}</b>", styles['Heading3']))
        elements.append(Spacer(1, 0.1*inch))
        
        position_data = [['Rank', 'Candidate Name', 'Votes', 'Percentage', 'Status']]
        
        for idx, c in enumerate(candidates, 1):
            status = 'WINNER' if idx == 1 and c['votes'] > 0 else ''
            # Check for tie
            if idx == 1 and len(candidates) >= 2 and candidates[0]['votes'] == candidates[1]['votes']:
                status = 'TIE'
            position_data.append([str(idx), c['name'], str(c['votes']), f"{c['percentage']}%", status])
        
        position_table = Table(position_data, colWidths=[0.6*inch, 2.5*inch, 0.8*inch, 1*inch, 1*inch])
        position_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
            # Highlight winner
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#dcfce7')),
            ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#166534')),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ]))
        elements.append(position_table)
        elements.append(Spacer(1, 0.2*inch))
    
    # Build PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer and write it to response
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response
