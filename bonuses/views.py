# bonuses/views.py
from decimal import Decimal
from datetime import date

from django.db import transaction
from rest_framework import generics, filters
from django_filters.rest_framework import DjangoFilterBackend

from distributors.models import Distributor
from .models import Bonus
from .serializers import BonusSerializer


# ------------------------------------------------------------------
# Rank strength map
# ------------------------------------------------------------------
RANK_ORDER = {
    'Seed': -1, 'Associate': 0, 'Builder': 1, 'Leader': 2,
    'Senior Leader': 3, 'Executive': 4, 'Manager': 5,
    'Senior Manager': 6, 'Director': 7, 'Crown Director': 8,
    'Royal Crown Director': 9,
}


# ------------------------------------------------------------------
# Bonus templates (from OMA document Sections 5 & 6)
# ------------------------------------------------------------------
BONUS_TEMPLATES = [
    {
        'name': 'Consistency Bonus',
        'type': 'consistency',
        'amount': Decimal('75000'),
        'description': (
            'Consistency Bonus — for registering new members who stay '
            'active for 4+ consecutive months with an SRS ≥ 50.'
        ),
        'qualifies': lambda d: d.downline_members.count() >= 1,
    },
    {
        'name': 'Smart Referral Score Bonus',
        'type': 'referral',
        'amount': Decimal('50000'),
        'description': (
            'Smart Referral Score Bonus — 20 points per new member + 30 '
            'points on their first purchase. Awarded at 50+ SRS.'
        ),
        'qualifies': lambda d: d.downline_members.count() >= 3,
    },
    {
        'name': 'Loyalty Sponsor Bonus',
        'type': 'loyalty',
        'amount': Decimal('50000'),
        'description': (
            'Loyalty Sponsor Bonus — awarded yearly to the top 3 '
            'consistency sponsors.'
        ),
        'qualifies': lambda d: d.downline_members.count() >= 3,
    },
    {
        'name': 'Diamond Garden Star',
        'type': 'dynamic',
        'amount': Decimal('200000'),
        'description': (
            'Diamond Garden Star ★★★ — top seller with 250+ PV monthly '
            'throughout the year.'
        ),
        'qualifies': lambda d: Decimal(d.pbv or 0) >= Decimal('250'),
    },
    {
        'name': 'Gold Garden Star',
        'type': 'dynamic',
        'amount': Decimal('150000'),
        'description': (
            'Gold Garden Star ★★ — second-best monthly seller.'
        ),
        'qualifies': lambda d: Decimal(d.pbv or 0) >= Decimal('150'),
    },
    {
        'name': 'Silver Garden Star',
        'type': 'dynamic',
        'amount': Decimal('100000'),
        'description': (
            'Silver Garden Star ★ — third-best monthly seller.'
        ),
        'qualifies': lambda d: Decimal(d.pbv or 0) >= Decimal('100'),
    },
    {
        'name': 'Training Excellence Bonus',
        'type': 'training',
        'amount': Decimal('150000'),
        'description': (
            "OMA Flower's Academy trainer who showed real transformation."
        ),
        'qualifies': lambda d: Decimal(d.pbv or 0) >= Decimal('100'),
    },
    {
        'name': 'Mentor Academy Bonus',
        'type': 'training',
        'amount': Decimal('250000'),
        'description': (
            'Mentor Academy Bonus — for trainers who developed other trainers.'
        ),
        'qualifies': lambda d: (
            RANK_ORDER.get(d.rank, -1) >= RANK_ORDER['Manager']
            and d.downline_members.count() >= 5
        ),
    },
    {
        'name': 'Event Booking Bonus',
        'type': 'booking',
        'amount': Decimal('45000'),
        'description': (
            'Event Booking Bonus — 5% of event revenue after client confirms.'
        ),
        'qualifies': lambda d: Decimal(d.pbv or 0) >= Decimal('50'),
    },
    {
        'name': 'Creative Design Bonus',
        'type': 'design',
        'amount': Decimal('120000'),
        'description': (
            'Creative Design Bonus — Best Wedding / Graduation Decoration.'
        ),
        'qualifies': lambda d: (
            Decimal(d.pbv or 0) >= Decimal('80')
            and d.downline_members.count() >= 2
        ),
    },
    {
        'name': 'Event Referral Bonus',
        'type': 'referral',
        'amount': Decimal('40000'),
        'description': 'Event Referral Bonus — client satisfaction referral.',
        'qualifies': lambda d: d.downline_members.count() >= 2,
    },
    {
        'name': 'Festival Bonus',
        'type': 'festival',
        'amount': Decimal('80000'),
        'description': (
            'Festival Bonus — for the Academy chosen to serve a festival.'
        ),
        'qualifies': lambda d: (
            RANK_ORDER.get(d.rank, -1) >= RANK_ORDER['Leader']
        ),
    },
]


# ------------------------------------------------------------------
# Auto-seed (idempotent)
# ------------------------------------------------------------------

def _ensure_bonuses_seeded():
    """Generate bonus rows on the first API hit if the table is empty."""
    if Bonus.objects.exists():
        return

    today = date.today()
    month = today.strftime('%B')
    year = today.year

    with transaction.atomic():
        for d in Distributor.objects.select_related('user').all():
            for tpl in BONUS_TEMPLATES:
                try:
                    if not tpl['qualifies'](d):
                        continue
                except Exception:
                    continue

                Bonus.objects.get_or_create(
                    distributor=d,
                    name=tpl['name'],
                    month=month,
                    year=year,
                    defaults={
                        'type': tpl['type'],
                        'amount': tpl['amount'],
                        'description': tpl['description'],
                        'status': 'pending',
                    },
                )


# ------------------------------------------------------------------
# Views
# ------------------------------------------------------------------

class BonusListView(generics.ListAPIView):
    queryset = Bonus.objects.select_related('distributor__user').all()
    serializer_class = BonusSerializer
    permission_classes = []
    authentication_classes = []

    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['type', 'status', 'distributor', 'year', 'month']
    search_fields = ['name', 'distributor__user__email']

    def get_queryset(self):
        _ensure_bonuses_seeded()
        return super().get_queryset()


class BonusDetailView(generics.RetrieveUpdateAPIView):
    queryset = Bonus.objects.select_related('distributor__user').all()
    serializer_class = BonusSerializer
    permission_classes = []
    authentication_classes = []
    lookup_field = 'id'