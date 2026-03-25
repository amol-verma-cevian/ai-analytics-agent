from fastapi import APIRouter, Query
from typing import Optional

from app.services.data_service import (
    get_orders_summary,
    get_revenue_summary,
    get_cancellations_summary,
    get_city_info,
    get_restaurants,
    get_hourly_trends,
    get_week_comparison,
    get_top_metrics_for_ceo,
)

router = APIRouter()


@router.get("/orders")
async def orders(date: Optional[str] = None, city: Optional[str] = None):
    """Order metrics, filterable by date and city."""
    return get_orders_summary(target_date=date, city=city)


@router.get("/revenue")
async def revenue(date: Optional[str] = None, city: Optional[str] = None):
    """Revenue metrics, filterable by date and city."""
    return get_revenue_summary(target_date=date, city=city)


@router.get("/cancellations")
async def cancellations(date: Optional[str] = None, city: Optional[str] = None):
    """Cancellation metrics, filterable by date and city."""
    return get_cancellations_summary(target_date=date, city=city)


@router.get("/cities")
async def cities(city: Optional[str] = None):
    """City metadata."""
    return get_city_info(city=city)


@router.get("/restaurants")
async def restaurants(city: Optional[str] = None, min_complaints: Optional[int] = None):
    """Restaurant data, filterable by city and minimum complaint count."""
    return get_restaurants(city=city, min_complaints=min_complaints)


@router.get("/hourly")
async def hourly(date: Optional[str] = None, city: Optional[str] = None):
    """Hourly order/revenue trends."""
    return get_hourly_trends(target_date=date, city=city)


@router.get("/week-comparison")
async def week_comparison(city: Optional[str] = None):
    """This week vs last week comparison."""
    return get_week_comparison(city=city)


@router.get("/ceo-summary")
async def ceo_summary():
    """Top 3 metrics for CEO: total orders, revenue, cancellation rate."""
    return get_top_metrics_for_ceo()
