from django.contrib import admin
# pyrefly: ignore [missing-import]
from apps.betting.models import Bet, BetSelection


class BetSelectionInline(admin.TabularInline):
    model = BetSelection
    extra = 0
    readonly_fields = ("selection", "odds_at_placement")

@admin.register(Bet)
class BetAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "bet_type", "stake", "total_odds", "status", "created_at")
    list_filter = ("status", "bet_type", "created_at")
    search_fields = ("id", "user__username", "idempotency_key")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [BetSelectionInline]