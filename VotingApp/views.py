from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.models import User
from .models import Voter, Candidate, Vote, AdminUser
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.utils import timezone
from django.views.decorators.http import require_http_methods

def landing_page(request):
    """Landing page for the chairperson election with real-time results"""
    # Get all candidates with their vote counts
    candidates_qs = Candidate.objects.annotate(votes_count=Count('vote')).order_by('-votes_count', 'name')
    
    # Calculate total votes cast
    total_votes = Vote.objects.count()
    total_voters = Voter.objects.count()
    
    # Build candidate list with percentages
    candidates_data = []
    for c in candidates_qs:
        percentage = round((c.votes_count / total_votes) * 100, 1) if total_votes else 0
        candidates_data.append({
            'id': c.id,
            'name': c.name,
            'nickname': c.nickname,
            'position': c.position,
            'photo': c.photo,
            'votes': c.votes_count,
            'percentage': percentage,
        })
    
    # Determine winner (candidate with most votes)
    winner = candidates_data[0] if candidates_data and total_votes > 0 else None
    
    # Check if there's a clear winner or tie
    is_tie = False
    if len(candidates_data) >= 2 and candidates_data[0]['votes'] == candidates_data[1]['votes'] and candidates_data[0]['votes'] > 0:
        is_tie = True
    
    context = {
        'election_title': 'Porpon Young Generation Chairman and Lady Election',
        'election_description': 'Vote for your preferred candidate for the position of Chairman and Lady',
        'election_status': 'Active',
        'end_date': 'September 2025',
        'candidate_count': candidates_qs.count(),
        'candidates': candidates_data,
        'total_votes': total_votes,
        'total_voters': total_voters,
        'winner': winner,
        'is_tie': is_tie,
    }
    return render(request, 'landing.html', context)

def login_page(request):
    """Login page for phone number entry"""
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
