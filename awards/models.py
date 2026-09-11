# awards/models.py
"""
OMA Flowers — Award model.

Includes:
  • Award fields (distributor, name, category, prize, description, year).
  • AUTO_SEED() — generates award rows for every qualifying distributor
    based on the OMA Flowers business plan (Sections 9 & 10).
  • Idempotent: safe to call on every request.
"""

from datetime import date

from django.db import models, transaction


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
# Award templates (OMA document Sections 9 & 10)
# ------------------------------------------------------------------
AWARD_TEMPLATES = [
    # ---------- Section 9.1: Golden Certificate ----------
    {
        'name': 'Golden Certificate Award',
        'category': 'annual',
        'prize': 'Special Golden Certificate',
        'description': (
            'Tuzo ya Cheti Maalum cha Dhahabu — Qualified Manager with MPGV '
            'exceeding 3,000 PV monthly. Awarded once per year.'
        ),
        'min_rank': 'Manager',
    },

    # ---------- Section 9.2: Continental Trip ----------
    {
        'name': 'Continental Trip Award',
        'category': 'annual',
        'prize': 'Trip within the continent — TSh 5,000,000',
        'description': (
            'Tuzo ya Safari (Ndani ya Bara) — Qualified Senior Manager with '
            'annual CGV ≥ 35,000 BV. Three trip phases.'
        ),
        'min_rank': 'Senior Manager',
    },

    # ---------- Section 9.3: International Trip ----------
    {
        'name': 'International Trip Award',
        'category': 'annual',
        'prize': 'Trip outside the continent — TSh 10,000,000',
        'description': (
            'Tuzo ya Safari Nje ya Bara — Qualified Director with five '
            'active legs.'
        ),
        'min_rank': 'Director',
    },

    # ---------- Section 9.4: Normal Car ----------
    {
        'name': 'Normal Car Award',
        'category': 'legacy',
        'prize': 'Normal car — ~TSh 31,250,000',
        'description': (
            'Tuzo ya Gari ya Kawaida — every 4 years, a Qualified Active '
            'Crown Director receives a car.'
        ),
        'min_rank': 'Crown Director',
    },

    # ---------- Section 9.5: Luxury Car ----------
    {
        'name': 'Luxury Car Award',
        'category': 'legacy',
        'prize': 'Luxury car — TSh 62,500,000',
        'description': (
            'Tuzo ya Gari ya Kifahari — Qualified Crown Director with five '
            'active legs, or Royal Crown Director with four active legs.'
        ),
        'min_rank': 'Crown Director',
    },

    # ---------- Section 9.6: House ----------
    {
        'name': 'House Award',
        'category': 'legacy_circle',
        'prize': 'House',
        'description': (
            'Tuzo ya Nyumba — Qualified Royal Crown Director with active legs.'
        ),
        'min_rank': 'Royal Crown Director',
    },

    # ---------- Section 10.1: Team Builder ----------
    {
        'name': 'Team Builder of the Year',
        'category': 'annual',
        'prize': 'Recognition + trophy',
        'description': (
            'For the leader who built the strongest team — active members, '
            'customer growth, stable sales.'
        ),
        'min_rank': 'Senior Leader',
    },

    # ---------- Section 10.2: Sales Excellence ----------
    {
        'name': 'Annual Sales Excellence Award',
        'category': 'annual',
        'prize': 'Recognition + trophy',
        'description': (
            'For distributors who set sales records — Diamond Garden winners.'
        ),
        'min_rank': 'Leader',
    },

    # ---------- Section 10.3: Best Trainer ----------
    {
        'name': 'Best Trainer Award',
        'category': 'annual',
        'prize': 'Recognition + trophy',
        'description': (
            'For the trainer who changed the most lives — Mentor Academy '
            'winners.'
        ),
        'min_rank': 'Manager',
    },

    # ---------- Section 10.4: Best Shop ----------
    {
        'name': 'Best Shop Attendance',
        'category': 'annual',
        'prize': 'Recognition',
        'description': 'For the best-performing office or shop.',
        'min_rank': 'Manager',
    },

    # ---------- Section 10.5: Event Designer ----------
    {
        'name': 'Event Designer of the Year',
        'category': 'annual',
        'prize': 'Recognition + featured on official pages',
        'description': (
            'For the Academy that demonstrated the best creative decoration.'
        ),
        'min_rank': 'Senior Leader',
    },

    # ---------- Section 10.6: Innovation ----------
    {
        'name': 'Innovation Award',
        'category': 'special',
        'prize': 'Recognition',
        'description': (
            'For new product, new flower, new decoration style, or new '
            'marketing idea.'
        ),
        'min_rank': 'Builder',
    },

    # ---------- Section 10.7: Signature Designer ----------
    {
        'name': 'OMA Signature Designer',
        'category': 'special',
        'prize': 'OMA Signature Designer trophy + training role',
        'description': (
            'Top 10 Signature Events of the year — published on official '
            'channels and invited to teach at OMA Flowers Academy.'
        ),
        'min_rank': 'Leader',
    },

    # ---------- Section 10.8: Legacy Circle ----------
    {
        'name': 'Legacy Circle Award',
        'category': 'legacy_circle',
        'prize': 'OMA Legacy Ring + entry in OMA Hall of Legends',
        'description': (
            'Legacy Circle Award — every 5 years, distributors who built a '
            'strong business are inducted. Their names stay in the OMA Hall '
            'of Legends forever.'
        ),
        'min_rank': 'Crown Director',
    },
]


class Award(models.Model):
    CATEGORY_CHOICES = (
        ('legacy_circle', 'Legacy Circle'),
        ('legacy', 'Legacy'),
        ('annual', 'Annual'),
        ('special', 'Special'),
    )

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('past', 'Past'),
        ('upcoming', 'Upcoming'),
    )

    distributor = models.ForeignKey(
        'distributors.Distributor',
        on_delete=models.CASCADE,
        related_name='awards',
    )
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    prize = models.CharField(max_length=200)
    description = models.TextField()
    year = models.PositiveSmallIntegerField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='upcoming'
    )
    given_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'awards'
        ordering = ['-year', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['distributor', 'name', 'year'],
                name='unique_award_per_distributor_per_year',
            ),
        ]

    def __str__(self):
        return f"{self.distributor.user.full_name} - {self.name}"

    # ----------------------------------------------------------------
    # Auto-seed (called by the view on first request)
    # ----------------------------------------------------------------

    @classmethod
    def auto_seed(cls, year=None):
        """
        Generate award rows for every qualifying distributor based on
        the OMA Flowers business plan (Sections 9 & 10).

        Idempotent:
          • Runs only if the table is empty.
          • Uses get_or_create to avoid duplicates.
        """
        if cls.objects.exists():
            return 0

        from distributors.models import Distributor

        if year is None:
            year = date.today().year

        created = 0

        with transaction.atomic():
            for d in Distributor.objects.select_related('user').all():
                for tpl in AWARD_TEMPLATES:
                    min_idx = RANK_ORDER.get(tpl['min_rank'], 99)
                    d_idx = RANK_ORDER.get(d.rank, -1)
                    if d_idx < min_idx:
                        continue

                    _, was_created = cls.objects.get_or_create(
                        distributor=d,
                        name=tpl['name'],
                        year=year,
                        defaults={
                            'category': tpl['category'],
                            'prize': tpl['prize'],
                            'description': tpl['description'],
                            'status': 'upcoming',
                        },
                    )
                    if was_created:
                        created += 1

        return created